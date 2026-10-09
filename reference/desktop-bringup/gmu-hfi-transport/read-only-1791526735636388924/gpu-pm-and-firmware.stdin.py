from pathlib import Path
import json,time,hashlib,gzip
root=Path('/')
boot=(root/'proc/sys/kernel/random/boot_id').read_text().strip()
assert (root/'etc/machine-id').read_text().strip()=='3c2a1b8f2d624db4b5ffdc836050fcf6'
assert hashlib.sha256(gzip.decompress((root/'proc/config.gz').read_bytes())).hexdigest()=='51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a'
assert hashlib.sha256((root/'sys/kernel/notes').read_bytes()).hexdigest()=='03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'
def sample():
 d={'boot_id':(root/'proc/sys/kernel/random/boot_id').read_text().strip(),'monotonic':time.monotonic(),'power':{},'devfreq':{}}
 assert d['boot_id']==boot
 for node in ('3d00000.gpu','3d6a000.gmu'):
  p=root/'sys/bus/platform/devices'/node/'power'
  d['power'][node]={n:(p/n).read_text().strip() for n in ('runtime_status','control','runtime_suspended_time','runtime_active_time') if (p/n).exists()}
 for p in (root/'sys/class/devfreq').glob('*gpu*'):
  d['devfreq'][p.name]={n:(p/n).read_text().strip() for n in ('governor','cur_freq','available_frequencies','trans_stat') if (p/n).exists()}
 return d
before=sample();time.sleep(15);after=sample()
fw={}
for n in ('a740_sqe.fw','gmu_gen70200.bin','a740_zap.mdt','a740_zap.mbn'):
 p=root/'lib/firmware/qcom'/n
 if p.exists():fw[n]={'target':str(p.resolve()),'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
print(json.dumps({'before':before,'after':after,'firmware':fw,'battery':(root/'sys/class/power_supply/sm5714-battery/uevent').read_text()}))
