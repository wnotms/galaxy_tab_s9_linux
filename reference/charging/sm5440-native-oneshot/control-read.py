import os,time,json,gzip,hashlib
from pathlib import Path
p=Path
expected=('fca646a8-8cc0-405c-814d-36cde33baa9e','31d5a9419dbe027e4c3d735a363b490c9484584152d22bb83eb990c092076132','d8e5fcf394811878c0368d8bd1db461e79e29a2cf949dc493256924f464d51f9')
def ident():return (p('/proc/sys/kernel/random/boot_id').read_text().strip(),hashlib.sha256(gzip.decompress(p('/proc/config.gz').read_bytes())).hexdigest(),hashlib.sha256(p('/sys/kernel/notes').read_bytes()).hexdigest())
assert ident()==expected
assert 'lpcharge=1' not in p('/proc/cmdline').read_text()
fd=os.open('/sys/kernel/debug/regmap/0-0063/registers',os.O_RDONLY)
rows=[]
try:
 for i in range(32):
  before=time.clock_gettime_ns(time.CLOCK_BOOTTIME)
  a=os.pread(fd,7,0x1c*7).decode();snap=p('/sys/kernel/debug/sm5440-0-0063/snapshot').read_text();b=os.pread(fd,7,0x1c*7).decode()
  rows.append(dict(before_ns=before,after_ns=time.clock_gettime_ns(time.CLOCK_BOOTTIME),control_before=a,control_after=b,snapshot=snap))
  time.sleep(.04)
finally:os.close(fd)
assert ident()==expected
print(json.dumps(dict(identity=expected,rows=rows,device_writes=False,INT_read=False,ADC_started=False),indent=2))
