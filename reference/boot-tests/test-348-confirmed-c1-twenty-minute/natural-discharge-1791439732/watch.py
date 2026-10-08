#!/usr/bin/env python3
"""One-time read-only preparation observation; no charging or device writes."""
from pathlib import Path
import importlib.util,json,time,os,shlex
D=Path(__file__).resolve().parent;R=D.parent
spec=importlib.util.spec_from_file_location('natural348',R/'host_flow.py')
f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f);f.configure()
f.verify_inputs(require_push=True)
rec=f.p.Recorder(D/'raw');BOOT='be1baaaa47fc41f582558f7092c01653'
CODE="""from pathlib import Path
import json
b=Path('/sys/class/power_supply/sm5714-battery');u=Path('/sys/class/power_supply/sm5714-usb')
boot=Path('/proc/sys/kernel/random/boot_id')
a=boot.read_text().strip().replace('-','')
s={k:(b/k).read_text().strip() for k in ('status','health','present','capacity','voltage_now','current_now','temp')}
s.update(boot_id=a,boot_after=boot.read_text().strip().replace('-',''),online=(u/'online').read_text().strip())
print(json.dumps(s))
"""
started=time.monotonic();count=0
f.write(D/'handle.json',dict(pid=os.getpid(),purpose='read-only natural discharge',owner_reply='已拔线',target_soc=58,max_seconds=21600,interval_seconds=60,boot_id=BOOT,charging_operations=False))
try:
 while True:
  raw,_=f.wifi_command(rec,'sample-%04d'%count,'10.175.236.175','python3 -c '+shlex.quote(CODE))
  s=json.loads(raw);s.update(host_epoch=time.time(),elapsed_seconds=time.monotonic()-started)
  with (D/'samples.jsonl').open('a') as out:out.write(json.dumps(s)+'\n')
  count+=1
  if s['boot_id']!=BOOT or s['boot_after']!=BOOT:raise ValueError('boot changed')
  if s['online']!='0' or s['status']!='Discharging' or int(s['current_now'])>=0:raise ValueError('USB/charging state is not natural discharge')
  if s['health']!='Good' or s['present']!='1' or not 0<int(s['capacity'])<=100 or not 0<int(s['temp'])<420 or not 3400000<=int(s['voltage_now'])<=4500000:raise ValueError('invalid/unhealthy battery telemetry')
  f.write(D/'latest.json',s)
  if count==1 or count%10==0:print(json.dumps(s),flush=True)
  if int(s['capacity'])<=58:
   f.write(D/'summary.json',dict(verdict='NATURAL_HEADROOM_READY_FOR_FRESH_PC_PREFLIGHT',samples=count,final=s,charging_operations=False));break
  if time.monotonic()-started>=21600:
   f.write(D/'summary.json',dict(verdict='NATURAL_DISCHARGE_OBSERVATION_LIMIT',samples=count,final=s,ready=False,charging_operations=False));break
  time.sleep(60)
except Exception as exc:
 f.write(D/'summary.json',dict(verdict='STOP_READONLY_PREPARATION_OBSERVER',error=repr(exc),samples=count,charging_operations=False,candidate_attempt_consumed=False));raise
finally:
 f.write(D/'terminal.json',dict(pid=os.getpid(),terminal=True,elapsed_seconds=time.monotonic()-started))
