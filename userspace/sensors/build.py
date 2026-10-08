#!/usr/bin/env python3
"""Cross-compile verified SSC sources in a networkless disposable container."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

BASE = Path(__file__).resolve().parent
_PREPARE_SPEC = importlib.util.spec_from_file_location(
    "gts9_ssc_source_prepare", BASE / "prepare.py")
_PREPARE = importlib.util.module_from_spec(_PREPARE_SPEC)
_PREPARE_SPEC.loader.exec_module(_PREPARE)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_sources(tree):
    manifest = json.loads((BASE / 'sources.json').read_text())
    report = json.loads((tree / 'PREPARED.json').read_text())
    if report['fedora_commit'] != manifest['fedora_commit']:
        raise ValueError('Fedora source identity mismatch')
    expected = {row['name']: row for row in manifest['sources']}
    rows = report['sources']
    if len(rows) != len(expected) or {r['name'] for r in rows} != set(expected):
        raise ValueError('source set mismatch')
    for row in rows:
        spec = expected[row['name']]
        if (row['version'], row['archive_sha256']) != (spec['version'], spec['sha256']):
            raise ValueError('source version/archive mismatch')
        if [p['patch'] for p in row['patches']] != [p['path'] for p in spec['patches']] or any(
                p['returncode'] for p in row['patches']):
            raise ValueError('patch preparation mismatch')
        root = tree / row['name']
        paths = list(root.rglob('*'))
        if root.is_symlink() or not root.is_dir() or any(p.is_symlink() for p in paths):
            raise ValueError('source links are forbidden')
        files = {str(p.relative_to(root)) for p in paths if p.is_file()}
        if files != set(row['patched_files']):
            raise ValueError('prepared file set mismatch')
        for name, sha in row['patched_files'].items():
            if digest(root / _PREPARE.relative(name)) != sha:
                raise ValueError('prepared source hash mismatch: ' + name)
    return report


def inspect_stage(stage):
    """Check every ELF target and ensure units have Debian's standard location."""
    files = {}
    links = {}
    elf_files = []
    for path in sorted(stage.rglob('*')):
        name = str(path.relative_to(stage))
        if 'systemd/system/' in name and '.wants/' in name:
            raise ValueError('offline stage must not enable services')
        if path.is_symlink():
            # Keep links relative and within the package tree.
            if not path.resolve().is_relative_to(stage.resolve()):
                raise ValueError('staged symlink escapes package')
            if not path.exists():
                raise ValueError('broken staged symlink')
            links[name] = os.readlink(path)
            continue
        if not path.is_file():
            continue
        data = path.read_bytes()
        if data[:4] == b'\x7fELF':
            if len(data) < 20 or data[4:6] != b'\x02\x01' or int.from_bytes(data[18:20], 'little') != 183:
                raise ValueError('staged ELF is not little-endian ARM64: ' + name)
            elf_files.append(name)
        if path.suffix == '.service' and path.parent != stage / 'usr/lib/systemd/system':
            raise ValueError('systemd service outside Debian unit path')
        files[name] = hashlib.sha256(data).hexdigest()
    required = ['usr/bin/pd-mapper', 'usr/bin/ssccli', 'usr/bin/monitor-sensor',
                'usr/bin/hexagonrpcd', 'usr/libexec/iio-sensor-proxy']
    if any(name not in elf_files for name in required):
        raise ValueError('missing ARM64 runtime executable')
    return dict(files=files, links=links, elf_files=elf_files)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sources', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--image', default='gts9-ssc-builder:trixie-arm64')
    args = parser.parse_args()
    tree = args.sources.resolve()
    output = args.output.resolve()
    verify_sources(tree)
    if output.exists() or output.is_relative_to(tree) or tree.is_relative_to(output):
        raise ValueError('output must be new and separate from inputs')
    identity = json.loads(subprocess.check_output(['docker', 'image', 'inspect', args.image]))[0]
    output.mkdir(parents=True)
    (output / 'image.json').write_text(json.dumps(identity, indent=2) + '\n')
    command = ['docker', 'run', '--rm', '--network=none',
               '--security-opt=no-new-privileges',
               '-e', 'HOST_UID=' + str(os.getuid()), '-e', 'HOST_GID=' + str(os.getgid()),
               '-v', str(tree) + ':/inputs:ro', '-v', str(BASE) + ':/recipe:ro',
               '-v', str(output) + ':/output', identity['Id'], 'sh', '/recipe/compile.sh']
    with (output / 'build.log').open('wb') as log:
        result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT)
    # compile.sh returns bind-mounted outputs to the invoking host user's UID.
    report = dict(build_returncode=result.returncode, device_operations=False,
                  installation_executed=False, image=identity['Id'],
                  inputs={p.name: digest(p) for p in [BASE / 'build.py', BASE / 'compile.sh',
                      BASE / 'cross-arm64.ini', BASE / 'builder.Dockerfile', tree / 'PREPARED.json']})
    if result.returncode == 0:
        try:
            report.update(inspect_stage(output / 'stage'))
            subprocess.run(['tar', '--sort=name', '--mtime=@0', '--owner=0', '--group=0',
                            '--numeric-owner', '-czf', str(output / 'ssc-arm64-stage.tar.gz'),
                            '-C', str(output / 'stage'), '.'], check=True)
            report['stage_archive_sha256'] = digest(output / 'ssc-arm64-stage.tar.gz')
            report['verdict'] = 'ARM64_COMPILED_NOT_DEPLOYED'
        except (ValueError, subprocess.CalledProcessError) as error:
            report['validation_error'] = str(error)
    final_status = result.returncode or int('validation_error' in report)
    report['final_status'] = final_status
    (output / 'BUILD.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k not in ('files', 'elf_files')}, indent=2))
    raise SystemExit(final_status)


if __name__ == '__main__':
    main()
