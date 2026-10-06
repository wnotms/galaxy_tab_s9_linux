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


def verify(text, baseline=None, profile="sm5440-passive"):
    before = STAGE2.CONTAINER.read_config(baseline or BASE.read_text())
    after = STAGE2.CONTAINER.read_config(text)
    expected = {"CONFIG_CHARGER_SM5440_DIRECT": [before.get("CONFIG_CHARGER_SM5440_DIRECT", "absent"), "y"]}
    if profile not in ("sm5440-passive", "sm5440-policy-offline", "sm5440-native-control", "sm5440-adc-condition", "sm5440-adc-timing", "sm5440-adc-raw", "sm5440-adc-oneshot", "sm5440-fedora"):
        return {"valid": False, "errors": ["unknown charging profile"]}
    fedora = "CONFIG_CHARGER_SM5440_FEDORA"
    if fedora in after and fedora not in before:
        expected[fedora] = ["absent", "n"]
    if profile == "sm5440-fedora":
        expected[fedora] = [before.get(fedora, "absent"), "y"]
        expected["CONFIG_CHARGER_SM5440_DIRECT"] = [
            before.get("CONFIG_CHARGER_SM5440_DIRECT", "absent"), "n"]
    policy = "CONFIG_X710_CHARGING_POLICY"
    if policy in after and policy not in before:
        expected[policy] = ["absent", "n"]
    if profile in ("sm5440-policy-offline", "sm5440-native-control"):
        expected[policy] = [before.get(policy, "absent"), "y"]
    native = "CONFIG_X710_NATIVE_CONTROL"
    if native in after and native not in before:
        expected[native] = ["absent", "n"]
    if profile == "sm5440-native-control":
        expected[native] = [before.get(native, "absent"), "y"]
    condition = "CONFIG_SM5440_ADC_CONDITION_TEST"
    if condition in after and condition not in before:
        expected[condition] = ["absent", "n"]
    if profile == "sm5440-adc-condition":
        expected[condition] = [before.get(condition, "absent"), "y"]
    timing = "CONFIG_SM5440_ADC_TIMING_TEST"
    if timing in after and timing not in before:
        expected[timing] = ["absent", "n"]
    if profile == "sm5440-adc-timing":
        expected[timing] = [before.get(timing, "absent"), "y"]
    raw = "CONFIG_SM5440_ADC_RAW_TEST"
    if raw in after and raw not in before:
        expected[raw] = ["absent", "n"]
    if profile == "sm5440-adc-raw":
        expected[raw] = [before.get(raw, "absent"), "y"]
    oneshot = "CONFIG_SM5440_ADC_ONESHOT_TEST"
    if oneshot in after and oneshot not in before:
        expected[oneshot] = ["absent", "n"]
    if profile == "sm5440-adc-oneshot":
        expected[oneshot] = [before.get(oneshot, "absent"), "y"]
    result = STAGE2.CONTAINER.verify(text, baseline or BASE.read_text(), expected)
    result["errors"] += [f"{name}: expected built-in" for name in sorted(STAGE2.REQUIRED)
                          if after.get(name) != "y"]
    allowed = {"CONFIG_CHARGER_SM5440_DIRECT"}
    if profile == "sm5440-adc-condition":
        allowed.add(condition)
    if profile == "sm5440-adc-timing":
        allowed.add(timing)
    if profile == "sm5440-adc-raw":
        allowed.add(raw)
    if profile == "sm5440-adc-oneshot":
        allowed.add(oneshot)
    if profile == "sm5440-fedora":
        allowed.add(fedora)
    result["errors"] += [f"{name}: forbidden advanced feature" for name in sorted(
        STAGE2.FORBIDDEN - allowed) if after.get(name) in ("y", "m")]
    if profile != "sm5440-native-control" and after.get(native) in ("y", "m"):
        result["errors"].append("native control requires its isolated profile")
    if profile != "sm5440-fedora" and after.get(fedora) in ("y", "m"):
        result["errors"].append("Fedora source port requires its isolated profile")
    result["valid"] = not result["errors"]
    result["profile"] = profile
    result["pump_activation_available"] = profile == "sm5440-fedora"
    if profile == "sm5440-fedora":
        result["direct_charge_default"] = False
        result["requires_registered_boot_opt_in"] = True
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("config", type=Path)
    parser.add_argument("--profile", choices=("sm5440-passive", "sm5440-policy-offline", "sm5440-native-control", "sm5440-adc-condition", "sm5440-adc-timing", "sm5440-adc-raw", "sm5440-adc-oneshot", "sm5440-fedora"), default="sm5440-passive")
    args = parser.parse_args()
    result = verify(args.config.read_text(), profile=args.profile)
    print(json.dumps(result, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
