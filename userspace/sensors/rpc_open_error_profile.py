#!/usr/bin/env python3
"""Prepare only the missing-file status correction over the frozen Test389 source."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('open_error_files', BASE / 'libssc_wait_profile.py')
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def prepare(source, output):
    source, output = Path(source).absolute(), Path(output).absolute()
    profile = json.loads((BASE / 'diagnostics/rpc-open-error.json').read_text())
    patch = BASE / 'diagnostics/rpc-open-error.patch'
    if (output.exists() or output.is_symlink() or
            output.resolve().is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(output.resolve())):
        raise ValueError('output must be absent and separate from source')
    if not source.is_dir() or HELPER.files(source) != profile['base_source_files']:
        raise ValueError('frozen RPC source file set/hash mismatch')
    if patch.is_symlink() or hashlib.sha256(patch.read_bytes()).hexdigest() != profile['patch_sha256']:
        raise ValueError('open error patch mismatch')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpc-open-error-', dir=output.parent) as directory:
        stage = Path(directory) / 'hexagonrpc'
        shutil.copytree(source, stage)
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '--forward',
                                 '--no-backup-if-mismatch', '-p1', '-i', str(patch)],
                                cwd=stage, capture_output=True, text=True, check=True, timeout=15)
        after = HELPER.files(stage)
        changed = sorted(n for n in after.keys() | profile['base_source_files'].keys()
                         if after.get(n) != profile['base_source_files'].get(n))
        if changed != profile['changed_files'] or any(after[n] != h for n, h in profile['patched_files'].items()):
            raise ValueError('unexpected open error source change')
        report = dict(profile=profile, source_hashes=after, changed_files=changed,
                      patch_stdout=result.stdout, patch_stderr=result.stderr,
                      device_operations=False, hardware_verified=False)
        (stage / 'OPEN_ERROR_SOURCE.json').write_text(json.dumps(report, indent=2) + '\n')
        stage.rename(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps({'changed_files': result['changed_files'], 'device_operations': False}))
