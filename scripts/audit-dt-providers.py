#!/usr/bin/env python3
"""Which enabled device-tree nodes have no driver in the kernel we actually built?

Why this exists.  Five of this port's defects have been the same shape: a node in
the device tree references a provider, the provider's driver is not built, the
consumer's probe returns -EPROBE_DEFER, and it sits on the deferred list for the
life of the boot.  Every one was found by hand, one at a time, and the last one
(`epss_l3`, `CONFIG_INTERCONNECT_QCOM_OSM_L3`) was invisible to a *provider*
enumeration because a provider with no driver has no entry to enumerate.

Several of them have the same root cause, and it is worth naming: upstream's
`arch/arm64/configs/defconfig` expresses Qualcomm platform support as **modules**
(`=m`), and this port installs no module tree.  Every relevant `=m` therefore
becomes "no driver at all", silently.  See `docs/DT_PROVIDER_AUDIT.md`.

How it works, and why it is not a heuristic:

* the input is the **built** board DTB, so it describes exactly what the kernel was
  handed, including anything the board DTS or a DTBO changed;
* the driver side comes from `modules.builtin.modinfo`, which lists
  `alias=of:N*T*C<compatible>` for every **built-in** driver that registered a
  device table.  A compatible with no such alias has no built-in driver;
* so the only judgement in here is the allowlist below, which names the
  compatibles that *correctly* have no driver of their own: CPUs and caches,
  idle-state and OPP description nodes, interrupt controllers, the PSCI and timer
  nodes, and other nodes consumed by a parent driver rather than bound directly.

Anything that is neither matched nor allowlisted is printed as UNKNOWN and makes
the run exit non-zero, so this can be used as a gate rather than as a report
nobody reads.

    scripts/audit-dt-providers.py                       # human-readable
    scripts/audit-dt-providers.py --json                # machine-readable
    scripts/audit-dt-providers.py --dts /tmp/x.dts      # skip the dtc step

It never writes to a device and never touches the kernel tree.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]

# Compatibles that correctly have no driver of their own.  Each entry says why,
# because "it is in the allowlist" must not become an answer by itself.
ALLOWED = {
    # CPUs, caches and the PMU: described, not bound.
    "arm,cortex-a510": "CPU node", "arm,cortex-a715": "CPU node",
    "arm,cortex-a710": "CPU node", "arm,cortex-x3": "CPU node",
    "arm,cortex-a510-pmu": "PMU description", "arm,cortex-a715-pmu": "PMU description",
    "arm,cortex-a710-pmu": "PMU description", "arm,cortex-x3-pmu": "PMU description",
    "cache": "cache description",
    # Idle, OPP and clock description.
    "arm,idle-state": "idle-state description",
    "domain-idle-state": "idle-state description",
    "operating-points-v2": "OPP table description",
    "fixed-clock": "fixed-clock is registered by the clk core",
    "fixed-factor-clock": "fixed-clock is registered by the clk core",
    # Firmware and interrupt infrastructure the kernel brings up directly.
    "arm,psci-1.0": "PSCI is driven by the kernel itself",
    "arm,armv8-timer": "arch timer is driven by the kernel itself",
    "arm,armv7-timer-mem": "arch timer is driven by the kernel itself",
    "arm,gic-v3": "GIC is an irqchip, matched by its own infrastructure",
    "arm,gic-v3-its": "GIC ITS is an irqchip, matched by its own infrastructure",
    # Consumed by a parent device rather than bound on their own.
    "simple-battery": "consumed by the charger/fuel-gauge driver",
    "usb-c-connector": "consumed by the Type-C driver",
    "qcom,fastrpc-compute-cb": "child of the FastRPC node",
    "qcom,gpr": "child of the ADSP glink edge",
    "qcom,q6apm": "child of the GPR node",
    "qcom,q6apm-dais": "child of the GPR node",
    "qcom,q6apm-lpass-dais": "child of the GPR node",
    "qcom,q6prm": "child of the GPR node",
    "qcom,q6prm-lpass-clocks": "child of the GPR node",
}

# Compatibles that have no driver, where the symbol that would provide one is
# known.  These are *findings*, not failures: each is either out of scope for the
# stall investigation or tracked as its own candidate, and the note says which.
KNOWN_GAPS = {
    "qcom,adreno-gmu-740.1": (
        "no standalone GMU driver upstream; drm/msm drives it as a sub-device. "
        "docs/PROVIDER_FOLLOWUPS.md §2"),
    "qcom,sm8550-cpu-bwmon": (
        "CONFIG_QCOM_ICC_BWMON is unset; upstream defconfig has it =m. CPU<->DDR "
        "bandwidth monitor, on the CPU path"),
    "qcom,sm8550-llcc-bwmon": (
        "CONFIG_QCOM_ICC_BWMON is unset; upstream defconfig has it =m"),
    "qcom,sm8550-trng": (
        "CONFIG_CRYPTO_DEV_QCOM_RNG is unset; upstream defconfig has it =m"),
    "qcom,sm8550-qce": (
        "CONFIG_CRYPTO_DEV_QCE is unset; upstream defconfig has it =m"),
    "qcom,spmi-temp-alarm": (
        "CONFIG_QCOM_SPMI_TEMP_ALARM is unset; upstream defconfig has it =m"),
    "qcom,spmi-adc5-gen3": (
        "CONFIG_QCOM_SPMI_ADC5_GEN3 is unset (the plain ADC5 driver is =y but is a "
        "different generation); upstream defconfig has the gen3 one =m"),
    "qcom,rmtfs-mem": (
        "CONFIG_QCOM_RMTFS_MEM is unset; upstream defconfig has it =m. Modem RMTFS "
        "carve-out, and the modem is out of scope"),
    "qcom,rpmh-stats": "CONFIG_QCOM_RPMH_STATS unset; debug-only",
    "qcom,pcie-sm8550": (
        "PCIe is deliberately out of the A/B; excluded as a stall cause in test-181"),
    "qcom,bam-v1.7.4": "CONFIG_QCOM_BAM_DMA is unset; no in-tree consumer needs it yet",
    "qcom,wcn6855-bt": "Bluetooth bring-up is explicitly out of scope this round",
    "gpio-sbu-mux": "CONFIG_TYPEC_MUX_GPIO_SBU is unset; Type-C SBU mux",
    # Camera, audio and video: out of scope by instruction, listed so that they
    # are visibly accounted for rather than forgotten.
    "qcom,sm8550-camcc": "camera clock controller; camera is out of scope",
    "qcom,sm8550-camss": "camera subsystem; out of scope",
    "qcom,sm8550-cci": "camera control interface; out of scope",
    "hynix,hi1337-gts9u-rear": "camera sensor; out of scope",
    "hynix,hi1337-gts9u-front": "camera sensor; out of scope",
    "dongwoon,dw9808-vcm": "camera lens; out of scope",
    "qcom,sm8550-videocc": "video clock controller; out of scope",
    "qcom,sm8550-iris": "video codec; out of scope",
    "qcom,sm8550-lpass-wsa-macro": "audio codec; out of scope",
    "qcom,sm8550-lpass-rx-macro": "audio codec; out of scope",
    "qcom,sm8550-lpass-tx-macro": "audio codec; out of scope",
    "qcom,sm8550-lpass-va-macro": "audio codec; out of scope",
    "qcom,sm8550-lpass-lpi-pinctrl": "audio pinctrl; out of scope",
    "qcom,sm8550-sndcard": "sound card; out of scope",
    "cirrus,cs35l45": "speaker amplifier; out of scope",
    "wacom,w90xx": "pen digitizer; out of scope",
    "st,fts1ba90a": "touchscreen; out of scope",
    "parade,ps5169": "Type-C redriver; no mainline driver needed for the console",
    "siliconmitus,sm5440": "direct charger; out of scope",
    "siliconmitus,sm5714": "charger/fuel gauge; out of scope",
    "siliconmitus,sm5714-usbpd": "USB-PD; out of scope",
    "qcom,wcn6855-pmu": "Wi-Fi PMU; Wi-Fi bring-up is out of scope",
    "pci17cb,1103": "the QCA6490 Wi-Fi function on the PCIe bus; out of scope",
}


# Makefile conventions for mapping an object file back to the symbol that builds
# it.  `obj-y` means "always built", which the caller represents as an empty symbol.
SYMBOL_RE = re.compile(r"obj-\$\(CONFIG_([A-Z0-9_]+)\)\s*[:+]?=\s*(.*)")
OBJ_Y_RE = re.compile(r"obj-y\s*[:+]?=\s*(.*)")

# Directories that describe or instantiate hardware rather than drive it.
# `drivers/of/` is here because of `reserved_mem_matches[]` in of/platform.c: it
# lists "qcom,rmtfs-mem" so that `of_platform_default_populate_init()` creates a
# platform device for that carve-out.  It registers no driver and can never bind,
# and treating it as one hid a real gap on an earlier run.
NOT_A_DRIVER = ("arch/arm64/boot/dts/", "drivers/of/", "Documentation/",
                "tools/", "scripts/")

# Where a compatible can be declared.  `fs/` is here for `ramoops`
# (`fs/pstore/ram.c`); the DTS directories are deliberately absent.
SEARCH_DIRS = ("drivers", "sound", "net", "fs", "arch/arm64")

def decompile(dtb: pathlib.Path) -> str:
    return subprocess.run(
        ["dtc", "-I", "dtb", "-O", "dts", "-o", "-", str(dtb)],
        check=True, capture_output=True, text=True,
    ).stdout


def parse_dts(text: str):
    """Yield (path, compatibles, status) for every node that declares one."""
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    node_re = re.compile(r"^\s*([A-Za-z0-9_,.@+-]+)\s*\{")
    comp_re = re.compile(r'compatible\s*=\s*("(?:[^"]*)"(?:\s*,\s*"[^"]*")*)\s*;')
    status_re = re.compile(r'status\s*=\s*"([^"]*)"')
    stack: list[list] = []
    for line in text.splitlines():
        m = node_re.match(line)
        if m:
            stack.append([m.group(1), None, None])
            continue
        if line.strip() == "};":
            if stack:
                name, comps, status = stack.pop()
                if comps:
                    yield "/".join(n[0] for n in stack) + "/" + name, comps, status
            continue
        if stack:
            mc = comp_re.search(line)
            if mc:
                stack[-1][1] = re.findall(r'"([^"]*)"', mc.group(1))
            ms = status_re.search(line)
            if ms:
                stack[-1][2] = ms.group(1)


def config_symbol_for(tree: pathlib.Path, source: pathlib.Path):
    """The CONFIG symbol whose Makefile rule builds this object.

    Returns the symbol, the empty string for `obj-y` (always built), or None when
    no rule can be found - in which case the caller must not guess.

    Two kernel Makefile idioms have to be handled, and both were found the hard
    way by a node that is plainly driven reporting as unresolvable:

    * **composite objects.** `drivers/iommu/arm/arm-smmu/Makefile` has
      `obj-$(CONFIG_ARM_SMMU) += arm_smmu.o` and
      `arm_smmu-objs += arm-smmu.o`; `drivers/soc/qcom/Makefile` has
      `qcom_rpmh-y += rpmh-rsc.o`.  The symbol is on the composite's rule, not on
      the object's;
    * **objects built by an ancestor Makefile.** `drivers/gpu/drm/msm/disp/dpu1/`
      has no Makefile at all: `drivers/gpu/drm/msm/Makefile` lists
      `disp/dpu1/dpu_kms.o` inside its own `msm-y`.  So the search walks up, and at
      each level tries the path *relative to that directory* as well as the
      basename.
    """
    directory = tree / source.parent
    root = tree
    while True:
        makefile = directory / "Makefile"
        if makefile.is_file():
            lines = [line.split("#")[0] for line in
                     makefile.read_text(errors="replace").splitlines()]

            def owner(target: str):
                for code in lines:
                    if target not in code:
                        continue
                    m = SYMBOL_RE.search(code)
                    if m:
                        return m.group(1)
                    if OBJ_Y_RE.search(code):
                        return ""
                return None

            def composite(target: str):
                for code in lines:
                    m = re.match(
                        r"\s*([A-Za-z0-9_+-]+)-(?:y|objs|"
                        r"\(CONFIG_[A-Z0-9_]+\))\s*[:+]?=", code)
                    if m and target in code:
                        return owner(m.group(1) + ".o")
                return None

            targets = [source.with_suffix(".o").name]
            try:
                targets.append(str(source.relative_to(directory).with_suffix(".o")))
            except ValueError:
                pass
            for target in dict.fromkeys(targets):
                found = owner(target)
                if found is None:
                    found = composite(target)
                if found is not None:
                    return found
        if directory == root or directory.parent == directory:
            return None
        directory = directory.parent


def builtin_compatibles(modinfo: pathlib.Path) -> set:
    """Every compatible string a built-in driver declares, exactly.

    `of_match_node()` compares each of a node's compatible **strings** for exact
    equality against a driver's `of_device_id` entries, and that is what decides
    binding.  The alias is `of:N*T*C<c1>[C<c2>...][C*]`, so splitting on `C` and
    dropping the `*` recovers the individual strings.

    An earlier version also treated the `C*` form as a *string prefix* - reading it
    as "any compatible starting with this" rather than "this compatible, with
    further compatibles after it".  That made `qcom,sm8550-llcc-bwmon` match the
    LLCC controller's `qcom,sm8550-llcc` and hid a real gap: a false "bound", the
    worst direction for an audit to be wrong in.  There is no prefix logic here.
    """
    out = set()
    prefix = "of:N*T*"
    for line in subprocess.run(["strings", str(modinfo)],
                               check=True, capture_output=True, text=True
                               ).stdout.splitlines():
        if "alias=of:" not in line:
            continue
        alias = line.split("alias=", 1)[1]
        if not alias.startswith(prefix):
            continue
        rest = alias[len(prefix):]
        if not rest.startswith("C"):
            continue
        for part in rest[1:].split("C"):
            if part and part != "*":
                out.add(part)
    return out


def driver_sources(tree: pathlib.Path, compatible: str) -> list:
    """Files that declare this compatible, in either declaration form.

    The second pass, needed because modinfo can only see drivers that registered a
    `MODULE_DEVICE_TABLE(of, ...)`: `drivers/pci/controller/dwc/pcie-qcom.c` matches
    `"qcom,pcie-sm8550"` with `CONFIG_PCIE_QCOM=y` and registers none, so the first
    pass alone calls the node driverless.

    Both declaration forms count - `{ .compatible = "x" }` and the declarator
    macros `IRQCHIP_MATCH("x", ...)` / `TIMER_OF_DECLARE(name, "x", ...)` /
    `CLK_OF_DECLARE(...)` / `OF_DECLARE(...)`.  Missing the macros made
    `qcom,sm8550-pdc` look driverless while `drivers/irqchip/qcom-pdc.c` declares it
    and `CONFIG_QCOM_PDC=y`.
    """
    # Plain `(...)`, not `(?:...)`: grep -E is POSIX ERE and has no
    # non-capturing groups.  `(?:` makes grep warn "? at start of expression" and
    # match nothing, which silently turned every gap into "no driver source".
    pattern = (r'(\.compatible\s*=\s*|[A-Z_]*DECLARE\([^,]+,\s*|'
               r'[A-Z_]*MATCH\(\s*)"' + re.escape(compatible) + r'"')
    found = subprocess.run(
        ["grep", "-rlE", "--include=*.c", pattern, *SEARCH_DIRS],
        cwd=tree, capture_output=True, text=True,
    ).stdout.split()
    return [pathlib.Path(p) for p in found if not p.startswith(NOT_A_DRIVER)]


def read_config(path: pathlib.Path) -> dict:
    cfg = {}
    for line in path.read_text(errors="replace").splitlines():
        if line.startswith("CONFIG_") and "=" in line:
            key, _, value = line.partition("=")
            cfg[key[len("CONFIG_"):]] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            cfg[line[len("# CONFIG_"):-len(" is not set")]] = "n"
    return cfg


def classify(tree: pathlib.Path, cfg: dict, exact: set, compatibles) -> dict:
    """Can a built-in driver bind this node, and if not, why not?

    Pass 1 is exact membership in the compatibles built-in drivers declare.  Every
    compatible of the node is tried, not just the first: nodes carry generic
    fallbacks (`"qcom,sm8550-trng", "qcom,trng"`) and a driver matching the fallback
    binds just as well.  Anything pass 1 rejects goes to pass 2, the driver source.
    """
    if any(c in exact for c in compatibles):
        return {"kind": "bound", "sources": []}
    seen, unresolved = [], []
    for compatible in compatibles:
        for source in driver_sources(tree, compatible):
            symbol = config_symbol_for(tree, source)
            if symbol is None:
                unresolved.append((compatible, str(source)))
                continue
            value = "y" if symbol == "" else cfg.get(symbol, "MISSING")
            seen.append([str(source), symbol or "obj-y", value, compatible])
    seen = sorted({tuple(item) for item in seen})
    seen = [list(item) for item in seen]

    if any(item[2] == "y" for item in seen):
        # Built, but it registers no MODULE_DEVICE_TABLE(of, ...), so pass 1 could
        # not see it.  Not a gap.
        return {"kind": "built_no_alias", "sources": seen}
    if seen:
        # `=m` is not the same finding as `=n`: the symbol IS requested, and this
        # port installs no module tree, so `=m` yields no driver at all.
        module_only = all(item[2] == "m" for item in seen)
        return {
            "kind": "module_only" if module_only else "symbol_off",
            "detail": ("requested as =m only, and this port installs no module tree"
                       if module_only else "driver source exists but is not built"),
            "sources": seen,
        }
    if unresolved:
        return {"kind": "unknown_symbol",
                "detail": "no Makefile rule could be resolved for the driver source",
                "unresolved": unresolved}
    return {"kind": "no_driver",
            "detail": "no driver source declares any of its compatibles"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dtb", default="out/kernel-gts9wifi/sm8550-samsung-gts9wifi.dtb")
    parser.add_argument("--dts", help="use this DTS instead of decompiling --dtb")
    parser.add_argument("--modinfo", default=".work/build/linux-out/modules.builtin.modinfo")
    parser.add_argument("--tree", default=".work/build/linux-src-gts9wifi",
                        help="kernel source tree, for the second-source check")
    parser.add_argument("--config", default="out/kernel-gts9wifi/config")
    parser.add_argument("--no-second-source", action="store_true",
                        help="skip the driver-source check and trust modinfo alone")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    if args.no_second_source:
        args.tree = "/nonexistent"

    dts_path = ROOT / args.dts if args.dts else None
    dtb = ROOT / args.dtb
    if dts_path:
        text = dts_path.read_text()
    elif dtb.is_file():
        text = decompile(dtb)
    else:
        print(f"missing DTB: {dtb} (build the kernel first)", file=sys.stderr)
        return 2

    modinfo = ROOT / args.modinfo
    if not modinfo.is_file():
        print(f"missing modinfo: {modinfo} (build the kernel first)", file=sys.stderr)
        return 2
    tree = ROOT / args.tree
    config_path = ROOT / args.config
    cfg = read_config(config_path) if config_path.is_file() else {}
    if not tree.is_dir() or not cfg:
        print(f"need a kernel tree ({tree}) and a config ({config_path})",
              file=sys.stderr)
        return 2
    exact = builtin_compatibles(modinfo)

    matched, gaps, unknown, late = [], [], [], []
    for path, comps, status in parse_dts(text):
        if status in ("disabled", "fail", "reserved"):
            continue
        verdict = classify(tree, cfg, exact, comps)
        if verdict["kind"] in ("bound", "built_no_alias"):
            (late if verdict["kind"] == "built_no_alias" else matched).append(
                (path, comps[0], verdict))
            continue
        if comps[0] in ALLOWED:
            continue
        verdict["note"] = KNOWN_GAPS.get(comps[0], "")
        (gaps if comps[0] in KNOWN_GAPS else unknown).append(
            (path, comps[0], comps, verdict))

    if args.json:
        print(json.dumps({
            "matched": len(matched),
            "bound_without_alias": [{"path": p, "compatible": c, "second_source": v}
                                    for p, c, v in sorted(late)],
            "known_gaps": [{"path": p, "compatible": c, "note": KNOWN_GAPS[c],
                            "second_source": v} for p, c, _, v in sorted(gaps)],
            "unknown": [{"path": p, "compatible": c, "all": a, "second_source": v}
                        for p, c, a, v in sorted(unknown)],
        }, indent=2))
        return 1 if unknown else 0

    print(f"bound, alias in modinfo   : {len(matched)}")
    print(f"bound, no of: alias       : {len(late)}")
    print(f"real gaps (driver not =y) : {len(gaps)}")
    print(f"unknown                   : {len(unknown)}")
    print()
    for path, comp, verdict in sorted(late):
        print(f"  {path}\n      {comp}   (built; no MODULE_DEVICE_TABLE(of, ...))")
        for source, symbol, value, reached in verdict.get("sources", []):
            print(f"      {source}  {symbol} = {value}")
    if late:
        print()
    print("--- real gaps ---")
    for path, comp, _, verdict in sorted(gaps):
        print(f"  {path}\n      {comp}")
        print(f"      {KNOWN_GAPS[comp]}")
        print(f"      second source: {verdict['kind']} - {verdict['detail']}")
        for source, symbol, value, reached in verdict.get("sources", []):
            print(f"      {source}  {symbol} = {value}   (via {reached})")
    if unknown:
        print()
        print("--- UNKNOWN: neither bound nor classified ---")
        for path, comp, allc, verdict in sorted(unknown):
            print(f"  {path}\n      {comp}   (all: {', '.join(allc)})")
            print(f"      second source: {verdict['kind']} - {verdict['detail']}")
        print()
        print("Add each one to ALLOWED (with a reason) or to KNOWN_GAPS (with the")
        print("config symbol that would provide a driver), or build that driver.")
    return 1 if unknown else 0


if __name__ == "__main__":
    sys.exit(main())
