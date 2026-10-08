"""One normal WEZ01 load, outside181dir, no reboot/flash/firmware update."""
from pathlib import Path
import gzip,hashlib,io,json,re,subprocess,sys,tarfile,time
BOOT='25ff0ad0-cf2f-4cc6-971d-2b38365da2db'
CONFIG='51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a'
NOTES='03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'
MODULE='bc3816a8f37c0f45bdaca3ac9548793df1784541364da9017d08d5c4841e1412'
root=Path('/var/log/gts9-test362-pen');stage=Path('/var/tmp/gts9-test362')
client=Path('/sys/bus/i2c/devices/6-0056');b=Path('/sys/class/power_supply/sm5714-battery')
assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
assert hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest()==CONFIG
assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()==NOTES
assert (client/'of_node/compatible').read_bytes()==b'wacom,w90xx\x00'
assert not (client/'driver').exists() and not Path('/sys/module/wacom_wez01').exists()
assert Path('/sys/module/fts1ba90a').exists()
assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<380 and int((b/'capacity').read_text())>=20
assert subprocess.check_output(['systemctl','is-active','gdm.service'],text=True).strip()=='active'
assert not subprocess.check_output(['systemctl','--failed','--plain','--no-legend'],text=True).strip()
root.mkdir(exist_ok=False);stage.mkdir(exist_ok=False)
state={'boot_id':BOOT,'verdict':'STARTED','insmod_attempts':0,'module_sha256':MODULE,'autoload':False,'touch_palm_rejection':False}
def run(name,argv,check=True):
 p=subprocess.run(argv,capture_output=True,timeout=15)
 (root/(name+'.stdout')).write_bytes(p.stdout);(root/(name+'.stderr')).write_bytes(p.stderr)
 (root/(name+'.command.json')).write_text(json.dumps({'argv':argv,'returncode':p.returncode,'monotonic':time.monotonic()}))
 if check and p.returncode:raise RuntimeError(name+' failed '+str(p.returncode))
 return p
try:
 before=run('kernel-before',['journalctl','-k','-b','-o','json','--no-pager']).stdout
 records=[json.loads(x) for x in before.splitlines() if x];assert records,'empty kernel journal'
 last=int(records[-1]['__MONOTONIC_TIMESTAMP']);state['kernel_start_monotonic_us']=last
 (root/'taint-before.txt').write_text(Path('/proc/sys/kernel/tainted').read_text())
 data=sys.stdin.buffer.read(1024*1024+1);assert len(data)<=1024*1024
 with tarfile.open(fileobj=io.BytesIO(data),mode='r:gz') as archive:
  assert {m.name for m in archive.getmembers()}=={'wacom-wez01.ko','capture-events.py'}
  for m in archive.getmembers():
   assert m.isfile() and m.size<=500000
   content=archive.extractfile(m).read();(stage/m.name).write_bytes(content);(stage/m.name).chmod(0o600)
 path=stage/'wacom-wez01.ko'
 assert path.stat().st_size==427920 and hashlib.sha256(path.read_bytes()).hexdigest()==MODULE
 state['insmod_attempts']=1
 run('insmod',['/usr/sbin/insmod',str(path)])
 deadline=time.monotonic()+10
 while not (client/'driver').exists() and time.monotonic()<deadline:time.sleep(.2)
 assert (client/'driver').resolve().name=='wacom-wez01','pen client not bound'
 events=list(client.glob('input/input*/event*'));assert len(events)==1
 event='/dev/input/'+events[0].name;assert Path(event).exists()
 state['event_device']=event;state['driver_bound']=str((client/'driver').resolve())
 run('udev-settle',['udevadm','settle','--timeout=5'])
 props=run('udev',['udevadm','info','--query=property','--name',event]).stdout.decode()
 assert 'ID_INPUT_TABLET=1' in props,'not classified as tablet input'
 run('interrupts-before',['cat','/proc/interrupts']);time.sleep(5);run('interrupts-after',['cat','/proc/interrupts'])
 def irq_count(name):
  lines=[x for x in (root/(name+'.stdout')).read_text().splitlines() if 'w90xx' in x or 'wacom-wez01' in x]
  assert len(lines)==1,'pen IRQ attribution ambiguous'
  return sum(int(x) for x in lines[0].split(':',1)[1].split() if x.isdigit())
 state['initial_irq_delta_5s']=irq_count('interrupts-after')-irq_count('interrupts-before')
 assert 0<=state['initial_irq_delta_5s']<5000,'unexpected IRQ rate'
 run('input-devices',['cat','/proc/bus/input/devices'])
 kernel=run('kernel-after',['journalctl','-k','-b','-o','json','--no-pager']).stdout
 after=[json.loads(x) for x in kernel.splitlines() if x and int(json.loads(x)['__MONOTONIC_TIMESTAMP'])>last]
 pattern=re.compile(r'soft lockup|rcu.*(?:stall|INFO)|CSD.*(?:stall|non.respon)|Kernel panic|\bOops:|\bBUG:|Internal error|SError|GPU fault|GPU hang|GPU recovery|w90xx.*(?:failed|error)|wacom.*(?:failed|error)|query failed|unexpected mpu id|BTF.*(?:invalid|failed)|disagrees about version|Unknown symbol',re.I)
 known='module verification failed: signature and/or required key missing - tainting kernel'
 state['new_faults']=[x.get('MESSAGE') for x in after if pattern.search(str(x.get('MESSAGE',''))) and known not in str(x.get('MESSAGE',''))]
 assert not state['new_faults'],'new fault after pen load'
 state['query_messages']=[x.get('MESSAGE') for x in after if 'fw version' in str(x.get('MESSAGE',''))]
 assert len(state['query_messages'])==1,'missing pen query identity'
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
 assert (b/'health').read_text().strip()=='Good' and int((b/'temp').read_text())<420
 assert run('gdm',['systemctl','is-active','gdm.service']).stdout.strip()==b'active'
 assert not run('failed-after',['systemctl','--failed','--no-legend','--plain']).stdout.strip()
 with (root/'capture.stdout').open('wb') as out,(root/'capture.stderr').open('wb') as err:
  worker=subprocess.Popen(['systemd-inhibit','--what=sleep','--mode=block','--who=Test362','--why=First pen input test; suspend not accepted','python3',str(stage/'capture-events.py'),event],stdin=subprocess.DEVNULL,stdout=out,stderr=err,start_new_session=True)
 state['capture_launcher_pid']=worker.pid
 for i in range(30):
  if (root/'capture-meta.json').exists():break
  assert worker.poll() is None,'capture exited';time.sleep(.1)
 meta=json.loads((root/'capture-meta.json').read_text())
 state['capture_pid']=meta['pid'];state['capture_proc_start_ticks']=meta['proc_start_ticks']
 state.update(verdict='PEN_ENUMERATED_CAPTURE_LIVE_AWAITING_OWNER',battery={n:(b/n).read_text().strip() for n in ('capacity','temp','health','status','current_now')})
except BaseException as exc:
 state.update(verdict='STOP_PEN_BRINGUP',error=repr(exc));raise
finally:
 (root/'taint-after.txt').write_text(Path('/proc/sys/kernel/tainted').read_text())
 (root/'summary.json').write_text(json.dumps(state,indent=2)+'\n');print(json.dumps(state),flush=True)
