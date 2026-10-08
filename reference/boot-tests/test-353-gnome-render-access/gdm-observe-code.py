from pathlib import Path
import json,subprocess,time
BOOT='be1baaaa-47fc-41f5-8255-8f7092c01653'
root=Path('/var/log/gts9-test353-gdm');units=('gdm.service','gdm3.service','display-manager.service')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert json.loads(Path('/var/log/gts9-test352-gpu/summary.json').read_text())['verdict']=='ADRENO_TURNIP_IDENTIFIED_PENDING_JOURNAL_REVIEW'
assert json.loads(Path('/var/log/gts9-test352-install/summary.json').read_text())['verdict']=='INSTALLED_GDM_MASKED_HARDWARE_NOT_ACCEPTED'
b=Path('/sys/class/power_supply/sm5714-battery')
assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<380
masks=[Path('/etc/systemd/system')/n for n in units]
assert all(p.is_symlink() and str(p.readlink())=='/dev/null' for p in masks)
assert json.loads(Path('/var/log/gts9-test353-render/summary.json').read_text())['verdict']=='MS_RENDER_ACCESS_VALIDATED'
root.mkdir(exist_ok=False)
def save(name,argv,timeout=10,check=True):
 with (root/(name+'.stdout.txt')).open('w') as out,(root/(name+'.stderr.txt')).open('w') as err:
  p=subprocess.run(argv,stdout=out,stderr=err,timeout=timeout)
 (root/(name+'.command.json')).write_text(json.dumps(dict(argv=argv,returncode=p.returncode)))
 if check and p.returncode:raise RuntimeError(name+' failed '+str(p.returncode))
 return p.returncode
state=dict(boot_id=BOOT,verdict='STARTED_NOT_ACCEPTED',gdm_start_attempts=0)
try:
 cursor=json.loads(subprocess.check_output(['journalctl','-n','1','-o','json','--no-pager'],text=True))['__CURSOR']
 state['journal_start_cursor']=cursor
 save('kernel-before',['journalctl','-k','-b','-o','json','--no-pager'])
 for p in masks:p.unlink()
 save('reload',['systemctl','daemon-reload'])
 state['gdm_start_attempts']=1
 save('start',['systemctl','start','gdm.service'],15)
 begin=time.monotonic();state['observation_started_monotonic']=begin
 print(json.dumps(dict(stage='GDM_STARTED',boot_id=BOOT)),flush=True)
 with (root/'samples.jsonl').open('x') as stream:
  while True:
   sample=dict(seconds=time.monotonic()-begin,boot_id=Path('/proc/sys/kernel/random/boot_id').read_text().strip(),battery={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')})
   stream.write(json.dumps(sample)+'\n');stream.flush()
   assert sample['boot_id']==BOOT and sample['battery']['health']=='Good' and int(sample['battery']['temp'])<420
   p=subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True,timeout=5)
   assert p.returncode==0 and p.stdout.strip()=='active','GDM lost active state'
   if sample['seconds']>=60:break
   time.sleep(min(5,60-sample['seconds']))
 state.update(verdict='GDM_60S_OBSERVED_PENDING_VISIBLE_AND_JOURNAL_REVIEW',observation_seconds=sample['seconds'])
except BaseException as exc:
 state.update(verdict='STOP_GDM_OBSERVATION',error=repr(exc));raise
finally:
 try:
  save('shell-journal',['journalctl','-b','--after-cursor',cursor,'_COMM=gnome-shell','--no-pager','-o','json'],check=False)
  save('gdm-journal',['journalctl','-b','-u','gdm.service','--no-pager','-o','short-monotonic'],check=False)
  save('sessions',['loginctl','list-sessions','--no-legend'],check=False)
 finally:
  try:save('stop',['systemctl','stop','gdm.service'])
  finally:
   for p in masks:
    if not p.is_symlink() and not p.exists():p.symlink_to('/dev/null')
    assert p.is_symlink() and str(p.readlink())=='/dev/null','mask changed unexpectedly'
   save('final-reload',['systemctl','daemon-reload'])
   save('final-state',['systemctl','is-active','gdm.service'],check=False)
   save('kernel-after',['journalctl','-k','-b','-o','json','--no-pager'])
   (root/'summary.json').write_text(json.dumps(state,indent=2)+'\n')
   print(json.dumps(state),flush=True)
