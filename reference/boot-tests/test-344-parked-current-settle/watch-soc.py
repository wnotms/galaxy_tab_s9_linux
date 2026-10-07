#!/usr/bin/env python3
"""Finite read-only natural-discharge watch; no stage/reboot/PD/pump action."""
import datetime,importlib.util,json,time
from pathlib import Path
R=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('watch344_flow',R/'host_flow.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
EXPECTED='dc8442f1b39f48f8855d8918979be1af'
COMMAND=('cat /proc/sys/kernel/random/boot_id; '
 'cat /sys/class/power_supply/sm5714-battery/uevent; '
 'cat /sys/class/power_supply/sm5714-usb/uevent; '
 'cat /sys/module/sm5440_fedora/parameters/direct_charge; '
 'cat /proc/sys/kernel/random/boot_id')

def run():
 f.verify_inputs(require_push=True)
 rec=f.p.Recorder(R/'natural-discharge-watch-01')
 if (rec.folder/'status.json').exists():raise RuntimeError('watch already started; do not overwrite')
 began=time.monotonic();result={'verdict':'WATCHING','device_writes':False}
 try:
  for index in range(30):
   raw,_=f.wifi_command(rec,'sample-%02d'%index,'10.175.236.14',COMMAND)
   lines=[x for x in raw.splitlines() if x];d=dict(x.split('=',1) for x in lines if '=' in x)
   if lines[0].replace('-','')!=EXPECTED or lines[-1]!=lines[0] or lines[-2]!='N':raise RuntimeError('boot/default identity changed')
   state=dict(timestamp_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),boot_id=EXPECTED,soc=int(d['POWER_SUPPLY_CAPACITY']),temp_decic=int(d['POWER_SUPPLY_TEMP']),voltage_uv=int(d['POWER_SUPPLY_VOLTAGE_NOW']),current_ua=int(d['POWER_SUPPLY_CURRENT_NOW']),usb_online=d['POWER_SUPPLY_ONLINE']=='1',direct=False,device_writes=False)
   if state['usb_online'] or state['current_ua']>=0:raise RuntimeError('natural discharge/power path changed')
   if d['POWER_SUPPLY_HEALTH']!='Good' or d['POWER_SUPPLY_PRESENT']!='1' or state['soc']<20:raise RuntimeError('pack baseline changed')
   if not 200<=state['temp_decic']<380 or not 3500000<=state['voltage_uv']<4300000:raise RuntimeError('preparation pack range changed')
   result=dict(state,verdict='READY_FOR_OWNER_PC_HANDOFF' if state['soc']<=75 else 'WATCHING',elapsed_seconds=round(time.monotonic()-began,3))
   f.write(rec.folder/'status.json',result);print(json.dumps(result),flush=True)
   if state['soc']<=75:return result
   time.sleep(30)
  result.update(verdict='BOUNDED_WATCH_EXPIRED',elapsed_seconds=round(time.monotonic()-began,3))
 except Exception as exc:
  result.update(verdict='READONLY_WATCH_STOP',error=repr(exc),device_writes=False)
  raise
 finally:
  f.write(rec.folder/'status.json',result)
 return result

if __name__=='__main__':run()
