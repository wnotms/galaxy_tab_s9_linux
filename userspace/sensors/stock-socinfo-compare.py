#!/usr/bin/env python3
"""Pure comparison of boot-bound recovery sysfs bytes and native SoC mapping.

No device access or output files at import. Recovery fields are hex-encoded by
od so ADB's CRLF conversion cannot alter the bytes being compared.
"""
import importlib.util
from pathlib import Path
import re
from uuid import UUID

FIELDS = ('soc_id', 'hw_platform', 'platform_subtype',
          'platform_subtype_id', 'platform_version')
SPEC = importlib.util.spec_from_file_location('stock_socinfo_native',
                                            Path(__file__).with_name('map-socinfo.py'))
MAPPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MAPPER)

# These are the actual Samsung socinfo.c attributes, not debugfs guesses.
COMMAND = '''set -e
printf 'begin\t'; cat /proc/sys/kernel/random/boot_id
printf 'device\t'; getprop ro.product.device
printf 'kernel\t'; uname -r
printf 'uid\t'; id -u
for name in soc_id hw_platform platform_subtype platform_subtype_id platform_version; do
    test -f /sys/devices/soc0/$name
    printf '%s\t' "$name"
    od -An -v -tx1 /sys/devices/soc0/$name | tr -d ' \n'
    printf '\n'
done
printf 'end\t'; cat /proc/sys/kernel/random/boot_id
'''


def parse(raw, expected_boot):
    expected_boot = str(UUID(expected_boot))
    rows = {}
    for line in raw.replace('\r', '').splitlines():
        cells = line.split('\t')
        if len(cells) != 2 or cells[0] in rows:
            raise ValueError('malformed/duplicate stock row')
        rows[cells[0]] = cells[1]
    if set(rows) != set(FIELDS) | {'begin', 'end', 'device', 'kernel', 'uid'}:
        raise ValueError('missing/extra stock row')
    if (str(UUID(rows['begin'])) != expected_boot or
            str(UUID(rows['end'])) != expected_boot):
        raise ValueError('mixed or unexpected recovery boot')
    if (rows['device'], rows['kernel'], rows['uid']) != (
            'gts9wifi', '5.15.94-Foldiby-+', '0'):
        raise ValueError('not qualified X710 root recovery')
    values = {}
    for name in FIELDS:
        encoded = rows[name]
        if not re.fullmatch(r'(?:[0-9a-f]{2}){1,64}', encoded):
            raise ValueError('invalid/bounded stock hex: ' + name)
        value = bytes.fromhex(encoded)
        if not value.endswith(b'\n') or b'\n' in value[:-1] or b'\0' in value:
            raise ValueError('not one stock sysfs line: ' + name)
        values[name] = value.decode('ascii')
    for name in ('soc_id', 'platform_subtype_id', 'platform_version'):
        if not re.fullmatch(r'[0-9]+\n', values[name]):
            raise ValueError('invalid stock decimal: ' + name)
        if int(values[name]) > 0xffffffff:
            raise ValueError('stock decimal overflow: ' + name)
    for name in ('hw_platform', 'platform_subtype'):
        if not re.fullmatch(r'[A-Za-z0-9_]+\n', values[name]):
            raise ValueError('invalid stock name: ' + name)
    if values['soc_id'] != '519\n':
        raise ValueError('not SM8550 stock identity')
    return dict(boot_id=expected_boot, values=values,
                source='X710 TWRP Samsung socinfo sysfs; recovery, not Android boot')


def compare(raw, recovery_boot, native):
    expected = MAPPER.translate(native)
    if UUID(recovery_boot) == UUID(native['boot_id']):
        raise ValueError('recovery boot must differ from native boot')
    observed = parse(raw, recovery_boot)
    differences = {name: dict(native=expected[name], stock=observed['values'][name])
                   for name in FIELDS if expected[name] != observed['values'][name]}
    return dict(verdict='STOCK_SOCINFO_EXACT_MATCH' if not differences else
                'STOCK_SOCINFO_DIFFERS', native_boot_id=native['boot_id'],
                recovery_boot_id=observed['boot_id'], expected=expected,
                observed=observed['values'], differences=differences,
                source=observed['source'], SSC_verified=False,
                sensor_verified=False, rotation_verified=False)


def observe_then_return(observe, return_to_baseline):
    """One observation, mandatory return once; preserve both errors separately.

    Caller must establish a known, boot-bound recovery before entering here.
    A lost rescue transport is handled by the return callback's identity gate;
    this helper never authorizes a blind reboot or a second observation.
    """
    result = dict(observation=None, observation_error=None,
                  returned=None, return_error=None)
    try:
        result['observation'] = observe()
    except Exception as error:
        result['observation_error'] = str(error)
    try:
        result['returned'] = return_to_baseline()
    except Exception as error:
        result['return_error'] = str(error)
    return result
