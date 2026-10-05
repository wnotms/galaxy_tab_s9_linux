#!/usr/bin/env python3
"""Build/hash a boot-only Test325 candidate offline. Never contacts a device."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tarfile
import tempfile

ROOT = Path(__file__).resolve().parents[3]
R = Path(__file__).resolve().parent
QUALIFIED = R
ACCEPTED = ROOT / 'reference/boot-tests/test-323-pc-source-budget'
RELEASE = '7.2.0-rc3-gts9wifi-dirty'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def metadata(path):
    return dict(path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha256=sha(path))


def verify_file(info):
    path = ROOT / info['path']
    if sha(path) != info['sha256'] or path.stat().st_size != info['bytes']:
        raise ValueError('artifact drift: ' + str(path))
    return path


def archive_manifest(path):
    files = {}
    with tarfile.open(path) as tar:
        for member in tar:
            parts = Path(member.name).parts
            if not parts or parts[0] != RELEASE or any(p in ('.', '..') for p in parts):
                raise ValueError('unsafe/unexpected module archive path')
            if member.isdir():
                continue
            if not member.isfile():
                raise ValueError('module archive links/special files refused')
            key = '/'.join(parts[1:])
            if not key or key in files:
                raise ValueError('duplicate/missing module name')
            with tar.extractfile(member) as stream:
                files[key] = hashlib.sha256(stream.read()).hexdigest()
    if len(files) != 181:
        raise ValueError('expected exact181-file module directory')
    return files


def manifest(path, entries):
    path.write_text(''.join(value + '  ' + name + '\n' for name, value in sorted(entries.items())))


def build():
    q = json.loads((QUALIFIED / 'summary.json').read_text())
    if q['verdict'] != 'OFFLINE_NATIVE_ONESHOT_PASS':
        raise ValueError('candidate not qualified')
    artifacts = {name: verify_file(info) for name, info in q['artifacts'].items()}
    accepted = json.loads((ACCEPTED / 'PACKAGE.json').read_text())
    old_boot = verify_file(accepted['artifacts']['boot.img'])
    old_modules = verify_file(accepted['artifacts']['modules-x710.tar.gz'])
    candidate_modules = archive_manifest(artifacts['modules-x710.tar.gz'])
    original_modules = archive_manifest(old_modules)
    # Preserve the exact existing passive DTB; no full bundle regeneration.
    if sha(artifacts['sm8550-samsung-gts9wifi.dtb']) != accepted['artifacts']['sm8550-samsung-gts9wifi.dtb']['sha256']:
        raise ValueError('DTB differs from accepted baseline')
    out = ROOT / 'out/boot-bundle-x710-oneshot-fixed9'
    out.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        payload = artifacts['Image.gz'].read_bytes() + artifacts['sm8550-samsung-gts9wifi.dtb'].read_bytes()
        (temp / 'kernel').write_bytes(payload)
        boot = out / 'boot.img'
        subprocess.run(['python3', str(ROOT / '.work/tools/mkbootimg.py'),
                        '--kernel', str(temp / 'kernel'), '--cmdline', '',
                        '--header_version', '4', '--os_version', '13',
                        '--os_patch_level', '2025-07', '-o', str(boot)], check=True)
        subprocess.run(['python3', str(ROOT / '.work/tools/avbtool.py'), 'add_hash_footer',
                        '--image', str(boot), '--partition_name', 'boot',
                        '--partition_size', '100663296', '--salt', sha(boot)], check=True)
        if boot.stat().st_size != 100663296:
            raise ValueError('boot partition size')
        header = subprocess.check_output(['python3', str(ROOT / '.work/tools/unpack_bootimg.py'),
                                          '--boot_img', str(boot), '--out', str(temp / 'unpacked')], text=True)
        if (temp / 'unpacked/kernel').read_bytes() != payload:
            raise ValueError('unpacked boot payload mismatch')
        if 'boot image header version: 4' not in header:
            raise ValueError('boot header version')
        (R / 'validation').mkdir(exist_ok=True)
        (R / 'validation/boot-header.txt').write_text(header)
    manifest(R / 'candidate-modules.sha256', candidate_modules)
    manifest(R / 'rollback-modules.sha256', original_modules)
    baseline = accepted['candidate_partitions']
    candidate = dict(baseline, boot=sha(boot))
    package = dict(test='Test325', source_revision=q['source_revision'],
                   kernel_qualification='isolated fixed9 OFF startup confirmation; unchanged native ADC converter', write_partitions=['boot'], modules=181,
                   baseline_partitions=baseline, candidate_partitions=candidate,
                   rollback_baseline='accepted Test323 source-authorized ordinary PC charging',
                   artifacts=dict(q['artifacts'], **{'boot.img': metadata(boot),
                       'rollback-boot.img': metadata(old_boot),
                       'rollback-modules-x710.tar.gz': metadata(old_modules)}),
                   all_other_partitions_unchanged=True, device_commands_executed=False)
    (R / 'PACKAGE.json').write_text(json.dumps(package, indent=2) + '\n')
    return package


if __name__ == '__main__':
    print(json.dumps(build(), indent=2))
