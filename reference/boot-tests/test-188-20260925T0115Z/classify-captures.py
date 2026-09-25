#!/usr/bin/env python3
"""Re-classify test-188's shutdown captures from the raw files.

Why this exists next to shutdown-series.sh.  The runner decides a round from one
console marker, `systemd-shutdown`, and that marker is *not reliable on this
port*: the USB gadget disappears at exactly the moment systemd-shutdown starts
printing.  Round 1 of test-188 caught 3 of its lines; round 2 caught none and was
recorded `unknown-capture-empty`, yet round 2's shutdown had demonstrably
succeeded - its capture contains

    Reached target reboot.target - System Reboot.

and the *next* boot's evidence collector reported `end=clean-shutdown` for it.

Two better signals are available, and this script uses both:

  resets          read failures that are not the watcher's own window closing.
                  More than one per session means the tablet rebooted unasked -
                  which is how round 1 of the test-187 series turns out to have
                  held an extra reset that its round record never captured.

  prev_boot_end   the device's own verdict, from its archive of the previous
                  boot's full journal.  Authoritative, and it appears inside the
                  capture because the collector runs ~6.5 s into the next boot.
                  It lags one round: round N's capture carries the verdict for
                  round N-1's boot.
  reboot.target   systemd prints this immediately before handing over to
                  systemd-shutdown, so it is emitted EARLIER than the
                  systemd-shutdown lines and survives the gadget dropping more
                  often.  Its absence on a shutdown that started is the failure.

Usage:
    classify-captures.py [DIR] [--json]
    classify-captures.py --file SOMECAPTURE.txt

DIR defaults to this script's directory.  --file classifies one capture, which is
how the pre-fix failure (test-184's console-A-5-watch.txt) is checked against the
threshold this tool calibrates from the clean series.  Read-only: nothing written.
"""
from __future__ import annotations

import datetime
import json
import pathlib
import re
import sys

RECV = re.compile(
    r"^(?P<t>\S+Z) (?P<kind>RECV|read failed|port closed|port open|PRESENCE|watch start|watch done)(?P<rest>.*)$"
)
TS = "%Y-%m-%dT%H:%M:%S.%fZ"

# The device's own per-boot verdict, printed by the collector on the NEXT boot.
PREV_END = re.compile(r"gts9-prev-boot-evidence:.*\bend=(?P<end>[a-z-]+)")
# test-188 keeps the watcher's own output (w19) and test-187 kept the copy of the
# same capture (console.log); both are accepted so the two series can be compared.
ROUND_FILE = re.compile(r"^shutdown-(?P<n>\d+)-(?:w19\.txt|console\.log)$")

# Counted, but not by itself a stall: `enc35 frame done timeout` is the first link
# of a chain the project already recorded (docs/DPU_TRACE.md, docs/WATCHDOG_X710.md,
# gts9-power-key.c), and it is the last line boot 7f02df57 printed before it was
# reset unasked.  Counting it per capture is what makes that visible.
DPU_FRAME_TIMEOUT = r"dpu_encoder_frame_done_timeout|frame done timeout"

# Calibrated, not guessed.  Longest open-port silence is 0.597-1.085 s across the
# 15 clean rounds measured in test-187 and test-188, and 28.903 s in the test-184
# A-5 failure.  5 s sits far outside the former and far inside the latter, so a
# shutdown that shows 5 s of silence with the port still open is the failure
# regardless of whether the completion marker happened to be captured.
STALL_SILENCE_S = 5.0

BANNERS = {
    "panic": r"Kernel panic",
    "softlockup": r"BUG: soft lockup|watchdog: BUG",
    "hardlockup": r"BUG: hard LOCKUP|Hard LOCKUP",
    "hungtask": r"hung_task|blocked for more than",
    "rcu": r"rcu.*detected stall|rcu.*starved",
}


def parse(path: pathlib.Path) -> list[tuple[str, str, str]]:
    """Return (timestamp, kind, payload) for every line of a watch capture."""
    out = []
    for line in path.read_text(errors="replace").splitlines():
        m = RECV.match(line)
        if m:
            out.append((m.group("t"), m.group("kind"), m.group("rest").strip()))
    return out


def seconds(a: str, b: str) -> float:
    fmt = TS
    return (
        datetime.datetime.strptime(b, fmt) - datetime.datetime.strptime(a, fmt)
    ).total_seconds()


def classify(events: list[tuple[str, str, str]]) -> dict:
    recv = [e for e in events if e[1] == "RECV"]
    text = "\n".join(e[2] for e in recv)

    result: dict = {"console_lines": len(recv)}
    for key, pattern in BANNERS.items():
        result[f"{key}_lines"] = len(re.findall(pattern, text))

    # A reset is a read failure that is not the watcher closing its own window.
    # More than one per session means the tablet rebooted without being asked:
    # exactly what round 1 of the test-187 series did after this boot's
    # `enc35 frame done timeout`.  See docs/STALL_FAILURE_SHAPE.md.
    resets = [t for t, k, payload in events
              if k == "read failed" and "watch end" not in payload]
    result["resets"] = len(resets)
    result["reset_times"] = resets
    result["unattended_resets"] = max(0, len(resets) - 1)

    result["dpu_frame_timeout"] = len(re.findall(DPU_FRAME_TIMEOUT, text))
    result["shutdown_started"] = bool(re.search(r"\bStopping\s", text))
    result["reboot_target_seen"] = text.count("reboot.target")
    result["systemd_shutdown_seen"] = text.count("systemd-shutdown")
    result["reached_target_lines"] = text.count("Reached target")

    m = PREV_END.search(text)
    result["prev_boot_end"] = m.group("end") if m else None

    # The longest silence, which is the failure's observable shape.
    gap, where = 0.0, None
    for a, b in zip(recv, recv[1:]):
        try:
            d = seconds(a[0], b[0])
        except ValueError:
            continue
        if d > gap:
            gap, where = d, (a[0], b[0])
    result["longest_gap_s"] = round(gap, 3)
    result["longest_gap_between"] = where

    # The gap that matters is silence while the port was still OPEN.  A healthy
    # reboot looks almost identical to a failure if only the longest gap is
    # measured, because the port is closed for ~20 s across the re-enumeration:
    #
    #   clean    reboot.target -> port closed -> (20 s, port closed) -> new boot
    #   failure  last stop line -> (29 s, PORT STILL OPEN) -> read failed -> reset
    #
    # So a long gap is only evidence of a stall when no read error falls inside
    # it.  This is the discriminator; longest_gap_s alone cannot tell them apart.
    # Walk the whole event stream, not just the RECV lines.  Silence is only
    # "while the port was open" if it ends at the next event, because the closing
    # event is itself the end of the silent interval: the port was open for the
    # WHOLE gap and closed at the end of it.  Comparing consecutive RECV lines
    # alone misses that - in the pre-fix failure the 28.9 s ends at `read failed`,
    # so a RECV-to-RECV scan sees only the 49.5 s that spans the reset and
    # discards it as "port was closed".
    open_gap, open_where, last = 0.0, None, None
    for t, k, _ in events:
        if k == "RECV":
            if last is not None:
                d = seconds(last, t)
                if d > open_gap:
                    open_gap, open_where = d, (last, t)
            last = t
        elif k == "port closed" and "watch end" in _:
            # The watcher's own window closed.  Silence here is the watcher
            # stopping, not the machine, so it is NOT counted.  Limitation: a
            # stall that begins after the last line and outlives the window is
            # invisible to this measure, which is why the runner also checks that
            # boot_id changed.
            last = None
        elif k in ("read failed", "port closed"):
            # The port closed on its own - the tablet reset underneath us - so the
            # preceding silence happened while the port was still open.  This is
            # the stall candidate.
            if last is not None:
                d = seconds(last, t)
                if d > open_gap:
                    open_gap, open_where = d, (last, t)
            last = None
        elif k == "watch done":
            last = None
        elif k == "port open":
            last = None
    result["longest_open_silence_s"] = round(open_gap, 3)
    result["longest_open_silence_between"] = open_where

    bad = [k for k in BANNERS if result[f"{k}_lines"]]
    if bad:
        result["verdict"] = "PANIC-OR-LOCKUP"
    elif result["prev_boot_end"] == "clean-shutdown" or result["reboot_target_seen"]:
        # Either the device's own journal says the shutdown completed, or the
        # console caught systemd reaching the reboot target.  Both mean the
        # shutdown finished; only the second is an observation of this round.
        result["verdict"] = "clean"
    elif result["prev_boot_end"] in ("hard-reset-or-incomplete", "panic"):
        result["verdict"] = "STALL"
    elif (result["shutdown_started"] and not result["reboot_target_seen"]
          and result["longest_open_silence_s"] >= STALL_SILENCE_S):
        # A shutdown began, went quiet for far longer than any healthy round does
        # while the port was still open, and never reached the reboot target.
        result["verdict"] = "STALL"
    elif result["shutdown_started"]:
        # The shutdown began, the port dropped promptly, and there was no stall
        # silence - but the marker that proves completion was not captured.  This
        # is NOT "clean"; it is "no stall signature".  Round 6 of test-188 is the
        # case: the gadget dropped 1.24 s after the first stop line, before
        # systemd printed reboot.target.
        result["verdict"] = "no-stall-signature"
    else:
        result["verdict"] = "inconclusive"
    return result


def main(argv: list[str]) -> int:
    if "--file" in argv:
        path = pathlib.Path(argv[argv.index("--file") + 1])
        print(json.dumps(classify(parse(path)), indent=2, sort_keys=True))
        return 0

    args = [a for a in argv[1:] if not a.startswith("--")]
    base = pathlib.Path(args[0]) if args else pathlib.Path(__file__).resolve().parent
    as_json = "--json" in argv

    # One file per round.  `-w19.txt` is the watcher's stdout for that single run;
    # `-console.log` is its -Out copy, which APPENDS, so round N's copy can hold
    # several sessions from different series.  Prefer the former.
    rounds = {}
    for pattern in ("shutdown-*-w19.txt", "shutdown-*-console.log"):
        for path in sorted(base.glob(pattern)):
            m = ROUND_FILE.match(path.name)
            if m and int(m.group("n")) not in rounds:
                rounds[int(m.group("n"))] = classify(parse(path))

    if as_json:
        print(json.dumps(rounds, indent=2, sort_keys=True))
        return 0

    print(f"{'round':>5}  {'verdict':<34} {'prev_boot_end':<26} "
          f"{'reboot.target':>13} {'sysd-shutdown':>13} {'gap_s':>8} "
          f"{'open_silence_s':>15} {'dpu_to':>7}")
    for n in sorted(rounds):
        r = rounds[n]
        flag = " *** UNATTENDED RESET" if r["unattended_resets"] else ""
        print(f"{n:>5}  {r['verdict']:<34} {str(r['prev_boot_end']):<26} "
              f"{r['reboot_target_seen']:>13} {r['systemd_shutdown_seen']:>13} "
              f"{r['longest_gap_s']:>8.3f} {r['longest_open_silence_s']:>15.3f} "
              f"{r['dpu_frame_timeout']:>7}{flag}")
    total = len(rounds)
    stalls = [n for n, r in rounds.items() if r["verdict"] == "STALL"]
    clean = [n for n, r in rounds.items() if r["verdict"] == "clean"]
    nostall = [n for n, r in rounds.items() if r["verdict"] == "no-stall-signature"]
    un = [n for n, r in rounds.items() if r["unattended_resets"]]
    print(f"\n{total} round(s): {len(clean)} clean, {len(stalls)} STALL"
          + (f" {stalls}" if stalls else ""))
    if nostall:
        print(f"{len(nostall)} round(s) show no stall signature but no completion "
              f"marker either (the gadget dropped first): {nostall}")
    if un:
        print(f"{len(un)} round(s) contain an UNATTENDED reset (the tablet rebooted "
              f"without being asked): {un}")
    return 1 if stalls else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
