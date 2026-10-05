#!/usr/bin/env python3
"""Capture stable ADC controls/masks without starting or adopting a conversion."""
import argparse
import datetime
import gzip
import hashlib
import inspect
import json
import os
from pathlib import Path
import re
import subprocess
import time


def capture(request, root=Path('/')):
    """The same body runs on the device and against an offline filesystem fixture."""
    def read(name):
        return (root / name.lstrip('/')).read_bytes()

    def identity():
        boot = read('/proc/sys/kernel/random/boot_id').decode().strip()
        config = hashlib.sha256(gzip.decompress(read('/proc/config.gz'))).hexdigest()
        notes = hashlib.sha256(read('/sys/kernel/notes')).hexdigest()
        cmdline = read('/proc/cmdline').decode().strip()
        if (boot, config, notes) != (request['boot_id'], request['config'], request['notes']):
            raise ValueError('boot/config/notes mismatch; no register observation admitted')
        if re.search(r'(?:^|[\s.])lpcharge=1(?:\s|$)', cmdline):
            raise ValueError('lpcharge boot; normal context not admitted')
        return dict(boot_id=boot, config=config, notes=notes, cmdline=cmdline)

    first = identity()
    base = root / 'sys/kernel/debug/regmap/0-0063'
    if (base / 'range').read_bytes() != b'0-2b\n':
        raise ValueError('unexpected regmap range')
    rows = []
    # Samsung sm5440_charger.h: MSK1..4=04..07. Never read INT1..4 here.
    # pread requests exactly one ordinary register line; no full-regmap dump.
    fd = os.open(base / 'registers', os.O_RDONLY)
    try:
        for name, reg in [('MODE_BEFORE', 0x10), ('MSK1', 4), ('MSK2', 5),
                          ('MSK3', 6), ('MSK4', 7), ('ADCCNTL1', 0x1c),
                          ('ADCCNTL2', 0x1d), ('DEVICEID', 0x2b), ('MODE_AFTER', 0x10)]:
            start = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            raw = os.pread(fd, 7, reg * 7).decode('ascii')
            end = time.clock_gettime_ns(time.CLOCK_BOOTTIME)
            if not re.fullmatch(f'{reg:02x}: [0-9a-f]{{2}}\n', raw):
                raise ValueError('register line mismatch')
            value = int(raw[4:6], 16)
            if reg == 0x10 and value & 0x0c:
                raise ValueError('pump not OFF')
            if reg == 0x2b and value & 0xf != 1:
                raise ValueError('SM5440 device identity mismatch')
            if end < start:
                raise ValueError('observation clock regression')
            rows.append(dict(name=name, register=reg, value=value, raw=raw,
                             start_boottime_ns=start, end_boottime_ns=end))
    finally:
        os.close(fd)
    battery = read('/sys/class/power_supply/sm5714-battery/uevent').decode()
    usb = read('/sys/class/power_supply/sm5714-usb/uevent').decode()
    # This is the existing poller's cached snapshot, not a fresh ADC request.
    cached = read('/sys/kernel/debug/sm5440-0-0063/snapshot').decode()
    last = identity()
    if first != last:
        raise ValueError('identity changed across observation')
    masks = {row['name']: row['value'] for row in rows if row['name'].startswith('MSK')}
    return dict(schema='sm5440-adc-context-v1', identity=first, registers=rows,
                masks=masks, vendor_msk4=0xf8, matches_vendor_msk4=masks['MSK4'] == 0xf8,
                msk4_bit0_set=bool(masks['MSK4'] & 1), battery=battery, usb=usb,
                cached_snapshot=cached, adc_request_executed=False,
                read_to_clear_registers_read=False, device_writes=False,
                conversion_freshness_proven=False, calibration_proven=False,
                software_ocp_verified=False, pump_activation_granted=False)


def device_program(request):
    imports = 'import gzip,hashlib,json,os,re,time\nfrom pathlib import Path\n'
    return imports + inspect.getsource(capture) + '\nprint(json.dumps(capture(' + repr(request) + '),indent=2))\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', default='/mnt/d/android/platform-tools/adb.exe')
    parser.add_argument('--serial', default='gts9wifi-0001')
    parser.add_argument('--expected-boot-id', required=True)
    parser.add_argument('--expected-config', required=True)
    parser.add_argument('--expected-notes', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}', args.expected_boot_id):
        parser.error('expected boot ID must be a UUID')
    if not all(re.fullmatch(r'[0-9a-f]{64}', x) for x in [args.expected_config, args.expected_notes]):
        parser.error('expected identity hashes must be SHA256')
    args.output.mkdir(parents=True, exist_ok=False)
    request = dict(boot_id=args.expected_boot_id, config=args.expected_config, notes=args.expected_notes)
    source = device_program(request)
    (args.output / 'device-read.py').write_text(source)
    argv = [args.adb, '-s', args.serial, 'shell', 'python3', '-']
    started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    try:
        run = subprocess.run(argv, input=source.encode(), capture_output=True, timeout=12)
        rc, stdout, stderr = run.returncode, run.stdout, run.stderr
    except subprocess.TimeoutExpired as error:
        rc, stdout, stderr = 124, error.stdout or b'', (error.stderr or b'') + b'\nouter timeout\n'
    except OSError as error:
        rc, stdout, stderr = 127, b'', str(error).encode()
    (args.output / 'capture.txt').write_bytes(stdout)
    (args.output / 'capture.stderr').write_bytes(stderr)
    command = dict(argv=argv, started_utc=started,
                   ended_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   returncode=rc, device_writes=False)
    (args.output / 'command.json').write_text(json.dumps(command, indent=2) + '\n')
    valid = False
    if not rc:
        try:
            data = json.loads(stdout)
            valid = (data['schema'] == 'sm5440-adc-context-v1' and
                     all(data['identity'][key] == value for key, value in request.items()) and
                     not any(data[k] for k in ['device_writes', 'adc_request_executed',
                         'read_to_clear_registers_read', 'conversion_freshness_proven',
                         'calibration_proven', 'software_ocp_verified', 'pump_activation_granted']))
        except (ValueError, KeyError, TypeError):
            pass
    verdict = 'CONTEXT_CAPTURED_NOT_ADC_QUALIFIED' if valid else 'STOP_IDENTITY_OR_CAPTURE'
    (args.output / 'summary.json').write_text(json.dumps(dict(verdict=verdict,
        expected=request, command=command, device_writes=False), indent=2) + '\n')
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(args.output.iterdir()) if p.is_file()}
    (args.output / 'SHA256.json').write_text(json.dumps(hashes, indent=2) + '\n')
    print(verdict)
    return 0 if valid else 1


if __name__ == '__main__':
    raise SystemExit(main())
