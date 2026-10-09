#!/usr/bin/env python3
"""Read-only comparison of X710 IMU config leaves with copied registry groups."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import tarfile

PREFIX = 'usr/share/qcom/sm8550/Samsung/gts9wifi/sensors/'
GROUPS = {
    'lsm6dso_0_platform.config': ('kailua_lsm6dso_0_0.json', ('lsm6dso_0_platform', '.config')),
    'lsm6dso_0_platform.orient': ('kailua_lsm6dso_0_0.json', ('lsm6dso_0_platform', '.orient')),
    'lsm6dso_0.accel.config': ('lsm6dso_0.json', ('lsm6dso_0', '.accel', '.config')),
    'lsm6dso_0.gyro.config': ('lsm6dso_0.json', ('lsm6dso_0', '.gyro', '.config')),
}


def audit(path, expected_sha256):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ValueError('archive must be a regular input')
    payload = path.read_bytes()
    actual_sha = hashlib.sha256(payload).hexdigest()
    if actual_sha != expected_sha256:
        raise ValueError('archive hash mismatch')
    results = {}
    with tarfile.open(fileobj=io.BytesIO(payload), mode='r:*') as archive:
        names = [m.name for m in archive.getmembers()]
        if len(names) != len(set(names)):
            raise ValueError('duplicate archive member')

        def read(name):
            try:
                member = archive.getmember(PREFIX + name)
            except KeyError as exc:
                raise ValueError('missing core sensor member: ' + name) from exc
            if not member.isfile() or not 0 < member.size <= 128 * 1024:
                raise ValueError('invalid core sensor member: ' + name)
            # These specific core files are strict JSON. Do not repair unrelated
            # vendor JSON extensions, flatten calibration or infer selection.
            return json.loads(archive.extractfile(member).read())

        for group, (filename, keys) in GROUPS.items():
            document = read('config/' + filename)
            reference = document
            for key in keys:
                reference = reference[key]
            saved = read('registry/' + group)
            if set(saved) != {group} or not isinstance(reference, dict):
                raise ValueError('invalid core registry schema')
            current = saved[group]
            if not isinstance(current, dict):
                raise ValueError('invalid core registry schema')
            different = sorted(key for key in reference.keys() | current.keys()
                               if reference.get(key) != current.get(key))
            results[group] = dict(config_file=filename, selectors=document['config'],
                                  matches=not different, differing_fields=different,
                                  config_values=reference, registry_values=current)
    complete = all(r['matches'] for r in results.values())
    return dict(verdict='CORE_IMU_CACHE_MATCHES_CONFIG' if complete else 'CORE_IMU_CACHE_DIFFERS_FROM_CONFIG',
                complete=complete, archive_sha256=actual_sha, groups=results,
                device_operations=False, selector_match_proved=False,
                electrical_bus_type_proved=False, SSC_publication_proved=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--sha256', required=True)
    args = parser.parse_args()
    result = audit(args.archive, args.sha256)
    print(json.dumps(result, indent=2))
    raise SystemExit(not result['complete'])


if __name__ == '__main__': main()
