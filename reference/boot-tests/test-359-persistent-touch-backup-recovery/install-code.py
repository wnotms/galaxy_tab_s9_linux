from pathlib import Path
import gzip,hashlib,io,json,os,subprocess,sys,tarfile,time
EXPECTED = json.loads('{"load.py": {"sha256": "95968c95709c7939316e730adf74741f0e3dd4ce2598d991ca77ed48ee060dfb", "bytes": 6360}, "gts9-touch.service": {"sha256": "f44bd9b745f5aa137d4a11693076d78ccd47a2bcbe27eab5d7b39479a3130a19", "bytes": 276}, "fts1ba90a.ko": {"sha256": "ac2fbdc6489b847771a65a1971d28f0b5d601c796c50d68c92f85a70feaf5e45", "bytes": 441776}}')
BOOT = '1adc0f13-a210-4856-bb15-c6e9df17867a'
def cmd(argv, timeout=20):
 p=subprocess.run(argv,capture_output=True,text=True,timeout=timeout)
 result=dict(argv=argv,returncode=p.returncode,stdout=p.stdout,stderr=p.stderr)
 report.setdefault('commands',[]).append(result)
 if p.returncode: raise RuntimeError(result)
 return p.stdout
report={'started_at':time.time(),'physical_insmod_attempts':0}
try:
 data=sys.stdin.buffer.read()
 with tarfile.open(fileobj=io.BytesIO(data)) as archive:
  members=archive.getmembers()
  assert {m.name for m in members}==set(EXPECTED) and len(members)==len(EXPECTED)
  assert all(m.isfile() for m in members)
  files={m.name:archive.extractfile(m).read() for m in members}
 for name,blob in files.items():
  assert len(blob)==EXPECTED[name]['bytes'] and hashlib.sha256(blob).hexdigest()==EXPECTED[name]['sha256']
 namespace={'__name__':'touch_install_gate'}
 exec(files['load.py'],namespace)
 namespace['MODULE']=Path('/var/tmp/gts9-test357/fts1ba90a.ko')
 before=namespace['run'](False)
 assert before['boot_id']==BOOT and before['status']=='already-loaded' and before['insmod_attempts']==0
 report['preflight']=before
 battery=Path('/sys/class/power_supply/sm5714-battery')
 report['battery_before']={name:(battery/name).read_text().strip() for name in ('capacity','temp','health','status','current_now')}
 assert report['battery_before']['health']=='Good' and 0<=int(report['battery_before']['temp'])<420
 assert cmd(['systemctl','is-active','gdm.service']).strip()=='active'
 existing_failed=cmd(['systemctl','--failed','--no-legend','--plain']).strip()
 assert existing_failed.splitlines()==['dpkg-db-backup.service loaded failed failed Daily dpkg database backup service']
 backup_state=cmd(['systemctl','show','dpkg-db-backup.service','-p','Result','-p','ExecMainStatus'])
 assert 'Result=start-limit-hit' in backup_state and 'ExecMainStatus=0' in backup_state
 report['existing_backup_failure_acknowledged']=existing_failed
 # One recorded unit only; historical failure retained in358. Do not mask,
 # disable timers, change clocks or reset other failures. Verify the operation.
 cmd(['systemctl','reset-failed','dpkg-db-backup.service'])
 cmd(['systemctl','start','dpkg-db-backup.service'])
 backup_after=cmd(['systemctl','show','dpkg-db-backup.service','-p','Result','-p','ExecMainStatus'])
 assert 'Result=success' in backup_after and 'ExecMainStatus=0' in backup_after
 report['backup_recovery']=backup_after
 assert cmd(['systemctl','--failed','--no-legend','--plain']).strip()==''
 masks={str(Path('/etc/systemd/system')/n):os.readlink(Path('/etc/systemd/system')/n) for n in ['gdm.service','gdm3.service','display-manager.service']}
 assert set(masks.values())=={'/dev/null'}
 report['masks_before']=masks
 targets={'load.py':Path('/usr/local/libexec/gts9-touch'),'gts9-touch.service':Path('/etc/systemd/system/gts9-touch.service'),'fts1ba90a.ko':Path('/usr/local/lib/gts9-desktop/fts1ba90a.ko')}
 for target in targets.values():assert not target.exists() and not target.is_symlink(),str(target)
 assert not Path('/usr/local/lib/gts9-desktop').exists()
 report['kernel_before_json']=cmd(['journalctl','-k','-b','-o','json','--no-pager'])
 # Mutation boundary: all targets absent, payload/identity/health/loaded input
 # qualified. Only these files plus systemd's recorded Wants link are created.
 for name,target in targets.items():
  target.parent.mkdir(mode=0o755,parents=True,exist_ok=True)
  with target.open('xb') as f:f.write(files[name])
  target.chmod(0o755 if name=='load.py' else 0o644)
  assert target.stat().st_uid==0
 namespace['MODULE']=targets['fts1ba90a.ko']
 report['installed_readonly']=namespace['run'](False)
 assert report['installed_readonly']['status']=='already-loaded'
 cmd(['systemctl','daemon-reload'])
 cmd(['systemctl','enable','gts9-touch.service'])
 cmd(['systemctl','start','gts9-touch.service'])
 assert cmd(['systemctl','is-active','gts9-touch.service']).strip()=='active'
 assert cmd(['systemctl','is-enabled','gts9-touch.service']).strip()=='enabled'
 report['unit_journal_json']=cmd(['journalctl','-b','-u','gts9-touch.service','-o','json','--no-pager'])
 verdicts=[]
 for line in report['unit_journal_json'].splitlines():
  message=json.loads(line).get('MESSAGE','')
  if message.startswith('{'):
   try:v=json.loads(message)
   except ValueError:continue
   if 'insmod_attempts' in v:verdicts.append(v)
 assert len(verdicts)==1 and verdicts[0]['status']=='already-loaded' and verdicts[0]['insmod_attempts']==0
 report['unit_verdict']=verdicts[0]
 report['final']=namespace['run'](False)
 assert report['final']['boot_id']==BOOT and report['final']['status']=='already-loaded'
 assert cmd(['systemctl','is-active','gdm.service']).strip()=='active'
 assert cmd(['systemctl','--failed','--no-legend','--plain']).strip()==''
 report['masks_after']={path:os.readlink(path) for path in masks}
 assert report['masks_after']==masks
 link=Path('/etc/systemd/system/gdm.service.wants/gts9-touch.service')
 assert link.is_symlink() and link.resolve()==targets['gts9-touch.service']
 report['wants_link']={'path':str(link),'target':os.readlink(link)}
 report['installed_sha256']={str(target):hashlib.sha256(target.read_bytes()).hexdigest() for target in targets.values()}
 assert all(report['installed_sha256'][str(target)]==EXPECTED[name]['sha256'] for name,target in targets.items())
 report['battery_after']={name:(battery/name).read_text().strip() for name in report['battery_before']}
 report['kernel_after_json']=cmd(['journalctl','-k','-b','-o','json','--no-pager'])
 report['verdict']='PERSISTENT_COMPONENT_INSTALLED_CURRENT_BOOT_NOOP_PASS'
except Exception as exc:
 report['verdict']='STOP'; report['error']=repr(exc)
finally:
 report['finished_at']=time.time()
 print(json.dumps(report))
if report['verdict']=='STOP':raise SystemExit(1)
