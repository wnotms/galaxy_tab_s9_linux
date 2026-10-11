#!/usr/bin/env python3
"""Read-only comparison of the qualified X710 sensor input archives.

Reports cache, calibration, metadata and SoC differences separately. Does not
extract files, stage a profile, reset a registry or replace physical identity.
"""
import argparse
import importlib.util
import json
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    'sensor_input_archive', Path(__file__).with_name('fedora_adsp_profile.py'))
ARCHIVE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ARCHIVE)
PREFIX = 'usr/share/qcom/sm8550/Samsung/gts9wifi/'
CONFIG = PREFIX + 'sensors/config/'
CACHE = PREFIX + 'sensors/registry/sns_reg_config'


def strict_json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError('duplicate JSON key')
            result[key] = value
        return result

    def constant(value):
        raise ValueError('nonfinite JSON constant: ' + value)

    return json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)


def fields(before, after, path=()):
    """Retain exact JSON scalar changes; do not reinterpret vendor strings."""
    if isinstance(before, dict) and isinstance(after, dict):
        result = []
        for key in sorted(before.keys() | after.keys()):
            child = path + (key,)
            if key not in before or key not in after:
                result.append(dict(path=list(child), before_present=key in before,
                                   after_present=key in after,
                                   before=before.get(key), after=after.get(key)))
            else:
                result.extend(fields(before[key], after[key], child))
        return result
    if type(before) is type(after) and before == after:
        return []
    return [dict(path=list(path), before_present=True, after_present=True,
                 before=before, after=after)]


def category(name):
    rel = name.removeprefix(PREFIX)
    if rel.startswith('socinfo/'):
        return 'identity-reference-not-device-measurement'
    if '.fac_cal' in rel or '.placement' in rel or 'gyro_cal_persist' in rel or 'gyro_cal_table' in rel:
        return 'calibration-or-placement-preserve-device'
    if '.volatile' in rel:
        return 'volatile-cache-not-hardware-policy'
    if name == CACHE:
        return 'config-mtime-cache'
    if rel.startswith('sensors/registry/'):
        return 'other-registry-input'
    if rel.startswith('sensors/config/'):
        return 'sensor-config'
    if rel.startswith('dsp/'):
        return 'dsp-library'
    return 'other-input'


def cache_map(files):
    try:
        doc = strict_json(files[CACHE]['data'])
    except (KeyError, ValueError, UnicodeError) as exc:
        raise ValueError('invalid config mtime cache') from exc
    if not isinstance(doc, dict) or set(doc) != {'sns_reg_config'}:
        raise ValueError('config mtime cache schema')
    group = doc['sns_reg_config']
    configs = {n.removeprefix(CONFIG): e for n, e in files.items() if n.startswith(CONFIG)}
    expected = {'/vendor/etc/sensors/config/' + n for n in configs}
    if not isinstance(group, dict) or set(group) != expected | {'owner'} or group['owner'] != 'NA':
        raise ValueError('config mtime cache coverage')
    rows = []
    for name in sorted(configs):
        key = '/vendor/etc/sensors/config/' + name
        entry = group[key]
        if (not isinstance(entry, dict) or set(entry) != {'type', 'ver', 'data'}
                or entry['type'] != 'int' or entry['ver'] != '0'
                or not isinstance(entry['data'], str) or not entry['data'].isascii()
                or not entry['data'].isdigit()):
            raise ValueError('config mtime cache entry')
        rows.append(dict(path=key, cache_seconds=int(entry['data']),
                         archive_mtime=configs[name]['mtime'],
                         cache_matches_archive=int(entry['data']) == configs[name]['mtime']))
    if not rows:
        raise ValueError('empty config mtime cache')
    return rows


def compare(current, fedora):
    left = {n: e for n, e in current.items() if n.startswith(PREFIX)}
    right = {n: e for n, e in fedora.items() if n.startswith(PREFIX)}
    configs = {n for n in left if n.startswith(CONFIG)}
    if len(configs) != 35 or configs != {n for n in right if n.startswith(CONFIG)}:
        raise ValueError('complete same 35 config inputs required')
    markers = [PREFIX + 'sensors/sns_reg.conf', PREFIX + 'sensors/sns_reg_version']
    if any(n not in left or n not in right for n in markers):
        raise ValueError('missing registry version/config marker')
    rows = []
    for name in sorted(left.keys() | right.keys()):
        a, b = left.get(name), right.get(name)
        row = dict(path=name, category=category(name), current_present=a is not None,
                   fedora_present=b is not None)
        for label, entry in (('current', a), ('fedora', b)):
            row[label] = None if entry is None else dict(
                sha256=ARCHIVE.digest(entry['data']), bytes=len(entry['data']),
                mtime=entry['mtime'], mode=entry['mode'])
        if a is None or b is None:
            row['comparison'] = 'member-set-difference'
        elif a['data'] == b['data']:
            row['comparison'] = 'bytes-equal'
        else:
            row['comparison'] = 'bytes-different'
            # Nonstandard vendor JSON is retained as a raw difference. Never
            # silently repair it or interpret unavailable data as equivalent.
            if '/sensors/registry/' in name:
                try:
                    changes = fields(strict_json(a['data']), strict_json(b['data']))
                    row.update(strict_json_comparable=True, json_fields=changes,
                               json_equal=not changes)
                except (ValueError, UnicodeError):
                    row.update(strict_json_comparable=False, json_equal=None)
        rows.append(row)
    before_cache, after_cache = cache_map(left), cache_map(right)
    return dict(verdict='FEDORA_SENSOR_INPUT_DIFFERENCES_RECORDED_NOT_DEPLOYED',
                device_operations=False, registry_reset_performed=False,
                extraction_performed=False, deployment_ready=False,
                SSC_rootcause_proved=False, DSP_reparse_observed=False,
                config_count=35,
                all_config_bytes_equal=all(left[n]['data'] == right[n]['data'] for n in configs),
                registry_markers_equal=all(left[n]['data'] == right[n]['data'] for n in markers),
                current_mtime_cache=before_cache, fedora_mtime_cache=after_cache,
                rows=rows)


def audit(current_path, fedora_path):
    current = ARCHIVE.read_archive(current_path, ARCHIVE.BASE_SHA)
    fedora = ARCHIVE.read_archive(fedora_path, ARCHIVE.FEDORA_SHA,
                                directories=True, owner=(1000, 1000))
    result = compare(current, fedora)
    result.update(current_archive_sha256=ARCHIVE.BASE_SHA,
                  fedora_archive_sha256=ARCHIVE.FEDORA_SHA,
                  fedora_release_url=ARCHIVE.FEDORA_URL)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--current', type=Path, required=True)
    parser.add_argument('--fedora', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.current, args.fedora), indent=2, sort_keys=True))
