import os,json,time,re,pathlib,subprocess
boot=pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()
assert boot=='ecaa3c64-5c69-4bbe-b755-1a2aff6a88ca',boot
base=pathlib.Path('/sys/kernel/debug/regmap/0-0063')
assert (base/'range').read_text()=='0-2b\n'
rows=[];fd=os.open(base/'registers',os.O_RDONLY)
try:
 for name,reg in [('MODE_BEFORE',0x10),('MSK1',4),('MSK2',5),('MSK3',6),('MSK4',7),('ADCCNTL1',0x1c),('ADCCNTL2',0x1d),('MODE_AFTER',0x10)]:
  start=time.clock_gettime_ns(time.CLOCK_BOOTTIME);os.lseek(fd,reg*7,os.SEEK_SET);raw=os.read(fd,7).decode();end=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
  assert re.fullmatch(f'{reg:02x}: [0-9a-f]{{2}}\n',raw),repr(raw)
  value=int(raw[4:6],16)
  if reg==0x10: assert not value&12
  rows.append(dict(name=name,register=reg,value=value,raw=raw,start_boottime_ns=start,end_boottime_ns=end))
finally: os.close(fd)
assert pathlib.Path('/proc/sys/kernel/random/boot_id').read_text().strip()==boot
print(json.dumps(dict(boot_id=boot,registers=rows,battery=pathlib.Path('/sys/class/power_supply/sm5714-battery/uevent').read_text(),usb=pathlib.Path('/sys/class/power_supply/sm5714-usb/uevent').read_text(),notes_sha256=subprocess.check_output(['sha256sum','/sys/kernel/notes'],text=True).strip()),indent=2))
