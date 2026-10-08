#!/usr/bin/env python3
"""Host-only verification of the registered X710 stock sensor export.

MDT checks follow Linux 7.2-rc3 drivers/soc/qcom/mdt_loader.c; they establish
structural completeness, never TrustZone authentication or runtime acceptance.
No extraction, installation, device command or daemon activation is performed.
"""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import tarfile

ELF_HEADER = struct.Struct('<16sHHIIIIIHHHHHH')
PROGRAM_HEADER = struct.Struct('<8I')
TYPE_MASK = 7 << 24
TYPE_HASH = 2 << 24


def digest(data):
    return hashlib.sha256(data).hexdigest()


def audit_mdt(name, files):
    data = files[name]
    if len(data) < ELF_HEADER.size:
        raise ValueError('short ELF header')
    h = ELF_HEADER.unpack_from(data)
    if h[0][:6] != b'\x7fELF\x01\x01' or h[3] != 1:
        raise ValueError('only ELF32 little-endian version 1 is supported')
    phoff, shoff, phsize, count, shsize, shcount = h[5], h[6], h[9], h[10], h[11], h[12]
    if phsize != 32 or not 2 <= count <= 100 or phoff + count * 32 > len(data):
        raise ValueError('invalid MDT program table')
    if (shsize or shcount) and (shsize != 40 or shoff + shcount * 40 > len(data)):
        raise ValueError('invalid MDT section table')
    ph = [PROGRAM_HEADER.unpack_from(data, phoff + i * 32) for i in range(count)]
    if ph[0][0] == 1 or ph[0][4] < phoff + count * 32 or ph[0][4] > len(data):
        raise ValueError('invalid MDT metadata header')
    hashes = [i for i in range(1, count) if ph[i][6] & TYPE_MASK == TYPE_HASH]
    if not hashes:
        raise ValueError('missing MDT hash metadata')
    required = []

    def segment(i):
        path = name[:-3] + f'b{i:02d}'
        if path not in files or len(files[path]) != ph[i][4]:
            raise ValueError(f'missing or wrong-sized split segment: {path}')
        required.append(path)

    hi = hashes[0]
    header_size, hash_size = ph[0][4], ph[hi][4]
    if not hash_size:
        raise ValueError('empty MDT hash metadata')
    if header_size + hash_size == len(data):
        metadata = 'packed-after-header'
    elif ph[hi][1] + hash_size <= len(data):
        metadata = 'embedded-at-offset'
    else:
        segment(hi)
        metadata = 'split-hash-segment'
    split = any(p[4] and p[1] + p[4] > len(data) for p in ph)
    loadable = []
    for i, p in enumerate(ph):
        if p[0] != 1 or p[6] & TYPE_MASK == TYPE_HASH or not p[5]:
            continue
        if p[4] > p[5] or p[3] + p[5] > 2**32:
            raise ValueError('invalid load segment size/address')
        loadable.append(p)
        if split and p[4]:
            segment(i)
    if not loadable:
        raise ValueError('no loadable segments')
    low = min(p[3] for p in loadable)
    high = max((p[3] + p[5] + 4095) & ~4095 for p in loadable)
    return dict(program_headers=count, loadable_segments=len(loadable), split=split,
                metadata_location=metadata, required_split_files=required,
                memory_start=low, memory_end=high, memory_bytes=high-low,
                structurally_complete=True, authentication_verified=False)


def inspect_registry(files):
    root = 'persist/sensors/registry/'
    marker = root + 'registry/sensors_registry'
    cache = root + 'registry/sns_reg_config'
    if marker not in files or files[marker] != b'' or cache not in files:
        raise ValueError('stock completion marker or timestamp cache absent/invalid')
    entries = json.loads(files[cache])['sns_reg_config']
    inputs = []
    for path, value in entries.items():
        if path == 'owner':
            continue
        p = PurePosixPath(path)
        if str(p.parent) != '/vendor/etc/sensors/config' or p.suffix != '.json' or '..' in p.parts:
            raise ValueError('unexpected registry config input path')
        if value['type'] != 'int' or int(value['data']) < 0:
            raise ValueError('invalid config timestamp')
        inputs.append(dict(path=path, required_mtime=int(value['data'])))
    if not inputs:
        raise ValueError('empty registry timestamp cache')
    # Fedora's HexagonFS maps virtual .../sensors/registry to PREFIX/sensors.
    mapping = {n: 'sensors/' + n[len(root):] for n in files if n.startswith(root)}
    return dict(completion_marker_present=True, config_inputs=sorted(inputs, key=lambda x:x['path']),
                copied_registry_mapping=mapping, config_inputs_collected=False,
                timestamp_normalization_allowed=False, real_persist_exposed=False)


def verify_archive(path, expected_sha256):
    if digest(Path(path).read_bytes()) != expected_sha256:
        raise ValueError('archive SHA-256 mismatch')
    files, members = {}, {}
    total = 0
    with tarfile.open(path) as archive:
        for m in archive:
            p = PurePosixPath(m.name)
            if (not m.isfile() or str(p) != m.name or p.is_absolute() or '..' in p.parts
                    or m.name in files or not 0 <= m.size <= 64*1024*1024):
                raise ValueError('unsafe/duplicate/special/oversized archive member')
            if m.name != 'MANIFEST.json' and p.parts[0] not in ('apnhlos','dsp','persist'):
                raise ValueError('unexpected asset root')
            total += m.size
            if total > 192*1024*1024 or len(files) >= 8193:
                raise ValueError('archive bounds exceeded')
            files[m.name] = archive.extractfile(m).read()
            members[m.name] = m
    manifest = json.loads(files.pop('MANIFEST.json'))
    if (manifest['purpose'] != 'READ_ONLY_STOCK_SENSOR_ASSETS'
            or manifest['firmware_installed'] or manifest['remoteproc_started']
            or not manifest['temporary_mounts_removed'] or manifest['cleanup_errors']
            or manifest['skipped_links']):
        raise ValueError('collection was incomplete or outside registered scope')
    if set(files) != set(manifest['files']):
        raise ValueError('manifest file set mismatch')
    for name, data in files.items():
        entry = manifest['files'][name]
        if (len(data) != entry['bytes'] or digest(data) != entry['sha256']
                or members[name].mtime != entry['archive_mtime']):
            raise ValueError('asset identity/mtime mismatch: ' + name)
    if sum(len(b) for b in files.values()) != manifest['total_bytes']:
        raise ValueError('manifest total mismatch')
    firmware = {n: audit_mdt('apnhlos/image/'+n, files) for n in ('adsp.mdt','adsp_dtb.mdt')}
    # Existing X710 reserved memory, unchanged; do not use reference-board sizes.
    for name, start, size in [('adsp.mdt',0x9ea00000,0x59b4000),
                              ('adsp_dtb.mdt',0x9e980000,0x80000)]:
        item = firmware[name]
        if item['memory_start'] < start or item['memory_end'] > start + size:
            raise ValueError('firmware exceeds existing X710 reserved memory')
        item['existing_reserved_region_fits'] = True
    return dict(verdict='STOCK_ASSETS_VERIFIED_CONFIG_INPUTS_STILL_REQUIRED',
                archive_sha256=expected_sha256, boot_id=manifest['boot_id'],
                files=len(files), bytes=manifest['total_bytes'],
                partition_file_counts={p:sum(n.startswith(p+'/') for n in files)
                                       for p in ('apnhlos','dsp','persist')},
                firmware=firmware, registry=inspect_registry(files),
                device_deployment_ready=False, remoteproc_started=False)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--archive',type=Path,required=True)
    p.add_argument('--sha256',required=True)
    p.add_argument('--report',type=Path,required=True)
    args = p.parse_args()
    result = verify_archive(args.archive,args.sha256)
    args.report.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:result[k] for k in ('verdict','files','bytes','device_deployment_ready')}))


if __name__ == '__main__':
    main()
