#!/usr/bin/env python3
"""Read native auxiliary PD-mapper binding; never start DSPs or send QMI calls."""
import argparse
import json
from pathlib import Path
import re
from uuid import UUID

# Pinned Linux 7.2-rc3: drivers/soc/qcom/qcom_pd_mapper.c + its Makefile.
# __auxiliary_driver_register() prefixes KBUILD_MODNAME to .name.
DRIVER = 'qcom_pd_mapper.qcom-pdm-mapper'
DEVICE = re.compile(r'qcom_common\.pd-mapper\.[0-9]+\Z')


def boot_id(root):
    return str(UUID((root / 'proc/sys/kernel/random/boot_id').read_text().strip()))


def snapshot(root=Path('/'), *, expected_boot):
    root = Path(root).resolve()
    before = boot_id(root)
    if before != str(UUID(expected_boot)):
        raise ValueError('boot changed before mapper snapshot')
    bus = root / 'sys/bus/auxiliary'
    driver = bus / 'drivers' / DRIVER
    rows = []
    for device in sorted((bus / 'devices').glob('qcom_common.pd-mapper*')):
        if not DEVICE.fullmatch(device.name) or not device.is_dir():
            raise ValueError('unexpected PD-mapper device entry: ' + device.name)
        link = device / 'driver'
        target = None
        if link.is_symlink():
            target = link.resolve(strict=True)
        elif link.exists():
            raise ValueError('driver binding is not a sysfs symlink')
        modalias = device / 'modalias'
        rows.append(dict(name=device.name, device_path=str(device.resolve(strict=True)),
                         driver_path=str(target) if target else None,
                         modalias=modalias.read_text().strip() if modalias.exists() else None,
                         bound=target == driver.resolve(strict=True) if driver.is_dir() else False))
    if boot_id(root) != before:
        raise ValueError('boot changed during mapper snapshot')
    if rows and all(row['bound'] for row in rows):
        state = 'bound'
    elif any(row['driver_path'] for row in rows):
        state = 'unexpected-binding'
    elif rows:
        state = 'unbound'
    else:
        state = 'no-device'
    return dict(boot_id=before, bus='auxiliary', driver=DRIVER,
                driver_registered=driver.is_dir(), devices=rows, binding_state=state,
                service_response_verified=False, sensor_discovery_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--boot-id', required=True)
    args = parser.parse_args()
    try:
        result = snapshot(expected_boot=args.boot_id)
    except (OSError, ValueError) as error:
        print(json.dumps(dict(error=str(error), binding_state='evidence-error')))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result['binding_state'] == 'bound' else 2


if __name__ == '__main__':
    raise SystemExit(main())
