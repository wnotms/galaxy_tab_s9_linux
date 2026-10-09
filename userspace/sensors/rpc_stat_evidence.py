#!/usr/bin/env python3
"""Compare same-boot sensor RPC stat results with frozen X710 archive metadata."""
import argparse
import json
from pathlib import Path
import re
from uuid import UUID

UNIT = 'hexagonrpcd-adsp-sensorspd.service'
STAT = re.compile(r'stat\(([^)\r\n]+)\) -> size=(\d+) mtime=(-?\d+)\.(\d{9})')


def inspect(raw, boot_id, metadata):
    boot = UUID(boot_id).hex
    expected = {}
    for item in metadata['entries']:
        name = item['virtual_path']
        if (name in expected or not name.startswith('/vendor/etc/sensors/config/') or
                not item['mtime_matches'] or
                item['archive_mtime_seconds'] != item['cache_mtime_seconds'] or
                type(item['archive_size']) is not int or item['archive_size'] < 0):
            raise ValueError('invalid or duplicate X710 archive metadata')
        expected[name] = item
    if not expected:
        raise ValueError('empty metadata reference')
    rows = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if not rows:
        raise ValueError('empty runtime journal')
    seen, faults = {}, []
    for index, row in enumerate(rows):
        if not isinstance(row, dict) or UUID(row['_BOOT_ID']).hex != boot:
            raise ValueError('runtime journal boot attribution mismatch')
        if row.get('_SYSTEMD_UNIT') != UNIT:
            continue
        message = row.get('MESSAGE')
        if not isinstance(message, str):
            raise ValueError('invalid sensor journal message')
        match = STAT.fullmatch(message)
        if match and match[1] in expected:
            name, size, seconds, nanoseconds = match.groups()
            reference = expected[name]
            timestamp = int(row['__MONOTONIC_TIMESTAMP'])
            if timestamp < 0:
                raise ValueError('negative source timestamp')
            event = dict(row=index, monotonic_us=timestamp, size=int(size),
                         mtime_seconds=int(seconds), mtime_nanoseconds=int(nanoseconds))
            seen.setdefault(name, []).append(event)
            if (event['size'] != reference['archive_size'] or
                    event['mtime_seconds'] != reference['cache_mtime_seconds'] or
                    event['mtime_nanoseconds'] != 0):
                faults.append(dict(row=index, path=name, reason='returned stat differs from frozen archive/cache'))
        elif any(message.startswith('stat(' + n + ')') or
                 message.startswith('Could not stat ' + n + ':') or
                 message.startswith('Could not open ' + n + ':') for n in expected):
            faults.append(dict(row=index, message=message, reason='missing metadata or config stat/open failure'))
    missing = sorted(set(expected) - set(seen))
    complete = not missing and not faults
    return dict(boot_id=str(UUID(boot_id)), verdict='RPC_CONFIG_METADATA_PASS' if complete else 'RPC_CONFIG_METADATA_INCOMPLETE_OR_FAILED',
                complete=complete, reference_entries=len(expected), observed_entries=len(seen),
                missing=missing, faults=faults, events=seen,
                SSC_publication_proved=False, accelerometer_sample_proved=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--journal', type=Path, required=True)
    parser.add_argument('--metadata', type=Path, required=True)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    result = inspect(args.journal.read_text(), args.boot_id, json.loads(args.metadata.read_text()))
    print(json.dumps(result, indent=2))
    raise SystemExit(not result['complete'])


if __name__ == '__main__':
    main()
