#!/usr/bin/env python3
"""Stage pinned X710 GPU firmware on the host; never install or activate it."""
import argparse
import hashlib
import json
from pathlib import Path
import struct


DESTINATIONS = {
    'a740_sqe.fw': 'lib/firmware/qcom/a740_sqe.fw',
    'gmu_gen70200.bin': 'lib/firmware/qcom/gmu_gen70200.bin',
    # The current DT requests .mdt. Linux's MDT loader also accepts a complete
    # ELF/MBN at that name when every segment is inside the file (no .bNN).
    'a740_zap.mbn': 'lib/firmware/qcom/a740_zap.mdt',
}


def validate_zap(data):
    """Check complete ELF32 metadata/load segments, not signature authenticity."""
    if len(data) < 52 or data[:7] != b'\x7fELF\x01\x01\x01':
        raise ValueError('ZAP must be a complete little-endian ELF32 image')
    header = struct.unpack_from('<16sHHIIIIIHHHHHH', data)
    offset, entry_size, count = header[5], header[9], header[10]
    if (header[8] != 52 or entry_size != 32 or count < 2 or
            offset < 52 or offset + entry_size * count > len(data)):
        raise ValueError('invalid ELF program header table')
    segments = [struct.unpack_from('<8I', data, offset + i * entry_size)
                for i in range(count)]
    if segments[0][0] == 1 or not (offset + entry_size * count <= segments[0][4] <= len(data)):
        raise ValueError('invalid Qualcomm header segment')
    hashes = [s for s in segments[1:] if s[6] & (7 << 24) == (2 << 24)]
    loads = [s for s in segments if s[0] == 1 and s not in hashes and s[5]]
    if len(hashes) != 1 or not hashes[0][4] or not loads:
        raise ValueError('missing Qualcomm hash or load segment')
    for segment in segments:
        if segment[4] and segment[1] + segment[4] > len(data):
            raise ValueError('split/truncated firmware requires missing segments')
    for segment in loads:
        if segment[4] > segment[5] or segment[3] + segment[5] > 2 ** 32:
            raise ValueError('invalid load segment memory bounds')
    return dict(format='complete-ELF32-MBN', program_headers=count,
                load_segments=len(loads), split_segments_required=False,
                cryptographic_authentication_verified=False)


def stage(manifest, source, output):
    rows = manifest['files']
    if len(rows) != len(DESTINATIONS) or {r['filename'] for r in rows} != set(DESTINATIONS):
        raise ValueError('expected exactly the three X710 GPU firmware files')
    prepared = []
    # Validate the whole set before publishing any file.
    for row in rows:
        path = source / row['filename']
        if path.is_symlink():
            raise ValueError('firmware source must not be a symlink')
        data = path.read_bytes()
        if len(data) != row['bytes'] or hashlib.sha256(data).hexdigest() != row['sha256']:
            raise ValueError('firmware source identity mismatch: ' + row['filename'])
        detail = validate_zap(data) if row['filename'] == 'a740_zap.mbn' else {}
        prepared.append((row, data, detail))
    output.mkdir(parents=True, exist_ok=True)
    if output.is_symlink() or any(output.iterdir()):
        raise ValueError('use a new empty host staging directory')
    result = []
    for row, data, detail in prepared:
        destination = DESTINATIONS[row['filename']]
        target = output / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open('xb') as stream:
            stream.write(data)
        result.append(dict(source=row['filename'], destination=destination,
                           sha256=row['sha256'], bytes=row['bytes'], **detail))
    report = dict(verdict='HOST_FIRMWARE_STAGED_NOT_DEPLOYED',
                  repository=manifest['repository'], commit=manifest['commit'],
                  device_operations=False, files=result)
    (output / 'PREPARED.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(json.loads(args.manifest.read_text()), args.source, args.output), indent=2))


if __name__ == '__main__':
    main()
