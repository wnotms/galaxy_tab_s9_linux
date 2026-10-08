#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-2.0-only
"""Translate a captured mainline SoCinfo snapshot to Samsung SSC file values.

Host-only: reads JSON, writes a new output directory; never reads device sysfs.
Hardware names/IDs follow Samsung msm-kernel/drivers/soc/qcom/socinfo.c,
HW_PLATFORM_* tables and msm_get_{hw_platform,platform_subtype*} functions.
Numeric fields are the same SMEM fields exposed by mainline qcom_socinfo.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

PLATFORMS = {0:'Unknown', 1:'Surf', 2:'FFA', 3:'Fluid', 4:'SVLTE_FFA',
             5:'SLVTE_SURF', 7:'MDM_MTP_NO_DISPLAY', 8:'MTP', 9:'Liquid',
             10:'Dragon', 11:'QRD', 13:'HRD', 14:'DTV', 21:'RCM', 23:'STP',
             24:'SBC', 25:'ADP', 31:'HDK', 32:'IOT', 33:'ATP', 34:'IDP',
             36:'WDP', 39:'X100'}
SUBTYPES = {0:'Unknown', 1:'charm', 2:'strange', 3:'strange_2a'}
QRD_SUBTYPES = {0:'QRD', 1:'SKUAA', 2:'SKUF', 3:'SKUAB', 5:'SKUG'}


def uint32(value, name, hexadecimal=False):
    if not isinstance(value, str) or not re.fullmatch(
            r'(?:0x[0-9a-fA-F]+|[0-9]+)' if hexadecimal else r'[0-9]+', value.strip()):
        raise ValueError('invalid unsigned field: ' + name)
    text = value.strip()
    number = int(text, 16 if hexadecimal and text.startswith('0x') else 10)
    if number > 0xffffffff:
        raise ValueError('unsigned field overflow: ' + name)
    return number


def translate(snapshot):
    if (not isinstance(snapshot, dict) or
        not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', snapshot.get('boot_id', '')) or
        snapshot.get('family') != 'Snapdragon' or snapshot.get('machine') != 'SM8550'):
        raise ValueError('unqualified X710 SoC snapshot identity')
    fields = ('soc_id', 'hardware_platform', 'hardware_platform_subtype', 'platform_version')
    if any(name not in snapshot for name in fields) or 'info_fmt' not in snapshot:
        raise ValueError('missing native SoCinfo field')
    values = {name:uint32(snapshot[name], name) for name in fields}
    fmt = uint32(snapshot['info_fmt'], 'info_fmt', hexadecimal=True)
    # Mainline 7.2-rc3's debugfs switch covers major 0 through format 23;
    # subtype first appears at 0.6. Reject unsupported/partial snapshots.
    if not 6 <= fmt <= 23 or values['soc_id'] != 519:
        raise ValueError('unsupported SMEM format or SoC ID')
    platform = values['hardware_platform']
    if platform not in PLATFORMS or platform == 0:
        raise ValueError('unknown hardware platform')
    subtype = values['hardware_platform_subtype']
    table = QRD_SUBTYPES if platform == 11 else SUBTYPES
    if subtype not in table:
        raise ValueError('unknown hardware subtype')
    return {'soc_id':str(values['soc_id'])+'\n',
            'hw_platform':PLATFORMS[platform]+'\n',
            'platform_subtype':table[subtype]+'\n',
            'platform_subtype_id':str(subtype)+'\n',
            'platform_version':str(values['platform_version'])+'\n'}


def stage(snapshot, output):
    values = translate(snapshot)
    output.mkdir(parents=True, exist_ok=False)
    for name, value in values.items():
        (output/name).write_text(value)
    result = dict(verdict='OFFLINE_SOCINFO_MAPPING_NOT_DEPLOYED', device_operations=False,
                  physical_identity_verified=False, boot_id=snapshot['boot_id'],
                  snapshot=snapshot, files={name:hashlib.sha256(value.encode()).hexdigest()
                                           for name,value in values.items()})
    (output/'MAPPING.json').write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(stage(json.loads(args.snapshot.read_text()), args.output), indent=2))
