import os,json,time,re,pathlib
base=pathlib.Path('/sys/kernel/debug/regmap/0-0063')
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='57535bed-a626-48d0-aaaa-3071ac8332e5',boot
ranges=(base/'range').read_text()
assert ranges=='0-2b\n',repr(ranges)
rows=[]
fd=os.open(base/'registers',os.O_RDONLY)
try:
 for name,reg in [('MODE_BEFORE',0x10),('CNTL1',0x0c),('CNTL2',0x0d),('CNTL3',0x0e),('CNTL4',0x0f),('CNTL5',0x10),('CNTL6',0x11),('CNTL7',0x12),('VBUSCNTL',0x13),('VBATCNTL',0x14),('VOUTCNTL',0x15),('IBUSCNTL',0x16),('PRTNCNTL',0x19),('THEMCNTL1',0x1a),('THEMCNTL2',0x1b),('ADCCNTL1',0x1c),('ADCCNTL2',0x1d),('DEVICEID',0x2b),('MODE_AFTER',0x10)]:
  start=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
  os.lseek(fd,reg*7,os.SEEK_SET)
  raw=os.read(fd,7).decode('ascii')
  end=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
  assert re.fullmatch(f'{reg:02x}: [0-9a-f]{{2}}\n',raw),repr(raw)
  value=int(raw[4:6],16)
  if reg==0x10: assert value&0x0c==0,raw
  rows.append(dict(name=name,register=reg,raw=raw,value=value,start_boottime_ns=start,end_boottime_ns=end))
finally: os.close(fd)
endboot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert endboot==boot
print(json.dumps(dict(boot_id=boot,range=ranges,registers=rows,battery=(pathlib.Path('/sys/class/power_supply/sm5714-battery/uevent').read_text())),indent=2))
