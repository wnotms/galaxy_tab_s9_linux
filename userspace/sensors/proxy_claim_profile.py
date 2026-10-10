#!/usr/bin/env python3
"""Prepare the GNOME early-claim repair over the exact Fedora-derived proxy."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('proxy_claim_source_files', BASE / 'libssc_wait_profile.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def prepare(source, output):
    source, output = Path(source).absolute(), Path(output).absolute()
    profile = json.loads((BASE / 'proxy-claim.json').read_text())
    if (output.exists() or output.is_symlink() or
            output.resolve().is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(output.resolve())):
        raise ValueError('output must be absent and separate from source')
    if not source.is_dir() or HELPER.files(source) != profile['base_files']:
        raise ValueError('pinned proxy base file set/hash mismatch')
    for name, sha in ((profile['patch_path'], profile['patch_sha256']),
                      (profile['reference_copy'], profile['reference_sha256'])):
        path = BASE / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != sha:
            raise ValueError('claim patch input mismatch')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='proxy-claim-', dir=output.parent) as directory:
        stage = Path(directory) / 'proxy'
        shutil.copytree(source, stage)
        run = subprocess.run(['patch', '--batch', '--fuzz=0', '--forward',
                              '--no-backup-if-mismatch', '-p1', '-i', str(BASE / profile['patch_path'])],
                             cwd=stage, capture_output=True, text=True, check=True, timeout=15)
        after = HELPER.files(stage)
        changed = sorted(name for name in after.keys() | profile['base_files'].keys()
                         if after.get(name) != profile['base_files'].get(name))
        if (changed != profile['changed_files'] or
                after['src/iio-sensor-proxy.c'] != profile['patched_file_sha256']):
            raise ValueError('unexpected claim repair source drift')
        report = dict(profile=profile, source_hashes=after, changed_files=changed,
                      patch_stdout=run.stdout, patch_stderr=run.stderr,
                      device_operations=False, hardware_verified=False)
        (stage / 'CLAIM_SOURCE.json').write_text(json.dumps(report, indent=2) + '\n')
        stage.rename(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps({'changed_files': result['changed_files'], 'device_operations': False}))
