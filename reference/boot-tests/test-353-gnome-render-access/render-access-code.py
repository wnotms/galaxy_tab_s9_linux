from pathlib import Path
import json,subprocess,time,os,re
BOOT='be1baaaa-47fc-41f5-8255-8f7092c01653'
root=Path('/var/log/gts9-test353-render')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert os.uname().machine=='aarch64' and os.geteuid()==0
b=Path('/sys/class/power_supply/sm5714-battery')
assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<380
assert subprocess.run(['systemctl','is-active','gdm.service'],capture_output=True,text=True).stdout.strip()=='inactive'
assert json.loads(Path('/var/log/gts9-test352-install/summary.json').read_text())['verdict']=='INSTALLED_GDM_MASKED_HARDWARE_NOT_ACCEPTED'
root.mkdir(exist_ok=False)
def run(name,args,timeout=10):
 with (root/(name+'.stdout.txt')).open('w') as out,(root/(name+'.stderr.txt')).open('w') as err:
  p=subprocess.run(args,stdout=out,stderr=err,timeout=timeout)
 (root/(name+'.command.json')).write_text(json.dumps(dict(argv=args,returncode=p.returncode)))
 assert p.returncode==0,name+' failed'
 return (root/(name+'.stdout.txt')).read_text()
state=dict(boot_id=BOOT,verdict='STARTED_NOT_ACCEPTED',groups_added=[])
try:
 run('group-before',['getent','group','render'])
 for user in ('ms','Debian-gdm'):
  groups=run(user+'-before',['id','-Gn',user]).split()
  if 'render' not in groups:
   run(user+'-add',['gpasswd','-a',user,'render']);state['groups_added'].append(user)
  after=run(user+'-after',['id','-Gn',user]).split()
  assert set(after)==set(groups)|{'render'},'unexpected group delta'
 run('group-after',['getent','group','render'])
 vulkan=run('ms-vulkan',['runuser','-u','ms','--','vulkaninfo','--summary'],30)
 assert 'Adreno' in vulkan and 'turnip' in vulkan.lower(),'user hardware Vulkan absent'
 egl=run('ms-egl',['runuser','-u','ms','--','eglinfo','-B','-p','surfaceless'],30)
 assert re.search(r'FD740|Adreno.*740',egl),'user hardware OpenGL absent'
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
 state['verdict']='MS_RENDER_ACCESS_VALIDATED'
except BaseException as exc:
 state.update(verdict='STOP_RENDER_ACCESS',error=repr(exc));raise
finally:
 (root/'summary.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state),flush=True)
