#!/usr/bin/env python3
"""Bounded read-only maintenance charging log; no test entry/flash authorization."""
import json
from pathlib import Path
import subprocess
import time

R=Path(__file__).resolve().parent
c=json.loads((R/'context.json').read_text())
command='set -e; echo @@boot; cat /proc/sys/kernel/random/boot_id; echo @@battery; cat /sys/class/power_supply/sm5714-battery/uevent; echo @@usb; cat /sys/class/power_supply/sm5714-usb/uevent; echo @@roles; cat /sys/class/typec/port0/power_role /sys/class/typec/port0/data_role; echo @@boot-end; cat /proc/sys/kernel/random/boot_id'
argv=['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+c['trust'],'-o','HostKeyAlias=gts9-maintenance318','root@'+c['wifi'],command]
(R/'observer-command.json').write_text(json.dumps(dict(argv=argv,window_seconds=1200,interval_seconds=30,timeout_seconds=8,physical_mutation=False,full_preflight=False),indent=2)+'\n')
started=time.monotonic(); verdict='MAINTENANCE_WINDOW_ENDED_BELOW_RESERVE'; previous=None; count=0
with (R/'samples.jsonl').open('x') as stream:
 while time.monotonic()-started<1200:
  count+=1; row=dict(index=count,host_started_epoch=time.time())
  try:
   p=subprocess.run(argv,capture_output=True,timeout=8)
   row.update(host_completed_epoch=time.time(),returncode=p.returncode,stdout=p.stdout.decode(),stderr=p.stderr.decode())
   if p.returncode:raise ValueError('authenticated Wi-Fi unavailable')
   sections={}
   for line in row['stdout'].splitlines():
    if line.startswith('@@'): key=line[2:]; sections[key]=[]
    else:sections[key].append(line)
   if sections['boot']!=[c['boot_id']] or sections['boot-end']!=sections['boot']:raise ValueError('maintenance boot changed')
   b=dict(line.split('=',1) for line in sections['battery'] if '=' in line)
   u=dict(line.split('=',1) for line in sections['usb'] if '=' in line)
   soc=int(b['POWER_SUPPLY_CAPACITY']);temp=int(b['POWER_SUPPLY_TEMP']);uv=int(b['POWER_SUPPLY_VOLTAGE_NOW']);ua=int(b['POWER_SUPPLY_CURRENT_NOW'])
   row['telemetry']=dict(soc=soc,temp_decic=temp,vbat_uv=uv,ibat_ua=ua,health=b['POWER_SUPPLY_HEALTH'],online=u['POWER_SUPPLY_ONLINE'],usb_type=u['POWER_SUPPLY_USB_TYPE'])
   if b['POWER_SUPPLY_HEALTH']!='Good' or b['POWER_SUPPLY_PRESENT']!='1' or temp>=380 or temp<200 or uv>=4300000 or uv<3500000 or soc<5 or soc>=80:raise ValueError('pack outside maintenance entry bounds')
   if sections['roles']!=['[sink]','[device]']:raise ValueError('unexpected role')
   state=(soc,row['telemetry']['online'],row['telemetry']['usb_type'],ua>0)
   if state!=previous:print(json.dumps(row['telemetry']),flush=True);previous=state
   if soc>=20:
    verdict='FLASH_RESERVE_OBSERVED_NEEDS_FRESH_PC_PREFLIGHT';row['reserve_observed']=True
    stream.write(json.dumps(row)+'\n');stream.flush();break
  except (ValueError,KeyError,subprocess.TimeoutExpired) as exc:
   row.update(error=str(exc),host_completed_epoch=time.time());verdict='MAINTENANCE_STOP_NO_MUTATION'
   stream.write(json.dumps(row)+'\n');stream.flush();break
  stream.write(json.dumps(row)+'\n');stream.flush();time.sleep(30)
result=dict(verdict=verdict,samples=count,elapsed_seconds=time.monotonic()-started,physical_mutation=False,full_preflight=False,flash=False,PPS=False,pump_ON=False)
(R/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result),flush=True)
