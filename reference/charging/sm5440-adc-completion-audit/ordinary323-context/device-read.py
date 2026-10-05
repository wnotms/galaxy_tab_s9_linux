import gzip,hashlib,json,os,re,time
from pathlib import Path
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

print(json.dumps(capture({'boot_id': 'fca646a8-8cc0-405c-814d-36cde33baa9e', 'config': '31d5a9419dbe027e4c3d735a363b490c9484584152d22bb83eb990c092076132', 'notes': 'd8e5fcf394811878c0368d8bd1db461e79e29a2cf949dc493256924f464d51f9'}),indent=2))
