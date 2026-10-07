#!/usr/bin/env python3
"""Read only stable CNTL5; atomic pointer/read, no INT/ADC/config writes."""
import ctypes as c
import fcntl,json,os
from pathlib import Path
class Msg(c.Structure):
    _fields_=[('addr',c.c_uint16),('flags',c.c_uint16),('length',c.c_uint16),('buf',c.POINTER(c.c_uint8))]
class Transfer(c.Structure):
    _fields_=[('msgs',c.POINTER(Msg)),('nmsgs',c.c_uint32)]
def capture():
    boot=Path('/proc/sys/kernel/random/boot_id');before=boot.read_text().strip()
    node=Path('/sys/bus/i2c/devices/0-0063').resolve(strict=True)
    driver=(node/'driver').resolve(strict=True).name
    if driver not in ('sm5440-passive','sm5440-fedora'):raise ValueError('unknown pump provider')
    if b'siliconmitus,sm5440' not in (node/'of_node/compatible').read_bytes().split(b'\0'):raise ValueError('pump compatible')
    fd=os.open('/dev/i2c-0',os.O_RDWR)
    try:
        pointer=(c.c_uint8*1)(0x10);out=(c.c_uint8*1)()
        messages=(Msg*2)(Msg(0x63,0,1,pointer),Msg(0x63,1,1,out))
        packet=Transfer(messages,2);fcntl.ioctl(fd,0x0707,packet)
    finally:os.close(fd)
    return dict(boot_before=before,boot_after=boot.read_text().strip(),driver=driver,register=0x10,value=out[0],config_data_written=False)
if __name__=='__main__':print(json.dumps(capture()))
