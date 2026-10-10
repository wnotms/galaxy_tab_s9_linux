#!/usr/bin/env python3
"""Prepare a separately qualified RPC wire-format candidate; never touch the tablet."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

BASE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('ssc_wire_build', BASE / 'build.py')
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def files(root):
    if root.is_symlink() or any(p.is_symlink() for p in root.rglob('*')):
        raise ValueError('source links forbidden')
    return {str(p.relative_to(root)): sha(p) for p in sorted(root.rglob('*')) if p.is_file()}


def prepare(tree, output):
    tree, output = Path(tree).resolve(), Path(output).absolute()
    profile = json.loads((BASE / 'diagnostics/rpc-wire.json').read_text())
    patch = BASE / 'diagnostics/rpc-wire.patch'
    if (sha(BASE / 'sources.json') != profile['base_manifest_sha256'] or
            sha(patch) != profile['patch_sha256']):
        raise ValueError('profile input hash mismatch')
    report = build.verify_sources(tree)
    source = next(row for row in report['sources'] if row['name'] == 'hexagonrpc')
    before = source['patched_files']
    if before['hexagonrpcd/iobuffer.c'] != profile['base_file_sha256']:
        raise ValueError('base wire source mismatch')
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(tree):
        raise ValueError('output must be absent and outside base sources')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpc-wire-', dir=output.parent) as name:
        temporary = Path(name)
        root = temporary / 'hexagonrpc'
        shutil.copytree(tree / 'hexagonrpc', root)
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i', str(patch)],
                                cwd=root, capture_output=True, text=True, check=True)
        after = files(root)
        changes = sorted(n for n in before.keys() | after.keys() if before.get(n) != after.get(n))
        if (changes != profile['changed_files'] or
                after['hexagonrpcd/iobuffer.c'] != profile['patched_file_sha256']):
            raise ValueError('unexpected diagnostic source changes')
        identity = dict(base_prepared_sha256=sha(tree / 'PREPARED.json'),
                        base_source=source, profile=profile, patched_files=after,
                        patch_stdout=result.stdout, device_operations=False)
        (temporary / 'SOURCE.json').write_text(json.dumps(identity, indent=2) + '\n')
        temporary.rename(output)
    return identity


def prepare_with_stat(tree, output):
    """Keep the accepted stat observer; change only its real wire codec."""
    spec = importlib.util.spec_from_file_location('ssc_wire_stat', BASE / 'rpc_stat_profile.py')
    stat_profile = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(stat_profile)
    tree, output = Path(tree).resolve(), Path(output).absolute()
    if output.exists() or output.is_symlink() or output.resolve().is_relative_to(tree):
        raise ValueError('output must be absent and outside base sources')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpc-wire-stat-', dir=output.parent) as name:
        temporary = Path(name)
        wire = prepare(tree, temporary / 'wire')
        stat = stat_profile.prepare(tree, temporary / 'stat')
        root = temporary / 'stat/hexagonrpc'
        result = subprocess.run(['patch', '--batch', '--fuzz=0', '-p1', '-i',
                                 str(BASE / 'diagnostics/rpc-wire.patch')],
                                cwd=root, capture_output=True, text=True, check=True)
        after = files(root)
        changes = sorted(n for n in stat['patched_files'].keys() | after.keys()
                         if stat['patched_files'].get(n) != after.get(n))
        if (changes != wire['profile']['changed_files'] or
                after['hexagonrpcd/iobuffer.c'] != wire['profile']['patched_file_sha256'] or
                after['hexagonrpcd/apps_std.c'] != stat['profile']['patched_file_sha256']):
            raise ValueError('unexpected composed profile changes')
        identity = dict(wire, patched_files=after, composition=dict(stat_profile=stat['profile'],
                        changes_from_stat=changes), patch_stdout=result.stdout)
        (temporary / 'stat/SOURCE.json').write_text(json.dumps(identity, indent=2) + '\n')
        (temporary / 'stat').rename(output)
    return identity


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--with-stat', action='store_true', help='retain accepted stat metadata observer')
    args = parser.parse_args()
    identity = (prepare_with_stat if args.with_stat else prepare)(args.sources, args.output)
    print(json.dumps(dict(changed_files=identity['profile']['changed_files'],
                          output=str(args.output), device_operations=False), indent=2))


if __name__ == '__main__':
    main()
