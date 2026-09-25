#!/usr/bin/env python3
"""Turn gts9-journal-survey's two files into a per-boot outcome table.

Why this exists: every stall assessment before round 17 rested on console
captures, and a host was watching for only ~22 cycles.  journald keeps 89 boots
on this device, and a per-boot outcome is derivable from it with no host at all:

  sd>0      systemd-shutdown ran -> the boot ended in an orderly shutdown
  sd=0      the journal stops without one -> a reset, from the watchdog, from a
            power cycle, or from a freeze

The distinction that matters is not sd alone - a harness that flashes or
power-cycles also produces sd=0 - but WHERE the journal stops.  A boot whose
journal stops immediately after `GTS9_DEBIAN_STAGE=multi-user`, at 6-7 s, is the
mid-run freeze: the machine had just finished booting and then stopped.  That is
the fingerprint this tool counts, and it is calibrated against two boots whose
freeze was independently captured on the host console (test-187's `1f85d97b` and
`7f02df57`).

Usage: analyse-survey.py [DIR]

Read-only; DIR defaults to this script's directory.
"""
from __future__ import annotations

import pathlib
import re
import sys

# A boot that never reached multi-user, or whose journal is too short to contain a
# boot at all, cannot say anything about the GPU chain or about a mid-run freeze.
MIN_LINES = 900

# The mid-run freeze band.  The two host-captured freezes stopped at 6.196 s and
# 6.476 s; the band is wide enough to hold them and narrow enough to exclude
# every other distinctive cluster in the survey.
BAND_LO, BAND_HI = 5.5, 8.0

TAIL_HEADER = re.compile(r"^== (-?\d+) ([0-9a-f]{8})$")


def read_survey(path: pathlib.Path) -> list[dict]:
    rows = []
    for line in path.read_text(errors="replace").splitlines():
        p = line.split()
        if len(p) < 9 or not p[0].lstrip("-").isdigit():
            continue
        rows.append(dict(idx=int(p[0]), bid=p[1], lines=int(p[2]), dpu=int(p[3]),
                         acd=int(p[4]), msm=int(p[5]), sd=int(p[6]),
                         multi=int(p[7]), last=float(p[8])))
    return sorted(rows, key=lambda r: r["idx"])


def read_tails(path: pathlib.Path) -> dict[str, list[str]]:
    tails: dict[str, list[str]] = {}
    cur = None
    for line in path.read_text(errors="replace").splitlines():
        m = TAIL_HEADER.match(line.strip())
        if m:
            cur = m.group(2)
            tails[cur] = []
        elif cur and line.strip():
            tails[cur].append(line.strip())
    return tails


def group(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Split into (valid, too-short, ...) and by GPU-chain era.

    The era discriminator is `Unable to send ACD state to AOSS`, which only the
    pre-fix kernel can print because it needs the GPU probe to reach ACD.  It is
    applied only to boots that reached multi-user: a boot that died at 4 s has
    acd=0 trivially and must not be counted as post-fix.
    """
    valid = [r for r in rows if r["multi"] > 0 and r["lines"] >= MIN_LINES]
    short = [r for r in rows if r not in valid]
    pre = [r for r in valid if r["acd"] > 0]
    post = [r for r in valid if r["acd"] == 0]
    return valid, pre, post, short


def main(argv: list[str]) -> int:
    base = pathlib.Path(argv[1]) if len(argv) > 1 else pathlib.Path(__file__).resolve().parent
    rows = read_survey(base / "journal-survey.txt")
    tails = read_tails(base / "journal-survey-tails.txt")
    if not rows:
        print("no survey rows found", file=sys.stderr)
        return 2

    valid, pre, post, short = group(rows)
    print(f"boots in the journal: {len(rows)}   reached multi-user: {len(valid)}   "
          f"too short to judge: {len(short)}")
    print(f"  pre-fix  (reached multi-user and printed the ACD error): {len(pre)}")
    print(f"  post-fix (reached multi-user and did not):               {len(post)}")
    print()

    print(f"{'group':<10} {'boots':>6} {'orderly':>8} {'no shutdown':>12} "
          f"{'freeze fingerprint':>19}")
    for name, grp in (("pre-fix", pre), ("post-fix", post)):
        clean = [r for r in grp if r["sd"] > 0]
        unclean = [r for r in grp if r["sd"] == 0]
        fp = [r for r in unclean if BAND_LO <= r["last"] <= BAND_HI]
        print(f"{name:<10} {len(grp):>6} {len(clean):>8} {len(unclean):>12} "
              f"{len(fp):>19}")

    print()
    print("freeze-fingerprint boots (journal stops "
          f"{BAND_LO}-{BAND_HI} s in, no shutdown):")
    for name, grp in (("pre-fix", pre), ("post-fix", post)):
        for r in grp:
            if r["sd"] == 0 and BAND_LO <= r["last"] <= BAND_HI:
                tail = tails.get(r["bid"], [])
                last = tail[-1][:78] if tail else "(no tail recorded)"
                print(f"  {name:<9} idx={r['idx']:>4} {r['bid']} last={r['last']:7.3f}s  {last}")

    print()
    print("every boot that printed a frame done timeout:")
    hits = [r for r in rows if r["dpu"] > 0]
    if not hits:
        print("  none")
    for r in hits:
        print(f"  idx={r['idx']} {r['bid']} dpu={r['dpu']} acd={r['acd']} "
              f"sd={r['sd']} last={r['last']:.3f}s")

    print()
    print("orderly-ended boots, to show the contrast:")
    for name, grp in (("pre-fix", pre), ("post-fix", post)):
        n = sum(1 for r in grp if r["sd"] > 0)
        print(f"  {name}: {n}/{len(grp)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
