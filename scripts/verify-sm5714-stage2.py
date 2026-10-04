#!/usr/bin/env python3
"""Offline Stage2 resolved-config gate, including exact Test254 delta."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("container_gate", ROOT / "scripts/verify-container-config.py")
CONTAINER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONTAINER)
BASE = ROOT / "reference/boot-tests/test-254-debian-container-kernel/validation/candidate.config"
EXPECTED = {"CONFIG_TYPEC_SM5714": ["absent", "y"]}
REQUIRED = {"CONFIG_TYPEC", "CONFIG_TYPEC_TCPM", "CONFIG_TYPEC_SM5714",
            "CONFIG_I2C", "CONFIG_REGMAP_I2C", "CONFIG_USB_ROLE_SWITCH"}
FORBIDDEN = {"CONFIG_SM5440_ADC_TIMING_TEST", "CONFIG_CHARGER_SM5440_DIRECT", "CONFIG_TYPEC_DP_ALTMODE",
             "CONFIG_TYPEC_MUX_PS5169", "CONFIG_TYPEC_MUX_GPIO_SBU",
             "CONFIG_SM5440_ADC_CONDITION_TEST"}


def verify(text, baseline=None):
    result = CONTAINER.verify(text, baseline, EXPECTED if baseline is not None else None)
    config = CONTAINER.read_config(text)
    result["errors"] += [f"{s}: expected built-in" for s in sorted(REQUIRED)
                         if config.get(s) != "y"]
    result["errors"] += [f"{s}: outside Stage2" for s in sorted(FORBIDDEN)
                         if config.get(s) not in (None, "n")]
    result["valid"] = not result["errors"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify(args.config.read_text(), args.baseline.read_text() if args.baseline else None)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
