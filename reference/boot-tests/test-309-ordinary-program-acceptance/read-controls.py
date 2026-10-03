#!/usr/bin/env python3
"""Seven atomic pointer/read transfers; no configuration-data or INT access."""
import ctypes as c
import fcntl
import json
import os
from pathlib import Path

REGISTERS = (0x0d, 0x0e, 0x13, 0x14, 0x15, 0x18, 0x1a)


class Msg(c.Structure):
    _fields_ = [('addr', c.c_uint16), ('flags', c.c_uint16), ('length', c.c_uint16),
                ('buf', c.POINTER(c.c_uint8))]


class Transfer(c.Structure):
    _fields_ = [('msgs', c.POINTER(Msg)), ('nmsgs', c.c_uint32)]


def capture():
    boot = Path('/proc/sys/kernel/random/boot_id')
    before = boot.read_text().strip()
    matches = list(Path('/sys/bus/i2c/devices').glob('*-0049'))
    if len(matches) != 1:
        raise ValueError('unique SM5714 charger I2C node required')
    node = matches[0]
    if node.resolve() != Path('/sys/class/power_supply/sm5714-battery/device').resolve():
        raise ValueError('battery/I2C provider mismatch')
    if (node / 'driver').resolve().name != 'sm5714-battery':
        raise ValueError('unexpected bound driver')
    if b'siliconmitus,sm5714' not in (node / 'of_node/compatible').read_bytes().split(b'\0'):
        raise ValueError('unexpected charger compatible')
    bus = int(node.name.split('-')[0])
    fd = os.open('/dev/i2c-' + str(bus), os.O_RDWR)
    try:
        result = {}
        for reg in REGISTERS:
            pointer = (c.c_uint8 * 1)(reg)
            output = (c.c_uint8 * 1)()
            messages = (Msg * 2)(Msg(0x49, 0, 1, pointer), Msg(0x49, 1, 1, output))
            packet = Transfer(messages, 2)
            fcntl.ioctl(fd, 0x0707, packet)
            result[f'0x{reg:02x}'] = f'0x{output[0]:02x}'
    finally:
        os.close(fd)
    return dict(boot_id_before=before, boot_id_after=boot.read_text().strip(),
                bound_driver='sm5714-battery', i2c_node=node.name,
                stable_registers=result, register_data_writes=False,
                only_atomic_pointer_reads=True)


if __name__ == '__main__':
    print(json.dumps(capture()))
