from pathlib import Path
import gzip,hashlib,json,os,subprocess,sys,time,re,pwd,stat
BOOT='25ff0ad0-cf2f-4cc6-971d-2b38365da2db'
ROOT=Path('/var/log/gts9-test361-heat')
report={'started_monotonic':time.monotonic(),'boot_id':BOOT,'phases':[],'changed':False}
user=pwd.getpwnam('ms')
runtime=Path('/run/user')/str(user.pw_uid)
bus=runtime/'bus'
settings=['runuser','-u','ms','--','env','XDG_RUNTIME_DIR='+str(runtime),'DBUS_SESSION_BUS_ADDRESS=unix:path='+str(bus)]
KEY='/org/gnome/desktop/interface/enable-animations'
severe=re.compile(r'\bsoft lockup\b|\brcu.*(?:detected.*stall|stall detected)|\bCSD.*(?:non-responsive|stuck)|\bKernel panic\b|\bOops:|\bBUG:|\bInternal error:|\bSError\b|blocked for more than|workqueue.*lockup|(?:adreno|msm).*GPU.*(?:fault|hang)|fts1ba90a.*(?:failed|timeout|error)',re.I)
def cmd(argv,timeout=15):
 p=subprocess.run(argv,text=True,capture_output=True,timeout=timeout)
 record=dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
 report.setdefault('commands',[]).append(record)
 if p.returncode:raise RuntimeError(record)
 return p.stdout
cursor=None
namespace={'__name__':'heat_sampler'}
try:
 assert not ROOT.exists(),'never restart the same scope'
 assert stat.S_ISSOCK(bus.stat().st_mode) and bus.stat().st_uid==user.pw_uid,'require the active user bus for live preference notification'
 assert Path('/proc/sys/kernel/random/boot_id').read_text().strip()==BOOT
 assert hashlib.sha256(gzip.decompress(Path('/proc/config.gz').read_bytes())).hexdigest()=='51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a'
 assert hashlib.sha256(Path('/sys/kernel/notes').read_bytes()).hexdigest()=='03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95'
 assert not any(t.startswith('sm5440_fedora.') or t=='lpcharge=1' for t in Path('/proc/cmdline').read_text().split())
 assert cmd(['systemctl','is-active','gdm.service']).strip()=='active'
 assert cmd(['systemctl','--failed','--no-legend','--plain']).strip()==''
 code=sys.stdin.buffer.read()
 assert hashlib.sha256(code).hexdigest()=='20d6166192ebed44d6e565deca4dcd40117646c12ae67e0a45d88efe1d403d60'
 exec(code,namespace)
 ROOT.mkdir(mode=0o700)
 report['collector_pid']=os.getpid()
 report['proc_start_ticks']=Path('/proc/self/stat').read_text().split()[21]
 (ROOT/'collector.json').write_text(json.dumps(report))
 report['original_animation_user_value']=cmd(settings+['dconf','read',KEY]).strip()
 report['original_animation_effective']=cmd(settings+['gsettings','get','org.gnome.desktop.interface','enable-animations']).strip()
 assert report['original_animation_effective']=='true','do not override an already changed owner preference'
 (ROOT/'original-setting.json').write_text(json.dumps({k:v for k,v in report.items() if k.startswith('original_')}))
 initial=cmd(['journalctl','-k','-b','-o','json','--quiet','--no-pager'])
 (ROOT/'kernel-before.jsonl').write_text(initial)
 initial_records=[json.loads(line) for line in initial.splitlines()]
 assert initial_records
 cursor=initial_records[-1]['__CURSOR']
 for phase in ('animations-on','animations-off'):
  if phase=='animations-off':
   report['changed']=True
   cmd(settings+['gsettings','set','org.gnome.desktop.interface','enable-animations','false'])
   assert cmd(settings+['gsettings','get','org.gnome.desktop.interface','enable-animations']).strip()=='false'
  samples=[];base=time.monotonic()
  for index in range(7):
   remaining=base+index*10-time.monotonic()
   if remaining>0:time.sleep(remaining)
   sample=namespace['snapshot']()
   assert sample['boot_id']==BOOT,'new boot'
   assert namespace['safe_pack'](sample['battery']),'battery safety gate'
   samples.append(sample)
   with (ROOT/'samples.jsonl').open('a') as f:f.write(json.dumps({'phase':phase,'sample':sample})+'\n')
   messages=cmd(['journalctl','-k','-b','--after-cursor',cursor,'-o','json','--quiet','--no-pager'])
   if messages:
    records=[json.loads(line) for line in messages.splitlines()]
    with (ROOT/'kernel-new.jsonl').open('a') as f:f.write(messages)
    cursor=records[-1]['__CURSOR']
    assert not any(severe.search(record.get('MESSAGE','')) for record in records),'new kernel fault'
  assert cmd(['systemctl','is-active','gdm.service']).strip()=='active'
  assert cmd(['systemctl','--failed','--no-legend','--plain']).strip()==''
  report['phases'].append({'name':phase,'samples':samples,'activity':namespace['interval'](samples[0],samples[-1])})
  (ROOT/'checkpoint.json').write_text(json.dumps({k:v for k,v in report.items() if k!='commands'}))
 report['final_animation_effective']=cmd(settings+['gsettings','get','org.gnome.desktop.interface','enable-animations']).strip()
 assert report['final_animation_effective']=='false'
 report['kernel_final_json']=cmd(['journalctl','-k','-b','-o','json','--quiet','--no-pager'])
 report['verdict']='GNOME_REDUCED_MOTION_APPLIED_TWO_BOUNDED_NORMAL_USE_WINDOWS'
except Exception as exc:
 report['verdict']='STOP';report['error']=repr(exc)
 if report['changed']:
  try:
   old=report['original_animation_user_value']
   cmd(settings+['dconf','write',KEY,old] if old else settings+['dconf','reset',KEY])
   report['preference_restored']=True
  except Exception as restore:report['restore_error']=repr(restore)
finally:
 report['finished_monotonic']=time.monotonic()
 if ROOT.exists():(ROOT/'terminal.json').write_text(json.dumps(report))
 print(json.dumps(report))
if report['verdict']=='STOP':raise SystemExit(1)
