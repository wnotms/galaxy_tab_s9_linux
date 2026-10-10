#!/usr/bin/env python3
"""Prepare a host-only, complete X710 Fedora ADSP comparison profile.

Only the two split firmware images change. Factory registry, DSP libraries and
PD maps remain byte/mode/mtime exact. No extraction to rootfs or device access.
MDT structure checks do not establish PAS authentication or sensor acceptance.
"""
import argparse
import gzip
import hashlib
import importlib.util
import io
import json
from pathlib import Path, PurePosixPath
import re
import tarfile

BASE_SHA = '6abc10ecdb82c6abe175461ae483670be0c82c8e038cb9acbf5eb5f8ae9231e5'
FEDORA_SHA = '30cace40556fdaf1577c76bedc1b1a6236f4acc23e9300253b3834fa7ed4bab5'
FEDORA_URL = ('https://github.com/nacht20-de/gts9wifi-fedora-linux/releases/download/'
              'kernel-7.2.0-rc3-gts9wifi-2/firmware-samsung-gts9wifi-v2.tar.gz')
FW = 'usr/lib/firmware/qcom/sm8550/'
PATTERN = re.compile(re.escape(FW) + r'adsp(?:_dtb)?\.(?:mdt|b[0-9]{2})\Z')
SPEC = importlib.util.spec_from_file_location(
    'fedora_adsp_mdt', Path(__file__).with_name('verify-stock-assets.py'))
MDT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MDT)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_archive(path, expected, *, directories=False, owner=(0, 0)):
    path = Path(path)
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024**2:
        raise ValueError('unsafe archive source/size')
    data = path.read_bytes()
    if digest(data) != expected:
        raise ValueError('archive identity')
    files, seen, total = {}, set(), 0
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        for member in archive:
            name = member.name
            p = PurePosixPath(name)
            if (not p.parts or str(p) != name or p.is_absolute() or '..' in p.parts
                    or name in seen or len(seen) >= 8192):
                raise ValueError('unsafe/duplicate archive path')
            seen.add(name)
            if directories and member.isdir():
                continue
            if (not member.isfile() or (member.uid, member.gid) != owner
                    or not 0 <= member.size <= 64 * 1024**2
                    or member.mode & ~0o777 or member.mtime < 0):
                raise ValueError('nonregular/ownership/mode/size archive member')
            total += member.size
            if total > 256 * 1024**2:
                raise ValueError('archive expanded size')
            raw = archive.extractfile(member).read()
            if len(raw) != member.size:
                raise ValueError('short archive member')
            files[name] = dict(data=raw, mtime=member.mtime, mode=member.mode)
    return files


def firmware_audit(files):
    mapped = {'apnhlos/image/' + Path(n).name: e['data']
              for n, e in files.items() if PATTERN.fullmatch(n)}
    reports = {}
    for name, start, size in (('adsp.mdt', 0x9ea00000, 0x59b4000),
                              ('adsp_dtb.mdt', 0x9e980000, 0x80000)):
        raw = mapped.get('apnhlos/image/' + name, b'')
        # Both qualified X710 archives use164 for executable ADSP and1 for
        # the opaque ADSP-DTB MDT envelope. The latter is not Hexagon code.
        machine = 164 if name == 'adsp.mdt' else 1
        if len(raw) < 20 or int.from_bytes(raw[18:20], 'little') != machine:
            raise ValueError('MDT machine differs from qualified X710 envelope')
        report = MDT.audit_mdt('apnhlos/image/' + name, mapped)
        if report['memory_start'] != start or report['memory_bytes'] > size:
            raise ValueError('firmware exceeds unchanged X710 carveout')
        reports[name] = report
    return reports


def plan(base, fedora):
    names = {n for n in base if PATTERN.fullmatch(n)}
    selected = {n for n in fedora if PATTERN.fullmatch(n)}
    if len(names) != 52 or names != selected:
        raise ValueError('complete 52-file firmware pair required')
    current_audit, candidate_audit = firmware_audit(base), firmware_audit(fedora)
    result = {n: dict(e) for n, e in base.items()}
    rows = []
    for n in sorted(names):
        # Retain baseline root-owned file mode; take each firmware member,
        # including unchanged segments, from the single pinned release archive.
        result[n] = dict(data=fedora[n]['data'], mtime=fedora[n]['mtime'], mode=base[n]['mode'])
        rows.append(dict(path=n, before=digest(base[n]['data']),
                         after=digest(result[n]['data']),
                         bytes_before=len(base[n]['data']), bytes_after=len(result[n]['data']),
                         changed=base[n]['data'] != result[n]['data']))
    if set(result) != set(base) or any(result[n] != base[n] for n in base if n not in names):
        raise ValueError('non-ADSP asset changed')
    return result, dict(firmware_files=len(names), changed_files=sum(e['changed'] for e in rows),
                       current_MDT=current_audit, candidate_MDT=candidate_audit,
                       firmware_changes=rows, non_firmware_members_preserved=len(base)-len(names),
                       authentication_verified=False, device_operations=False)


def stage(base_path, fedora_path, output):
    base = read_archive(base_path, BASE_SHA)
    # Pinned Fedora release was archived by UID/GID1000. It is a byte source,
    # never extracted; the new tar is explicitly generated as root:root.
    fedora = read_archive(fedora_path, FEDORA_SHA, directories=True, owner=(1000, 1000))
    files, report = plan(base, fedora)
    output = Path(output)
    output.mkdir(mode=0o700, exist_ok=False)
    target = output / 'sensor-assets.tar.gz'
    with target.open('xb') as stream:
        target.chmod(0o600)
        with gzip.GzipFile(fileobj=stream, filename='', mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name, e in sorted(files.items()):
                    m = tarfile.TarInfo(name)
                    m.size, m.mtime, m.mode = len(e['data']), e['mtime'], e['mode']
                    archive.addfile(m, io.BytesIO(e['data']))
    archive_sha = digest(target.read_bytes())
    if read_archive(target, archive_sha) != files:
        raise ValueError('reopened output mismatch')
    report.update(verdict='FEDORA_ADSP_PROFILE_OFFLINE_ONLY',
                  base_archive_sha256=BASE_SHA, fedora_archive_sha256=FEDORA_SHA,
                  fedora_release_url=FEDORA_URL, archive_sha256=archive_sha,
                  files={n: dict(bytes=len(e['data']), sha256=digest(e['data']),
                                 mtime=e['mtime'], mode=e['mode']) for n, e in sorted(files.items())},
                  deployment_ready=False,
                  outstanding=['independent registration', 'early ramdisk matching52 firmware',
                               'qualified transactional firmware install/restore',
                               'fresh baseline/rescue/health admission',
                               'one early boot/PAS/SSC/sample acceptance and exact370 return'])
    (output/'PROFILE.json').write_text(json.dumps(report, indent=2, sort_keys=True)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--fedora', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.base, args.fedora, args.output)
    print(json.dumps({k: result[k] for k in ('verdict', 'firmware_files', 'changed_files',
                      'non_firmware_members_preserved', 'archive_sha256', 'deployment_ready')}))
