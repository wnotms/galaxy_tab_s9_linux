import sys,time,json,shlex
from pathlib import Path
sys.path.insert(0,'scripts')
import production_reboot_stability as p
import production_stability_evidence as e
import sm5714_fixed_charge_regression as f
from sm5440_passive_admission import startup_evidence
base=Path('reference/boot-tests/test-262-sm5714-fixed-charge-on-test260')
rec=p.Recorder(base/'unplug-attempt-02')
(rec.folder/'observer.py').write_bytes(Path(__file__).read_bytes())
boot='18bce160ddda4c5b9f27f8429f204b59'
argv=['env','GTS9_DEVICE=10.191.121.145',p.SSH]
source=p.ROOT/'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
known={x['MESSAGE'] for x in map(json.loads,source.read_text().splitlines()) if int(x.get('PRIORITY',7))<=3}
initial=json.loads((base/'charging-attempt-02/initial-startup.json').read_text())
rows=[];start=time.monotonic();offline_start=None
try:
 print('UNPLUG_CAPTURE_READY',flush=True)
 while True:
  tick=time.monotonic()
  x=f.parse(rec.command(f'sample-{len(rows):03d}',argv+[f.COMMAND],15)[0])
  x['elapsed_seconds']=round(tick-start,3);rows.append(x)
  p.write_json(rec.folder/'samples.json',rows)
  error=f.safety(x,boot,rows[:-1])
  if error:raise RuntimeError(error)
  offline=(x['usb_online']==x['tcpm_online']==x['passive_online']==0 and x['battery_status']=='Discharging' and x['battery_current_ua']<0)
  if offline:
   if offline_start is None:offline_start=tick;print('OFFLINE_DISCHARGE_CONFIRMED',flush=True)
   if tick-offline_start>=15:break
  elif offline_start is not None:raise RuntimeError('offline-state-lost')
  if tick-start>300:raise RuntimeError('unplug-not-confirmed-within-300s')
  time.sleep(max(.05,5-(time.monotonic()-tick)))
 raw=rec.command('final-kernel',argv+['journalctl -b -k --no-pager -o json'],25)[0]
 scan=e.inspect_journal(raw,boot,known,accepted_startup_variants=True,startup_iova_range=(0xb8000000,0xbab00000),accepted_qca_cycles=True,observed_uptime=x['uptime_seconds'])
 p.write_json(rec.folder/'kernel-scan.json',scan)
 if scan['fault_counts'] or scan['suspects'] or startup_evidence(raw,boot)!=initial:raise RuntimeError('new-kernel-or-passive-fault')
 result={'verdict':'PASS bounded unplug/discharge check','boot_id':boot,'offline_seconds':round(tick-offline_start,3),'samples':len(rows),'device_configuration_changed':False,'pps_requested':False,'pump_on':False}
except Exception as exc:
 result={'verdict':'STOP','error':str(exc),'samples':len(rows),'device_configuration_changed':False}
 p.write_json(rec.folder/'summary.json',result);print('STOP',str(exc),flush=True);sys.exit(1)
p.write_json(rec.folder/'summary.json',result);print(json.dumps(result),flush=True)
