from pathlib import Path
import json,os,subprocess,time,hashlib
BOOT='25ff0ad0-cf2f-4cc6-971d-2b38365da2db'
report={'started_at':time.time()}
def cmd(argv, timeout=20, accepted=(0,)):
 p=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
 result=dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
 report.setdefault('commands',[]).append(result)
 if p.returncode not in accepted:raise RuntimeError(result)
 return p.stdout
def thermal_snapshot():
 r={'monotonic':time.monotonic(),'loadavg':Path('/proc/loadavg').read_text().strip(),'cpu_stat':Path('/proc/stat').read_text().splitlines()[0]}
 b=Path('/sys/class/power_supply/sm5714-battery')
 r['battery']={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')}
 r['cpufreq']={}
 for cpu in Path('/sys/devices/system/cpu').glob('cpu[0-9]*'):
  f=cpu/'cpufreq';values={}
  for n in ('scaling_cur_freq','scaling_governor','scaling_min_freq','scaling_max_freq'):
   try:values[n]=(f/n).read_text().strip()
   except OSError:pass
  if values:r['cpufreq'][cpu.name]=values
 r['devfreq']={}
 for device in Path('/sys/class/devfreq').glob('*'):
  values={}
  for n in ('name','cur_freq','governor','min_freq','max_freq','trans_stat'):
   try:values[n]=(device/n).read_text().strip()
   except OSError:pass
  if values:r['devfreq'][device.name]=values
 return r
masks=[Path('/etc/systemd/system')/n for n in ('gdm.service','gdm3.service','display-manager.service')]
started=False
try:
 ns={'__name__':'touch_gate'}
 assert hashlib.sha256(Path('/usr/local/libexec/gts9-touch').read_bytes()).hexdigest()=='95968c95709c7939316e730adf74741f0e3dd4ce2598d991ca77ed48ee060dfb'
 exec(Path('/usr/local/libexec/gts9-touch').read_text(),ns)
 before=ns['run'](False);report['before']=before
 assert before['boot_id']==BOOT and before['status']=='ready' and before['insmod_attempts']==0
 assert cmd(['systemctl','is-active','gdm.service'],accepted=(0,3)).strip()=='inactive'
 assert cmd(['systemctl','is-active','gts9-touch.service'],accepted=(0,3)).strip()=='inactive'
 assert cmd(['systemctl','is-enabled','gts9-touch.service']).strip()=='enabled'
 assert cmd(['systemctl','--failed','--no-legend','--plain']).strip()==''
 assert all(p.is_symlink() and os.readlink(p)=='/dev/null' for p in masks)
 report['kernel_before_json']=cmd(['journalctl','-k','-b','-o','json','--no-pager'])
 report['taint_before']=Path('/proc/sys/kernel/tainted').read_text().strip()
 report['thermal_before']=thermal_snapshot()
 cmd(['systemctl','unmask','gdm.service','gdm3.service','display-manager.service'])
 started=True
 try:cmd(['systemctl','start','gdm.service'],timeout=40)
 finally:cmd(['systemctl','mask','gdm.service','gdm3.service','display-manager.service'])
 assert cmd(['systemctl','is-active','gts9-touch.service']).strip()=='active'
 assert cmd(['systemctl','is-active','gdm.service']).strip()=='active'
 report['unit_journal_json']=cmd(['journalctl','-b','-u','gts9-touch.service','-o','json','--no-pager'])
 verdicts=[]
 for line in report['unit_journal_json'].splitlines():
  message=json.loads(line).get('MESSAGE','')
  if message.startswith('{'):
   try:value=json.loads(message)
   except ValueError:continue
   if 'insmod_attempts' in value:verdicts.append(value)
 assert len(verdicts)==1 and verdicts[0]['status']=='loaded' and verdicts[0]['insmod_attempts']==1
 report['loader_verdict']=verdicts[0]
 time.sleep(10)
 final=ns['run'](False);report['final']=final
 assert final['boot_id']==BOOT and final['status']=='already-loaded'
 assert all(p.is_symlink() and os.readlink(p)=='/dev/null' for p in masks)
 assert cmd(['systemctl','--failed','--no-legend','--plain']).strip()==''
 report['gdm_journal_json']=cmd(['journalctl','-b','-u','gdm.service','-o','json','--no-pager'])
 report['kernel_after_json']=cmd(['journalctl','-k','-b','-o','json','--no-pager'])
 report['input']=Path('/proc/bus/input/devices').read_text()
 report['taint_after']=Path('/proc/sys/kernel/tainted').read_text().strip()
 b=Path('/sys/class/power_supply/sm5714-battery')
 report['battery']={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')}
 report['thermal_after']=thermal_snapshot()
 assert report['battery']['health']=='Good' and 0<=int(report['battery']['temp'])<420
 report['verdict']='PERSISTENT_NEWBOOT_LOADER_PASS_OWNER_UI_PENDING'
except Exception as exc:
 report['verdict']='STOP';report['error']=repr(exc)
 if started:
  try:cmd(['systemctl','stop','gdm.service']);cmd(['systemctl','mask','gdm.service','gdm3.service','display-manager.service'])
  except Exception as cleanup:report['cleanup_error']=repr(cleanup)
 try:report['kernel_failure_json']=cmd(['journalctl','-k','-b','-o','json','--no-pager'])
 except Exception as collection:report['collection_error']=repr(collection)
finally:
 report['finished_at']=time.time();print(json.dumps(report))
if report['verdict']=='STOP':raise SystemExit(1)
