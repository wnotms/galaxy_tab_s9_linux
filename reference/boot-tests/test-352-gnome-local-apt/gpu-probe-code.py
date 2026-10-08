from pathlib import Path
import json,subprocess,time
BOOT='be1baaaa-47fc-41f5-8255-8f7092c01653'
root=Path('/var/log/gts9-test352-gpu')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert json.loads(Path('/var/log/gts9-test352-install/summary.json').read_text())['verdict']=='INSTALLED_GDM_MASKED_HARDWARE_NOT_ACCEPTED'
b=Path('/sys/class/power_supply/sm5714-battery')
assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<380
root.mkdir(exist_ok=False)
def save(name,argv,timeout):
 with (root/(name+'.stdout.txt')).open('w') as out,(root/(name+'.stderr.txt')).open('w') as err:
  p=subprocess.run(argv,stdout=out,stderr=err,timeout=timeout)
 (root/(name+'.command.json')).write_text(json.dumps(dict(argv=argv,returncode=p.returncode)))
 return p.returncode
start=time.monotonic();state=dict(boot_id=BOOT,verdict='STARTED_NOT_ACCEPTED')
try:
 assert save('kernel-before',['journalctl','-k','-b','-o','json','--no-pager'],10)==0
 assert save('vulkan',['vulkaninfo','--summary'],30)==0
 text=(root/'vulkan.stdout.txt').read_text()
 assert 'Adreno' in text and 'turnip' in text.lower(),'hardware renderer absent'
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
 state['verdict']='ADRENO_TURNIP_IDENTIFIED_PENDING_JOURNAL_REVIEW'
except BaseException as exc:
 state.update(verdict='STOP_GPU_PROBE',error=repr(exc))
 raise
finally:
 try:save('kernel-after',['journalctl','-k','-b','-o','json','--no-pager'],10)
 finally:
  state['elapsed_seconds']=time.monotonic()-start
  (root/'summary.json').write_text(json.dumps(state,indent=2)+'\n')
  print(json.dumps(state),flush=True)
