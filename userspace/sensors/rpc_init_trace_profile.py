#!/usr/bin/env python3
"""Prepare bounded init observation over the frozen Fedora-derived daemon."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile

BASE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location('init_profile_files', BASE/'libssc_wait_profile.py')
HELPER = importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(HELPER)


def prepare(source, output):
    source, output = Path(source).absolute(), Path(output).absolute()
    profile = json.loads((BASE/'diagnostics/rpc-return-init.json').read_text())
    header = BASE/'diagnostics'/profile['header_file']
    if (output.exists() or output.is_symlink() or output.resolve().is_relative_to(source.resolve())
            or source.resolve().is_relative_to(output.resolve())):
        raise ValueError('output must be absent and separate from source')
    if HELPER.files(source) != profile['base_source_files']:
        raise ValueError('qualified source file set/hash mismatch')
    if header.is_symlink() or hashlib.sha256(header.read_bytes()).hexdigest() != profile['header_sha256']:
        raise ValueError('observer header drift')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='rpc-init-observer-', dir=output.parent) as temporary:
        stage = Path(temporary)/'hexagonrpc'; shutil.copytree(source, stage)
        shutil.copyfile(header, stage/'hexagonrpcd/rpc-return-trace.h')
        after = HELPER.files(stage)
        changed = sorted(n for n in set(after)|set(profile['base_source_files'])
                         if after.get(n) != profile['base_source_files'].get(n))
        if changed != profile['changed_files']:
            raise ValueError('unexpected observer source change')
        report = dict(profile=profile, source_hashes=after, changed_files=changed,
                      device_operations=False, hardware_verified=False)
        (stage/'INIT_OBSERVER_SOURCE.json').write_text(json.dumps(report, indent=2)+'\n')
        stage.rename(output)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = prepare(args.source, args.output)
    print(json.dumps(dict(changed_files=result['changed_files'], device_operations=False)))
