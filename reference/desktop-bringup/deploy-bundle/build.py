#!/usr/bin/env python3
"""Reproduce the host-only GNOME deployment tar from existing verified assets."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE = Path(__file__).resolve().parent
CACHE = ROOT / 'out/gnome-trixie-arm64'
INITIAL = ROOT / 'reference/desktop-bringup/initial-readonly-1791439861'


def main():
    check = subprocess.run(['python3', str(ROOT / 'userspace/gnome/install.py'),
                            str(INITIAL / 'gnome-packages.json'), '--cache', str(CACHE / 'packages'),
                            '--firmware', str(CACHE / 'firmware-root')], capture_output=True, check=True)
    (EVIDENCE / 'cache-validation.json').write_bytes(check.stdout)
    packages = json.loads((INITIAL / 'gnome-packages.json').read_text())
    files = {'packages.json': INITIAL / 'gnome-packages.json',
             'firmware-source.json': INITIAL / 'gpu-firmware-source.json',
             'README.md': EVIDENCE / 'BUNDLE_README.md',
             'tools/install.py': ROOT / 'userspace/gnome/install.py',
             'tools/prepare.py': ROOT / 'userspace/gnome/prepare.py',
             'optional-touch/fts1ba90a.ko': CACHE / 'touch-module/fts1ba90a.ko',
             'optional-touch/SOURCE.json': ROOT / 'kernel/desktop/fts1ba90a/SOURCE.json',
             'optional-touch/qualification.json': ROOT / 'reference/desktop-bringup/fts1ba90a-offline/summary.json'}
    for row in packages['packages']:
        files['packages/' + row['filename']] = CACHE / 'packages' / row['filename']
    firmware = CACHE / 'firmware-root'
    for path in sorted(firmware.rglob('*')):
        if path.is_file():
            files['firmware/' + str(path.relative_to(firmware))] = path
    payload = {}
    identities = {}
    for name, path in sorted(files.items()):
        if path.is_symlink() or not path.is_file() or '..' in Path(name).parts or Path(name).is_absolute():
            raise ValueError('unsafe/non-regular deployment input: ' + str(path))
        data = path.read_bytes()
        payload[name] = data
        identities[name] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
    touch = json.loads(files['optional-touch/qualification.json'].read_text())
    if identities['optional-touch/fts1ba90a.ko']['sha256'] != touch['module']['sha256']:
        raise ValueError('optional touch module changed after qualification')
    installer = json.loads((ROOT / 'reference/desktop-bringup/gnome-installer-offline/summary.json').read_text())
    if identities['tools/install.py']['sha256'] != installer['source_sha256']:
        raise ValueError('installer changed after affected-test qualification')
    payload['checksums.sha256'] = ''.join(row['sha256'] + '  ' + name + '\n'
                                         for name, row in identities.items()).encode()
    archive = CACHE / 'gts9-gnome-deploy.tar'
    with tarfile.open(archive, 'w', format=tarfile.PAX_FORMAT) as tar:
        for name, data in sorted(payload.items()):
            info = tarfile.TarInfo('gts9-gnome/' + name)
            info.size, info.mode, info.mtime = len(data), 0o644, 0
            info.uid = info.gid = 0
            info.uname = info.gname = 'root'
            tar.addfile(info, io.BytesIO(data))
    # Validate the actual archive's complete file set and bytes, not just the
    # staging inputs. No extraction or device operation occurs here.
    with tarfile.open(archive) as tar:
        members = tar.getmembers()
        if len(members) != len(payload) or {m.name for m in members} != {'gts9-gnome/' + n for n in payload}:
            raise ValueError('deployment archive file-set mismatch')
        for member in members:
            if not member.isfile() or tar.extractfile(member).read() != payload[member.name.removeprefix('gts9-gnome/')]:
                raise ValueError('deployment archive content mismatch')
    summary = dict(verdict='HOST_DEPLOY_BUNDLE_VERIFIED_NOT_TRANSFERRED',
                   archive=str(archive.relative_to(ROOT)), bytes=archive.stat().st_size,
                   sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                   members=len(payload), packages=packages['package_count'], firmware_files=3,
                   optional_touch_loaded=False, installation_executed=False, device_operations=False,
                   input_identities=identities)
    (EVIDENCE / 'bundle.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps({k: v for k, v in summary.items() if k != 'input_identities'}, indent=2))


if __name__ == '__main__':
    main()
