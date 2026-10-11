#!/usr/bin/env python3
"""Build an offline mtime-cache comparison over the qualified Test400 assets.

Changes only copied sns_reg_config timestamp values to the published Fedora
values. No factory calibration, config, firmware, physical persist or identity
file is changed. This archive alone is not qualified for device deployment.
"""
import argparse
import copy
import gzip
import importlib.util
import io
import json
from pathlib import Path
import tarfile

SPEC = importlib.util.spec_from_file_location(
    'registry_input_comparison', Path(__file__).with_name('fedora_sensor_inputs.py'))
INPUTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(INPUTS)
ARCHIVE = INPUTS.ARCHIVE
BASE_SHA = 'd647dcdf5ecc010080dbd057cec2c9cc66368d9e241cc3883a532e3f648177b3'


def plan(base, fedora):
    if len(base) != 328:
        raise ValueError('qualified complete 328-file baseline required')
    current = INPUTS.cache_map(base)
    reference = INPUTS.cache_map(fedora)
    if (len(current) != 35 or len(reference) != 35
            or [r['path'] for r in current] != [r['path'] for r in reference]
            or not all(r['cache_matches_archive'] for r in current)
            or any(r['cache_seconds'] != 0 or r['cache_matches_archive'] for r in reference)):
        raise ValueError('qualified current-matched/Fedora-zero cache boundary')
    for row in current:
        name = INPUTS.CONFIG + row['path'].rsplit('/', 1)[1]
        if base[name]['data'] != fedora[name]['data']:
            raise ValueError('sensor config differs from published reference')
    before = INPUTS.strict_json(base[INPUTS.CACHE]['data'])
    after = copy.deepcopy(before)
    for row in reference:
        after['sns_reg_config'][row['path']]['data'] = str(row['cache_seconds'])
    changes = INPUTS.fields(before, after)
    expected = {('sns_reg_config', r['path'], 'data') for r in current}
    if (len(changes) != 35 or {tuple(r['path']) for r in changes} != expected
            or any(r['after'] != '0' or not r['before_present'] or not r['after_present']
                   for r in changes)):
        raise ValueError('only 35 cached timestamp fields may differ')
    result = {n:dict(e) for n,e in base.items()}
    result[INPUTS.CACHE]['data'] = json.dumps(after, separators=(',', ':')).encode()
    if (set(result) != set(base) or result[INPUTS.CACHE] == base[INPUTS.CACHE]
            or any(result[n] != base[n] for n in base if n != INPUTS.CACHE)):
        raise ValueError('one copied cache member boundary')
    return result, dict(changed_file=INPUTS.CACHE, changed_fields=changes,
                        unchanged_files=327, files=328,
                        firmware_changed=False, calibration_input_changed=False,
                        config_input_changed=False, physical_persist_changed=False,
                        identity_input_changed=False, device_operations=False,
                        deployment_ready=False, SSC_rootcause_proved=False,
                        generated_cache_content_qualified=False)


def stage(base_path, fedora_path, output):
    base = ARCHIVE.read_archive(base_path, BASE_SHA)
    reference = ARCHIVE.read_archive(fedora_path, ARCHIVE.FEDORA_SHA,
                                    directories=True, owner=(1000, 1000))
    files, report = plan(base, reference)
    output = Path(output)
    if output.exists() or output.is_symlink():
        raise ValueError('output already exists')
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    target = output/'sensor-assets.tar.gz'
    with target.open('xb') as stream:
        target.chmod(0o600)
        with gzip.GzipFile(fileobj=stream, filename='', mode='wb', mtime=0) as zipped:
            with tarfile.open(fileobj=zipped, mode='w') as archive:
                for name, entry in sorted(files.items()):
                    member = tarfile.TarInfo(name)
                    member.size, member.mode, member.mtime = len(entry['data']), entry['mode'], entry['mtime']
                    archive.addfile(member, io.BytesIO(entry['data']))
    output_sha = ARCHIVE.digest(target.read_bytes())
    if ARCHIVE.read_archive(target, output_sha) != files:
        raise ValueError('reopened profile differs')
    report.update(verdict='FEDORA_MTIME_CACHE_PROFILE_OFFLINE_NOT_DEPLOYABLE',
                  base_archive_sha256=BASE_SHA, fedora_archive_sha256=ARCHIVE.FEDORA_SHA,
                  archive_sha256=output_sha,
                  cache_before_sha256=ARCHIVE.digest(base[INPUTS.CACHE]['data']),
                  cache_after_sha256=ARCHIVE.digest(files[INPUTS.CACHE]['data']),
                  files_manifest={n:dict(bytes=len(e['data']), mode=e['mode'], mtime=e['mtime'],
                                         sha256=ARCHIVE.digest(e['data'])) for n,e in sorted(files.items())},
                  outstanding=['generated isolated cache/write evidence qualification',
                               'independent registration and fresh admission',
                               'single attributed boot and exact normal desktop restoration',
                               'actual SSC publication, accelerometer and orientation acceptance'])
    (output/'PROFILE.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', type=Path, required=True)
    parser.add_argument('--fedora', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = stage(args.base, args.fedora, args.output)
    print(json.dumps({k:result[k] for k in ('verdict','archive_sha256','unchanged_files','deployment_ready')}))
