#!/usr/bin/env python3
"""Prepare only the bounded-CPU libssc wait fix; no tablet operations."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent


def files(root):
    paths = list(root.rglob('*'))
    if root.is_symlink() or any(p.is_symlink() for p in paths):
        raise ValueError('source links are forbidden')
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


def prepare(source, output, *, reference_only=False):
    source, output = Path(source).absolute(), Path(output).absolute()
    profile = json.loads((BASE / 'libssc-wait.json').read_text())
    if (output.exists() or output.is_symlink() or
            output.resolve().is_relative_to(source.resolve()) or
            source.resolve().is_relative_to(output.resolve())):
        raise ValueError('output must be absent and separate from source')
    if not source.is_dir() or files(source) != profile['base_files']:
        raise ValueError('pinned libssc base file set/hash mismatch')
    patches = profile['patches'][:1] if reference_only else profile['patches']
    for row in patches:
        path = BASE / row['path']
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise ValueError('wait patch input mismatch')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='libssc-wait-', dir=output.parent) as directory:
        stage = Path(directory) / 'libssc'
        shutil.copytree(source, stage)
        logs = []
        for row in patches:
            result = subprocess.run(['patch', '--batch', '--fuzz=0', '--forward',
                                     '--no-backup-if-mismatch', '-p1', '-i',
                                     str(BASE / row['path'])], cwd=stage,
                                    capture_output=True, text=True, check=True, timeout=15)
            if hashlib.sha256((stage / 'src/libssc-common.c').read_bytes()).hexdigest() != row['common_sha256']:
                raise ValueError('patched wait source mismatch')
            logs.append({'patch': row['path'], 'stdout': result.stdout, 'stderr': result.stderr})
        after = files(stage)
        changed = sorted(name for name in after.keys() | profile['base_files'].keys()
                         if after.get(name) != profile['base_files'].get(name))
        if changed != profile['changed_files']:
            raise ValueError('unexpected wait profile change')
        report = dict(profile=profile, reference_only=reference_only,
                      source_hashes=after, changed_files=changed, patch_logs=logs,
                      device_operations=False, hardware_verified=False)
        (stage / 'WAIT_SOURCE.json').write_text(json.dumps(report, indent=2) + '\n')
        stage.rename(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps({'changed_files': result['changed_files'], 'device_operations': False}))
