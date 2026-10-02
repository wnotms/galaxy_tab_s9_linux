#!/usr/bin/env python3
"""Offline artifact/config/DT/protected-source audit; never contacts a device."""
import argparse
import difflib
import hashlib
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT / "reference/boot-tests/test-256-x710-charging-offline"
BASE_DIR = ROOT / "reference/boot-tests/test-255-sm5714-fixed-pd/validation"
SPEC = importlib.util.spec_from_file_location("config_gate", ROOT / "scripts/verify-container-config.py")
CONFIG = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CONFIG)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dt_properties(path):
    properties = {}
    def visit(node):
        for prop in subprocess.check_output(["fdtget", "-p", str(path), node],
                                            text=True).splitlines():
            value = subprocess.check_output(["fdtget", "-t", "bx", str(path), node, prop],
                                             text=True).strip()
            properties[node + ":" + prop] = value
        for child in subprocess.check_output(["fdtget", "-l", str(path), node],
                                             text=True).splitlines():
            visit(node.rstrip("/") + "/" + child)
    visit("/")
    return properties


def audit(out, tree, build, revision, profile):
    errors = []
    baseline = json.loads((RECORD / "baseline.json").read_text())
    baseline_cfg = (BASE_DIR / "candidate.config").read_text()
    cfg = (out / "config").read_text()
    before, after = CONFIG.read_config(baseline_cfg), CONFIG.read_config(cfg)
    delta = {key: [before.get(key, "absent"), after.get(key, "absent")]
             for key in sorted(before.keys() | after.keys())
             if before.get(key, "absent") != after.get(key, "absent")}
    # New inactive Kconfig declarations are an explained absent->n difference.
    expected = {}
    for key in ("CONFIG_CHARGER_SM5440_DIRECT", "CONFIG_X710_CHARGING_POLICY"):
        if key in after and key not in before:
            expected[key] = ["absent", "n"]
    if profile in ("sm5440-passive", "sm5440-policy-offline"):
        expected["CONFIG_CHARGER_SM5440_DIRECT"] = [before.get("CONFIG_CHARGER_SM5440_DIRECT", "absent"), "y"]
    if profile == "sm5440-policy-offline":
        expected["CONFIG_X710_CHARGING_POLICY"] = [before.get("CONFIG_X710_CHARGING_POLICY", "absent"), "y"]
    if delta != expected:
        errors.append("resolved configuration has an unexpected or missing change")
    container = CONFIG.verify(cfg)
    errors += container["errors"]
    protected = json.loads((ROOT / baseline["protected_manifest"]).read_text())["files"]
    changed = {name: sha(ROOT / name) for name, data in protected.items()
               if sha(ROOT / name) != data["sha256"]}
    if changed:
        errors.append("protected baseline source changed")
    retained = {name: sha(ROOT / "out/kernel-sm5714-stage2" / name)
                for name in baseline["artifact_sha256"]}
    if retained != baseline["artifact_sha256"]:
        errors.append("frozen Stage2 artifact changed")
    dtb = out / "sm8550-samsung-gts9wifi.dtb"
    old_dtb = ROOT / "out/kernel-sm5714-stage2/sm8550-samsung-gts9wifi.dtb"
    old, new = ({}, {}) if sha(old_dtb) == sha(dtb) else (dt_properties(old_dtb), dt_properties(dtb))
    dt_delta = {key: [old.get(key), new.get(key)] for key in sorted(old.keys() | new.keys())
                if old.get(key) != new.get(key)}
    if profile in ("sm5440-passive", "sm5440-policy-offline"):
        status_keys = [k for k, value in old.items() if k.endswith("/charger@63:status")]
        allowed_dt = {k: ["64 69 73 61 62 6c 65 64 0", "6f 6b 61 79 0"] for k in status_keys}
        if len(status_keys) != 1 or dt_delta != allowed_dt:
            errors.append("passive DT changes more than the pump status property")
    elif dt_delta:
        errors.append("primary fixed-PD DT changed")
    # Check compiled overlay bytes against the committed revision, not current
    # worktree bytes which may already be undergoing the next phase.
    compiled = {}
    for name in ("sm5714-battery.c", "sm5714-stage2.h", "sm5714_usbpd.c",
                 "sm5714-pd-policy.h", "sm5440-direct.c", "sm5440-hw.h",
                 "x710-charging-policy.c", "x710-charging-policy.h",
                 "x710-pd-session.c", "x710-pd-session.h"):
        show = subprocess.run(["git", "-C", str(ROOT), "show", f"{revision}:kernel/drivers/{name}"],
                              capture_output=True)
        if show.returncode:
            continue
        subsystem = "usb/typec/tcpm" if name in ("sm5714_usbpd.c", "sm5714-pd-policy.h") else "power/supply"
        path = tree / "drivers" / subsystem / name
        compiled[name] = sha(path) == hashlib.sha256(show.stdout).hexdigest()
    if not all(compiled.values()):
        errors.append("compiled driver does not match recorded source revision")
    embedded = subprocess.check_output([str(tree / "scripts/extract-ikconfig"), str(out / "Image.gz")])
    if embedded != (out / "config").read_bytes():
        errors.append("embedded config is not the resolved artifact config")
    release = (out / "kernel.release").read_text().strip()
    module_dir = out / "modules-root/lib/modules" / release
    modules = {str(p.relative_to(module_dir)): sha(p) for p in sorted(module_dir.rglob("*")) if p.is_file()}
    if len(modules) != 181:
        errors.append("expected 181 paired regular module-directory files")
    subprocess.run(["llvm-objcopy", "--dump-section", f".notes={out / 'kernel-notes.bin'}",
                    str(build / "vmlinux"), "/dev/null"], check=True)
    archive = out / "modules-x710.tar.gz"
    def normalized(info):
        if info.issym() or info.islnk():
            return None  # no build/source host-path symlinks in an install archive
        info.uid = info.gid = info.mtime = 0
        info.uname = info.gname = "root"
        return info
    with archive.open("wb") as raw:
        with gzip.GzipFile(filename="", fileobj=raw, mode="wb", mtime=0, compresslevel=3) as gz:
            with tarfile.open(fileobj=gz, mode="w|") as tar:
                tar.add(module_dir, arcname=release, filter=normalized)
    with tarfile.open(archive) as tar:
        archived = {str(Path(p.name).relative_to(release)): hashlib.sha256(tar.extractfile(p).read()).hexdigest()
                    for p in tar.getmembers() if p.isfile()}
    if archived != modules:
        errors.append("module archive does not contain the exact paired regular file set")
    files = [out / "Image.gz", dtb, out / "config", out / "kernel-notes.bin", archive]
    return dict(valid=not errors, errors=errors, revision=revision, profile=profile,
                config_delta=delta, expected_config_delta=expected,
                unexpected_config_delta={k: v for k, v in delta.items() if expected.get(k) != v},
                dt_delta=dt_delta, container_gate=container,
                protected_file_count=len(protected), protected_changes=changed,
                frozen_artifacts_intact=retained == baseline["artifact_sha256"],
                compiled_source_matches=compiled, modules=modules,
                artifacts={p.name: {"path": str(p), "sha256": sha(p), "bytes": p.stat().st_size} for p in files},
                device_commands_executed=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("out", "tree", "build", "report"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--profile", choices=("fixed", "sm5440-passive", "sm5440-policy-offline"), default="fixed")
    args = parser.parse_args()
    result = audit(args.out, args.tree, args.build, args.revision, args.profile)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, indent=2) + "\n")
    args.report.with_suffix(".config.diff").write_text("".join(difflib.unified_diff(
        (BASE_DIR / "candidate.config").read_text().splitlines(True),
        (args.out / "config").read_text().splitlines(True), fromfile="Test255", tofile=args.profile)))
    print(json.dumps({k: v for k, v in result.items() if k not in ("modules", "container_gate", "artifacts")}, indent=2))
    return 0 if result["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
