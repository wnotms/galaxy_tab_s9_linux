import json,os,subprocess
from pathlib import Path

def read(path):
 try:return Path(path).read_text().strip()
 except OSError as e:return {'error':str(e)}
report={'boot_id':read('/proc/sys/kernel/random/boot_id'),'uname':list(os.uname()),'uptime':read('/proc/uptime'),'mounts':read('/proc/mounts'),'adsp_state':read('/sys/class/remoteproc/remoteproc0/state')}
paths=['/run/gts9-gpu-fw-source','/vendor/firmware_mnt','/mnt/vendor/persist','/usr/share/qcom','/lib/firmware/qcom/sm8550']
report['source_roots']={p:(os.listdir(p)[:80] if os.path.isdir(p) else None) for p in paths}
for name,path in [('capacity','capacity'),('temp','temp'),('status','status')]:report[name]=read('/sys/class/power_supply/sm5714-battery/'+path)
result=subprocess.run(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${Architecture}\t${db:Status-Status}\n','libglib2.0-0t64','libqmi-glib5','libprotobuf-c1','libgudev-1.0-0','libpolkit-gobject-1-0','libqrtr1','liblzma5','libc6','iio-sensor-proxy','libssc2','pd-mapper'],capture_output=True,text=True)
report['packages']={'stdout':result.stdout,'stderr':result.stderr,'returncode':result.returncode}
print(json.dumps(report,indent=2))
