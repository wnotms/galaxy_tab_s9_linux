#!/usr/bin/env python3
"""Prepare bounded return observation over verified Fedora wire/stat sources."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ssc_return_wire', BASE / 'rpc_wire_profile.py')
wire = importlib.util.module_from_spec(spec)
spec.loader.exec_module(wire)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(sources, output, profile_name='rpc-return'):
    sources = Path(sources).resolve()
    output = Path(output).absolute()
    if profile_name not in ('rpc-return', 'rpc-return-v2'):
        raise ValueError('unknown return observer profile')
    profile = json.loads((BASE / ('diagnostics/' + profile_name + '.json')).read_text())
    patch = BASE / 'diagnostics/rpc-return.patch'
    header = BASE / ('diagnostics/' + profile.get('header_file', 'rpc-return-trace.h'))
    if sha(patch) != profile['patch_sha256'] or sha(header) != profile['header_sha256']:
        raise ValueError('return observer input mismatch')
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(sources):
        raise ValueError('output must be absent and outside source tree')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpc-return-', dir=output.parent) as directory:
        temporary = Path(directory)
        identity = wire.prepare_with_stat(sources, temporary / 'composed')
        root = temporary / 'composed/hexagonrpc'
        if sha(root / 'hexagonrpcd/listener.c') != profile['base_file_sha256']:
            raise ValueError('listener base mismatch')
        subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)],
                       cwd=root, check=True, capture_output=True)
        shutil.copyfile(header, root / 'hexagonrpcd/rpc-return-trace.h')
        after = wire.files(root)
        before = identity['patched_files']
        changed = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
        if changed != profile['changed_files'] or sha(root / 'hexagonrpcd/listener.c') != profile['patched_file_sha256']:
            raise ValueError('return observer source drift')
        identity['composition']['return_profile'] = profile
        identity['composition']['changes_from_wire_stat'] = changed
        identity['patched_files'] = after
        (temporary / 'composed/SOURCE.json').write_text(json.dumps(identity, indent=2) + '\n')
        (temporary / 'composed').rename(output)
    return identity


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--profile', choices=('rpc-return', 'rpc-return-v2'), default='rpc-return')
    args = parser.parse_args()
    result = prepare(args.sources, args.output, args.profile)
    print(json.dumps({'changed_files': result['composition']['changes_from_wire_stat'],
                      'device_operations': False}, indent=2))
