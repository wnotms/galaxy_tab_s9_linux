#!/usr/bin/env python3
"""Fail closed if a Stage 1 build changes the accepted Test249 profile beyond
the SM5714 supply and its mandatory PMK8550 pack-thermistor ADC provider.

This verifies host build artifacts only. It does not query or modify the tablet.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

EXPECTED_DELTA = {
    "CONFIG_BATTERY_SM5714": (None, "y"),
    "CONFIG_QCOM_SPMI_ADC5_GEN3": ("n", "y"),
}
DTB = "sm8550-samsung-gts9wifi.dtb"


def parse_config(path):
    result = {}
    for line in path.read_text().splitlines():
        if line.startswith("CONFIG_"):
            name, value = line.split("=", 1)
            result[name] = value
        elif line.startswith("# CONFIG_") and line.endswith(" is not set"):
            result[line[2:-11]] = "n"
    return result


def config_delta(baseline, candidate):
    before, after = parse_config(baseline), parse_config(candidate)
    return {key: (before.get(key), after.get(key))
            for key in sorted(before.keys() | after.keys())
            if before.get(key) != after.get(key)}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(baseline, candidate, vmlinux=None, module_root=None):
    delta = config_delta(baseline / "config", candidate / "config")
    cfg = parse_config(candidate / "config")
    result = {
        "config_delta": delta,
        "expected_config_delta": EXPECTED_DELTA,
        "dcc_absent": cfg.get("CONFIG_HVC_DCC") == "n",
        "dtb_sha256": sha256(candidate / DTB),
        "baseline_dtb_sha256": sha256(baseline / DTB),
    }
    result["dtb_unchanged"] = result["dtb_sha256"] == result["baseline_dtb_sha256"]
    checks = [delta == EXPECTED_DELTA, result["dcc_absent"], result["dtb_unchanged"]]
    if vmlinux is not None:
        symbols = subprocess.run(["nm", str(vmlinux)], check=True,
                                 capture_output=True, text=True).stdout
        result["sm5714_built_in"] = any(line.endswith(" sm5714_probe")
                                                for line in symbols.splitlines())
        checks.append(result["sm5714_built_in"])
    if module_root is not None:
        trees = list(module_root.glob("lib/modules/*"))
        result["module_trees"] = len(trees)
        result["modules_dep_present"] = len(trees) == 1 and (trees[0] / "modules.dep").is_file()
        checks.append(result["modules_dep_present"])
    result["valid"] = all(checks)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path("out/kernel-no-dcc-production"))
    parser.add_argument("--candidate", type=Path, default=Path("out/kernel-gts9wifi"))
    parser.add_argument("--vmlinux", type=Path)
    parser.add_argument("--module-root", type=Path)
    args = parser.parse_args()
    try:
        result = verify(args.baseline, args.candidate, args.vmlinux, args.module_root)
    except (OSError, subprocess.CalledProcessError) as error:
        print(f"cannot verify Stage 1 build: {error}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    sys.exit(main())
