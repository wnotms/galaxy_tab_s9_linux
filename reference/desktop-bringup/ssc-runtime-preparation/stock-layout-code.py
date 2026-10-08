import json,subprocess,os
from pathlib import Path
report={'boot_id':Path('/proc/sys/kernel/random/boot_id').read_text().strip(),'board_model':Path('/sys/firmware/devicetree/base/model').read_bytes().decode().rstrip(chr(0)),'board_compatible':Path('/sys/firmware/devicetree/base/compatible').read_bytes().decode().split(chr(0)),'partitions':{}}
for name in ['apnhlos','dsp','persist']:
 path=Path('/dev/disk/by-partlabel')/name
 result=subprocess.run(['blkid','-p','-o','export',str(path)],capture_output=True,text=True,timeout=5)
 report['partitions'][name]={'device':str(path.resolve()),'returncode':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
result=subprocess.run(['dpkg-query','-W','-f=${binary:Package}\t${Version}\t${db:Status-Status}\n','libqmi-proxy','libqrtr-glib0','libprotobuf-c1','libqrtr1','udev','systemd'],capture_output=True,text=True)
report['remaining_dependencies']={'stdout':result.stdout,'stderr':result.stderr,'returncode':result.returncode}
print(json.dumps(report,indent=2))
