#!/usr/bin/env python3
"""Prepare a hash-bound ARM64 GNOME package cache, without installing anything."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from urllib.parse import urlsplit
from urllib.request import urlopen


def validate(manifest):
    rows = manifest['packages']
    if manifest['package_count'] != len(rows) or not rows:
        raise ValueError('package count mismatch')
    names = set()
    for row in rows:
        name = row['filename']
        url = urlsplit(row['url'])
        if (Path(name).name != name or not name.endswith('.deb') or
                name in names or row['architecture'] not in ('arm64', 'all') or
                not re.fullmatch('[0-9a-f]{64}', row['sha256']) or
                type(row['bytes']) is not int or row['bytes'] <= 0 or
                url.scheme != 'https' or not url.hostname or url.username or url.password):
            raise ValueError('invalid package identity: ' + name)
        names.add(name)
    if sum(row['bytes'] for row in rows) != manifest['download_bytes']:
        raise ValueError('download size mismatch')
    return rows


def matches(path, row):
    return (path.is_file() and not path.is_symlink() and
            path.stat().st_size == row['bytes'] and
            hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256'])


def fetch(row, output, opener=urlopen):
    target = output / row['filename']
    if matches(target, row):
        return dict(filename=row['filename'], status='reused')
    if target.exists() or target.is_symlink():
        raise ValueError('existing cache mismatch: ' + str(target))
    with tempfile.NamedTemporaryFile(dir=output, prefix='.download-', delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with opener(row['url'], timeout=60) as response:
                while block := response.read(1024 * 1024):
                    stream.write(block)
                    if stream.tell() > row['bytes']:
                        raise ValueError('oversized download: ' + row['filename'])
            stream.close()
            if not matches(temporary, row):
                raise ValueError('download identity mismatch: ' + row['filename'])
            # Another preparer must not replace an unverified existing file.
            os.link(temporary, target)
            return dict(filename=row['filename'], status='downloaded')
        finally:
            temporary.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--jobs', type=int, default=4, choices=range(1, 9))
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text())
    rows = validate(manifest)
    args.output.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        results = list(pool.map(lambda row: fetch(row, args.output), rows))
    report = dict(verdict='PACKAGE_CACHE_VERIFIED', packages=len(results),
                  downloaded=sum(x['status'] == 'downloaded' for x in results),
                  bytes=manifest['download_bytes'], installation_executed=False,
                  device_operations=False, results=results)
    (args.output / 'PREPARED.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: v for k, v in report.items() if k != 'results'}, indent=2))


if __name__ == '__main__':
    main()
