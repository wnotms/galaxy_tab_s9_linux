#!/usr/bin/env python3
"""Build/hash a boot-only Test318 package offline. Never contacts a device."""
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
QUALIFIED = ROOT / 'reference/charging/sm5440-continuous-timing'
ACCEPTED = R.parent / 'test-311-serial-device-acceptance'
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
    if q['verdict'] != 'OFF_CONTINUOUS_ADC_DIAGNOSTIC_OFFLINE_QUALIFIED':
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
    out = ROOT / 'out/boot-bundle-x710-318-continuous-timing'
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
    package = dict(test='Test318', source_revision='44c2190ab9b264d4c43a95e31351bc1d0fb53c05',
                   kernel_qualification='44c2190a OFF continuous timing qualification', write_partitions=['boot'], modules=181,
                   baseline_partitions=baseline, candidate_partitions=candidate,
                   rollback_baseline='accepted Test308 ordinary recovery physically accepted in Test311',
                   artifacts=dict(q['artifacts'], **{'boot.img': metadata(boot),
                       'rollback-boot.img': metadata(old_boot),
                       'rollback-modules-x710.tar.gz': metadata(old_modules)}),
                   all_other_partitions_unchanged=True, device_commands_executed=False)
    (R / 'PACKAGE.json').write_text(json.dumps(package, indent=2) + '\n')
    return package


def stage(package, local=None):
    local = local or Path('/mnt/d/android/gts9-active/gts9-test318')
    selections = {'candidate-boot.img': ROOT / package['artifacts']['boot.img']['path'],
                  'rollback-accepted311-boot.img': ROOT / package['artifacts']['rollback-boot.img']['path'],
                  'candidate-modules.tar.gz': ROOT / package['artifacts']['modules-x710.tar.gz']['path'],
                  'candidate-modules.sha256': R / 'candidate-modules.sha256',
                  'rollback-modules.sha256': R / 'rollback-modules.sha256',
                  'module-swap.sh': R / 'module-swap.sh',
                  'mount-debian.sh': ROOT / 'scripts/twrp-mount-debian.sh'}
    # This is byte-identical to the accepted Test292 mounting helper. Validate
    # every input and any partial previous copy BEFORE making/copying anything.
    expected_mount = json.loads((R.parent / 'test-292-passive-observation/staged-files.json').read_text())['mount-debian.sh']
    if sha(selections['mount-debian.sh']) != expected_mount['sha256']:
        raise ValueError('accepted mount helper changed')
    source_hashes = {name: sha(source) for name, source in selections.items()}
    if local.exists():
        if local.is_symlink() or not local.is_dir():
            raise ValueError('invalid staging directory')
        if set(p.name for p in local.iterdir()) - set(selections):
            raise ValueError('unexpected staging file')
        for name, expected in source_hashes.items():
            target = local / name
            if target.exists() or target.is_symlink():
                if target.is_symlink() or not target.is_file() or sha(target) != expected:
                    raise ValueError('existing stage drift: ' + name)
    else:
        local.mkdir()
    for name, source in selections.items():
        if not (local / name).exists():
            existing = Path('/mnt/d/android/gts9-active/gts9-test311')
            reuse = next((p for p in existing.iterdir() if p.is_file() and p.stat().st_size == source.stat().st_size and sha(p) == source_hashes[name]), None) if existing.is_dir() else None
            if reuse is not None:
                import os
                os.link(reuse, local / name)
            else:
                shutil.copyfile(source, local / name)
        if sha(local / name) != source_hashes[name]:
            raise ValueError('stage copy mismatch: ' + name)
    files = {name: dict(sha256=sha(local / name), bytes=(local / name).stat().st_size)
             for name in selections}
    (R / 'staged-files.json').write_text(json.dumps(files, indent=2) + '\n')
    return files


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', action='store_true', help='copy package to Windows staging; no ADB/device access')
    parser.add_argument('--stage-only', action='store_true', help='verify and finish copying the already built package; do not regenerate boot')
    args = parser.parse_args()
    if args.stage_only:
        result = json.loads((R / 'PACKAGE.json').read_text())
        for info in result['artifacts'].values():
            verify_file(info)
    else:
        result = build()
    if args.stage or args.stage_only:
        stage(result)
    print(json.dumps(result, indent=2))
