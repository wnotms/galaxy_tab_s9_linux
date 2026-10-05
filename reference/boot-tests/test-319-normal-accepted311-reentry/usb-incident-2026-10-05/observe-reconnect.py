#!/usr/bin/env python3
"""Read-only bounded USB transition capture; never reset services or hardware."""
import concurrent.futures
import json
from pathlib import Path
import subprocess
import time

R=Path(__file__).resolve().parent
c=json.loads((R.parent.parent/'test-318-off-continuous-adc-timing/maintenance-2026-10-05/context.json').read_text())
ssh=['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=3','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+c['trust'],'-o','HostKeyAlias=gts9-maintenance318','root@'+c['wifi']]
cmd='echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@udc; cat /sys/class/udc/a600000.usb/state /sys/class/udc/a600000.usb/current_speed; echo @@carrier; cat /sys/class/net/usb0/carrier; echo @@usb; cat /sys/class/power_supply/sm5714-usb/uevent; echo @@roles; cat /sys/class/typec/port0/power_role /sys/class/typec/port0/data_role; echo @@boot-end; cat /proc/sys/kernel/random/boot_id'
adb=['/mnt/d/android/platform-tools/adb.exe','devices','-l']
def capture(argv):
 try:
  p=subprocess.run(argv,capture_output=True,timeout=6)
  return dict(returncode=p.returncode,stdout=p.stdout.decode(errors='replace'),stderr=p.stderr.decode(errors='replace'))
 except subprocess.TimeoutExpired as e:
  return dict(returncode='timeout',stdout=(e.stdout or b'').decode(errors='replace'),stderr=(e.stderr or b'').decode(errors='replace'))
start=time.monotonic();previous=None;seen_off=False;verdict='BOUNDED_WINDOW_ENDED_NO_CONFIRMED_RECOVERY'
with (R/'reconnect-samples.jsonl').open('x') as log, concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
 while time.monotonic()-start<180:
  a=pool.submit(capture,ssh+[cmd]);b=pool.submit(capture,adb)
  row=dict(epoch=time.time(),elapsed_seconds=time.monotonic()-start,device=a.result(),adb=b.result())
  log.write(json.dumps(row)+'\n');log.flush()
  raw=row['device']['stdout']; lines=raw.splitlines()
  if row['device']['returncode']!=0 or lines.count(c['boot_id'])!=2:
   verdict='DEVICE_TRANSPORT_OR_BOOT_CHANGED';print(verdict,flush=True);break
  sections={}
  for line in lines:
   if line.startswith('@@'):key=line[2:];sections[key]=[]
   else:sections[key].append(line)
  state=(tuple(sections['udc']),tuple(sections['carrier']),row['adb']['stdout'].strip())
  if state!=previous:print(json.dumps(dict(elapsed=row['elapsed_seconds'],state=state)),flush=True);previous=state
  if sections['udc'][0]=='not attached':seen_off=True
  if seen_off and 'gts9wifi-0001' in row['adb']['stdout'] and '\tdevice ' in row['adb']['stdout']:
   verdict='ADB_ENUMERATED_AFTER_OBSERVED_DISCONNECT';break
  time.sleep(2)
(R/'reconnect-observer-summary.json').write_text(json.dumps(dict(verdict=verdict,observed_disconnect=seen_off,elapsed_seconds=time.monotonic()-start,device_mutation=False),indent=2)+'\n')
print(verdict,flush=True)
