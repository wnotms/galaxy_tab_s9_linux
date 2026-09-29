#!/usr/bin/env python3
"""Strict resolved-config gate for isolated passive charging candidates."""
import argparse
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage2", ROOT / "scripts/verify-sm5714-stage2.py")
STAGE2 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STAGE2)
BASE = ROOT / "reference/boot-tests/test-255-sm5714-fixed-pd/validation/candidate.config"


def verify(text, baseline=None):
    before = STAGE2.CONTAINER.read_config(baseline or BASE.read_text())
    after = STAGE2.CONTAINER.read_config(text)
    expected = {"CONFIG_CHARGER_SM5440_DIRECT": [before.get("CONFIG_CHARGER_SM5440_DIRECT", "absent"), "y"]}
    result = STAGE2.CONTAINER.verify(text, baseline or BASE.read_text(), expected)
    result["errors"] += [f"{name}: expected built-in" for name in sorted(STAGE2.REQUIRED)
                          if after.get(name) != "y"]
    result["errors"] += [f"{name}: forbidden advanced feature" for name in sorted(
        STAGE2.FORBIDDEN - {"CONFIG_CHARGER_SM5440_DIRECT"}) if after.get(name) in ("y", "m")]
    result["valid"] = not result["errors"]
    result["profile"] = "sm5440-passive"
    result["pump_activation_available"] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    result = verify(args.config.read_text())
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
