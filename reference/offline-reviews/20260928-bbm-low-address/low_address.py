#!/usr/bin/env python3
"""Bounded, non-faulting A715 BBM path coverage. No default device action."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import signal
import subprocess
import sys

ADDRESS = PAGE = 4096
CPUS = (3, 4)
CYCLES = 4
EVENT = "gts9_bbm_low_245"
TRACE = Path("/sys/kernel/tracing")
BOOT = Path("/proc/sys/kernel/random/boot_id")
PTE_UXN = 1 << 54


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def verify_trace(trace, stats, pid):
    """Fail closed: exact workload count, low address, old PTE, and no loss."""
    require(set(stats) == {str(cpu) for cpu in range(8)}, "missing CPU stats")
    for cpu, raw in stats.items():
        for field in ("overrun", "commit overrun", "dropped events"):
            values = re.findall(r"^" + re.escape(field) + r":\s*(\d+)\s*$", raw, re.M)
            require(values == ["0"], f"CPU{cpu}: missing/nonzero {field}")
    rows = []
    pattern = re.compile(
        r"-(\d+)\s+\[(\d+)\].*?" + EVENT +
        r":.*?\baddr=(\d+)\s+nr=(\d+)\s+pte=(?:0x)?([0-9a-fA-F]+)\s*$")
    for line in trace.splitlines():
        if EVENT + ":" not in line:
            continue
        match = pattern.search(line)
        require(match is not None, "malformed probe or unreadable old PTE")
        task, cpu, addr, nr = map(int, match.groups()[:4])
        pte = int(match.group(5), 16)
        require(task == pid and cpu in CPUS, "wrong task/CPU")
        require(addr == ADDRESS and nr == 1, "missing low-address single-PTE branch")
        require(pte & 1, "old PTE not valid")
        rows.append((cpu, not bool(pte & PTE_UXN)))
    # Each cycle starts RW/NX, becomes RX, executes, then becomes RW/NX.
    for cpu in CPUS:
        require([execute for core, execute in rows if core == cpu] ==
                [False, True] * CYCLES, f"CPU{cpu}: incomplete/extra PTE sequence")
    return {"result": "low_address_path_covered", "probe_hits": len(rows),
            "executable_old_pte_hits": sum(execute for _, execute in rows),
            "address": ADDRESS, "nr": 1,
            "physical_erratum_reproduced": False, "cpu_stall_fix_established": False}


def worker():
    # Parent installs the PID filter before releasing this child.
    require(os.read(0, 1) == b"G", "missing parent handshake")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    signal.signal(signal.SIGALRM, signal.SIG_DFL)
    signal.alarm(8)  # Default SIGALRM terminates a stuck userspace child.
    require(os.uname().machine == "aarch64" and os.sysconf("SC_PAGE_SIZE") == PAGE,
            "requires native ARM64/4K pages")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.mmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int,
                          ctypes.c_int, ctypes.c_int, ctypes.c_long]
    libc.mmap.restype = ctypes.c_void_p
    for name in ("mprotect", "munmap"):
        getattr(libc, name).restype = ctypes.c_int
    libc.mprotect.argtypes = [ctypes.c_void_p, ctypes.c_size_t, ctypes.c_int]
    libc.munmap.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
    clear = ctypes.CDLL("libgcc_s.so.1").__clear_cache
    clear.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    clear.restype = None
    # MAP_PRIVATE | MAP_ANONYMOUS | MAP_FIXED_NOREPLACE. Never replace a mapping.
    address = libc.mmap(ADDRESS, PAGE, 3, 0x100022, -1, 0)
    if address == ctypes.c_void_p(-1).value:
        raise OSError(ctypes.get_errno(), "low mmap denied; no sysctl fallback")
    try:
        require(address == ADDRESS, "kernel ignored MAP_FIXED_NOREPLACE")
        ctypes.memmove(address, bytes.fromhex("40058052c0035fd6"), 8)
        clear(address, address + 8)
        function = ctypes.CFUNCTYPE(ctypes.c_int)(address)
        for cpu in CPUS:
            os.sched_setaffinity(0, {cpu})
            require(os.sched_getaffinity(0) == {cpu}, "CPU affinity mismatch")
            for _ in range(CYCLES):
                if libc.mprotect(address, PAGE, 5):
                    raise OSError(ctypes.get_errno(), "mprotect RX")
                require(function() == 42, "generated code returned wrong value")
                if libc.mprotect(address, PAGE, 3):
                    raise OSError(ctypes.get_errno(), "mprotect RW")
                # Read only while NX; no intentional instruction abort.
                require(ctypes.c_uint32.from_address(address).value == 0x52800540,
                        "generated code changed")
        print(json.dumps({"pid": os.getpid(), "mprotect_calls": 16,
                          "address": address, "completed": True}), flush=True)
    finally:
        if libc.munmap(address, PAGE):
            raise OSError(ctypes.get_errno(), "munmap")


def probe_command(command):
    fd = os.open(TRACE / "kprobe_events", os.O_WRONLY)
    try:
        data = (command + "\n").encode()
        require(os.write(fd, data) == len(data), "short tracefs write")
    finally:
        os.close(fd)


def run(expected_boot, expected_notes):
    require(BOOT.read_text().strip() == expected_boot, "wrong boot")
    require(hashlib.sha256(Path("/sys/kernel/notes").read_bytes()).hexdigest() ==
            expected_notes, "wrong kernel notes")
    require(os.geteuid() == 0 and os.uname().machine == "aarch64", "ARM64 root required")
    require(b"samsung,gts9wifi" in Path("/proc/device-tree/compatible").read_bytes(),
            "wrong board")
    require(os.sched_getaffinity(0).issuperset(CPUS), "A715 CPUs unavailable")
    identities = {}
    for cpu in CPUS:
        midr = int(Path(f"/sys/devices/system/cpu/cpu{cpu}/regs/identification/midr_el1").read_text(), 0)
        require((midr >> 4) & 0xfff == 0xd4d, "target CPU is not A715")
        identities[str(cpu)] = hex(midr)
    minimum = Path("/proc/sys/vm/mmap_min_addr").read_text().strip()
    status = Path("/proc/self/status").read_text()
    capabilities = int(re.search(r"^CapEff:\s*(\w+)$", status, re.M).group(1), 16)
    require(int(minimum) <= ADDRESS or capabilities & (1 << 17),
            "low mapping requires existing CAP_SYS_RAWIO; do not lower mmap_min_addr")
    instance = TRACE / "instances" / EVENT
    require(not instance.exists() and EVENT not in (TRACE / "kprobe_events").read_text(),
            "probe/instance already exists; refusing to modify it")
    child = None
    owns_event = owns_instance = False
    report = {"boot_id": expected_boot, "notes_sha256": expected_notes,
              "midr": identities, "mmap_min_addr": minimum, "cap_eff": hex(capabilities)}
    cleanup_errors = []
    try:
        child = subprocess.Popen([sys.executable, __file__, "--worker"],
                                 stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE)
        probe_command(f"p:{EVENT} modify_prot_start_ptes addr=%x1:u64 nr=%x3:u32 pte=+0(%x2):x64")
        owns_event = True
        instance.mkdir()
        owns_instance = True
        (instance / "tracing_on").write_text("0")
        (instance / "buffer_size_kb").write_text("16")
        event = instance / "events/kprobes" / EVENT
        (event / "filter").write_text(f"common_pid == {child.pid} && addr == {ADDRESS}")
        (event / "enable").write_text("1")
        (instance / "tracing_on").write_text("1")
        out, err = child.communicate(b"G", timeout=12)
        report.update(worker_stdout=out.decode(errors="replace"),
                      worker_stderr=err.decode(errors="replace"), worker_status=child.returncode)
        (event / "enable").write_text("0")
        (instance / "tracing_on").write_text("0")
        report["trace"] = (instance / "trace").read_text()
        report["stats"] = {str(cpu): (instance / f"per_cpu/cpu{cpu}/stats").read_text()
                           for cpu in range(8)}
        require(child.returncode == 0, "worker failed; no coverage verdict")
        result = json.loads(out)
        require(result == {"pid": child.pid, "mprotect_calls": 16,
                           "address": ADDRESS, "completed": True}, "unexpected worker result")
        report["coverage"] = verify_trace(report["trace"], report["stats"], child.pid)
        require(BOOT.read_text().strip() == expected_boot, "boot changed")
        require(Path("/proc/sys/vm/mmap_min_addr").read_text().strip() == minimum,
                "mmap_min_addr changed during run")
    except Exception as error:
        report["error"] = repr(error)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            try:
                out, err = child.communicate(timeout=2)
                report.update(worker_stdout=out.decode(errors="replace"),
                              worker_stderr=err.decode(errors="replace"),
                              worker_status=child.returncode)
            except subprocess.TimeoutExpired:
                cleanup_errors.append("child did not exit after SIGKILL")
        # Attempt all cleanup steps even if an earlier step fails.
        actions = []
        if owns_instance:
            actions = [lambda: (instance / "events/kprobes" / EVENT / "enable").write_text("0"),
                       lambda: (instance / "tracing_on").write_text("0")]
        for action in actions:
            try:
                action()
            except Exception as error:
                cleanup_errors.append(repr(error))
        if owns_instance:
            try:
                report.setdefault("trace", (instance / "trace").read_text())
                report.setdefault("stats", {
                    str(cpu): (instance / f"per_cpu/cpu{cpu}/stats").read_text()
                    for cpu in range(8)})
            except Exception as error:
                cleanup_errors.append(repr(error))
        actions = [instance.rmdir] if owns_instance else []
        if owns_event:
            actions.append(lambda: probe_command(f"-:{EVENT}"))
        for action in actions:
            try:
                action()
            except Exception as error:
                cleanup_errors.append(repr(error))
        report["cleanup_errors"] = cleanup_errors
        report["cpu_stall_fix_established"] = False
        print(json.dumps(report, sort_keys=True), flush=True)
    return 1 if "error" in report or cleanup_errors else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", action="store_true")
    group.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--expected-boot")
    parser.add_argument("--expected-notes-sha256")
    args = parser.parse_args()
    if args.worker:
        worker()
        return 0
    if not args.expected_boot or not args.expected_notes_sha256:
        parser.error("--run requires both expected boot and kernel notes hash")
    return run(args.expected_boot, args.expected_notes_sha256)


if __name__ == "__main__":
    sys.exit(main())
