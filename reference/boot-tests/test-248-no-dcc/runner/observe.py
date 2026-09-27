import control
import datetime,hashlib,json,re,subprocess,time
from pathlib import Path

def classify(text):
 bad=[x for x in ("CPUS still haven't responded",'BUG: workqueue lockup','soft lockup - CPU',
      'detected stalls','self-detected stall','CSD lock','Kernel panic - not syncing','Oops:') if x in text]
 if bad:return 'failure_observed',bad
 suspect=[x for x in ('vblank wait timed out','CTL_START timeout','Timeout waiting for hardware cmd interrupt','rpmh_rsc_send_data: Error') if x in text]
 if re.search(r'mmc\d.*(?:timed out|timeout)',text,re.I):suspect.append('MMC timeout')
 return ('suspect',suspect) if suspect else (None,[])

def profile(phase,boot,production):
 if production:
  s,_=control.shell(phase,'profile','cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /sys/module/ramoops/parameters/ecc; test ! -e /sys/module/gts9_pnmi_test/parameters/enable; echo helper_absent=$?',timeout=6)
  assert s.splitlines()==['0','0','0','0','0','helper_absent=0']
 else:
  s,_=control.shell('target','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/cmdline; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /sys/module/gts9_lastactivity/parameters/capture_id; sha256sum /sys/kernel/notes; cat /proc/sys/kernel/printk; test ! -e /sys/module/gts9_pnmi_test/parameters/enable; echo helper_absent=$?; grep -E " (_text|_stext|do_nothing|rcu_barrier_handler|irq_work_run|ipi_types)$" /proc/kallsyms; cat /proc/sys/kernel/random/boot_id',timeout=8)
  l=s.splitlines();assert l[0]==l[-1]==boot
  assert all(x in l[2].split() for x in ['gts9_lastactivity=1','irqchip.gicv3_pseudo_nmi=1','loglevel=5','csdlock_debug=1'])
  assert l[3:8]==['64','1','1','1','10'] and l[10].split()[:2]==['5','4'] and l[11]=='helper_absent=0'
  assert re.fullmatch(r'[a-f0-9-]{36}',l[8])
  assert l[9].split()[0]==hashlib.sha256(Path('out/test248/kernel-notes.bin').read_bytes()).hexdigest()
  link={r.split()[2]:int(r.split()[0],16) for r in Path('out/test248/System.map').read_text().splitlines()}
  anchors={r.split()[2]:int(r.split()[0],16)-link[r.split()[2]] for r in l[12:-1]}
  assert len(anchors)==6 and len(set(anchors.values()))==1
  dcc,_=control.shell('target','dcc-absent','cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | grep -F \"# CONFIG_HVC_DCC is not set\"; test ! -e /dev/hvc0 && test ! -e /sys/class/tty/hvc0 && echo dcc_tty_absent; systemctl is-active serial-getty@hvc0.service; cat /proc/sys/kernel/random/boot_id',timeout=8)
  assert dcc.splitlines()==[boot,'# CONFIG_HVC_DCC is not set','dcc_tty_absent','inactive',boot],dcc
  csd,_=control.shell('target','csd-config','cat /proc/sys/kernel/random/boot_id; cat /sys/module/smp/parameters/csd_lock_timeout /sys/module/smp/parameters/panic_on_ipistall /sys/module/rcutree/parameters/csd_lock_suppress_rcu_stall; cat /proc/sys/kernel/random/boot_id',timeout=6)
  assert csd.splitlines()==[boot,'5000','0','N',boot],csd
  (control.P/'target/identity.json').write_text(json.dumps({'boot_id':boot,'capture_id':l[8],'notes_sha256':l[9].split()[0],'anchors':anchors,'runtime_minus_link':next(iter(anchors.values())),'runtime_arming_verified':True,'calibration_helper_absent':True},indent=2)+'\n')
 s,_=control.shell(phase,'module-hashes','cat /proc/sys/kernel/random/boot_id; find /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty -type f -exec sha256sum {} +; cat /proc/modules; cat /proc/sys/kernel/random/boot_id',timeout=8)
 l=s.splitlines();assert l[0]==l[-1]==boot
 actual={r.split()[1].removeprefix('/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/'):r.split()[0] for r in l if re.match(r'^[0-9a-f]{64}\s',r)}
 manifest=control.P/'validation'/('original-module-checksums.txt' if production else 'candidate-module-checksums.txt')
 expected={r.split(maxsplit=1)[1].strip():r.split()[0] for r in manifest.read_text().splitlines()}
 assert actual==expected

def run(production=False):
 phase='production' if production else 'target-run';p=control.P/phase;p.mkdir(exist_ok=False)
 verdict={'cpu_stall_repair_established':False,'budget_uptime_seconds':120}
 for i in range(20):
  s,rc=control.shell(phase,'poll-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',timeout=4,check=False)
  l=s.splitlines()
  if rc==0 and len(l)==3 and l[0]==l[-1]:break
  time.sleep(3)
 else:raise RuntimeError('no attributed response; inspect before any recovery action')
 boot=l[0];verdict.update(boot_id=boot,first_connection_uptime=float(l[1].split()[0]))
 command=[control.ADB,'-s',control.LIVE,'shell',f'journalctl -b {boot.replace("-", "")} -k -f -n all --no-pager -o json']
 stream=p/'kernel-follow.jsonl';started=time.monotonic()
 procmeta={'command':command,'utc':datetime.datetime.now(datetime.timezone.utc).isoformat()}
 with stream.open('wb') as output,(p/'kernel-follow.stderr').open('wb') as error:
  proc=subprocess.Popen(command,stdout=output,stderr=error)
  try:
   time.sleep(1);profile(phase,boot,production)
   for i in range(30):
    s,rc=control.shell(phase,'identity-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',timeout=5,check=False)
    text=stream.read_text(errors='replace');kind,markers=classify(text)
    if kind:
     verdict.update(verdict=kind,markers=markers)
     if kind=='failure_observed':time.sleep(20)
     break
    if rc!=0:
     verdict.update(verdict='inconclusive',reason='identity transport loss')
     # Preserve the existing source follower for late evidence; never start a new trial.
     time.sleep(20);break
    l=s.splitlines();assert len(l)==3 and l[0]==l[-1]==boot,'changed boot'
    uptime=float(l[1].split()[0]);verdict['uptime']=uptime
    assert proc.poll() is None and stream.stat().st_size,'stream ended/empty'
    if not production:
     assert 'Pseudo-NMIs enabled' in text and 'GTS9_LA_READY' in text and '2645198' in text
    print(phase,boot,uptime,flush=True)
    if uptime>=120:verdict['verdict']='clean_window';break
    time.sleep(min(5,max(0,120-uptime)))
   else:raise RuntimeError('observation budget exhausted')
   j,rc=control.shell(phase,'final-json',f'journalctl -b {boot.replace("-", "")} -k --no-pager -o json',timeout=10,check=False)
   kind,markers=classify(j+'\n'+stream.read_text(errors='replace'))
   if kind:verdict.update(verdict=kind,markers=markers)
   assert rc==0 and j,'missing final journal'
   rows=[json.loads(x) for x in j.splitlines()]
   assert rows and all(r['_BOOT_ID']==boot.replace('-','') for r in rows)
   verdict['final_rows']=len(rows);verdict['source_timestamp_rows']=sum('_SOURCE_BOOTTIME_TIMESTAMP' in r for r in rows)
   s,rc=control.shell(phase,'final-health','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; systemctl --failed --no-legend --plain --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=8,check=False)
   l=s.splitlines();assert rc==0 and l[0]==l[-1]==boot,'health identity failed'
   failed=[r.split()[0] for r in l[2:-1] if r.strip()]
   verdict['failed_units']=failed;verdict['overall_health_passed']=not failed
   assert set(failed)<= {'upower.service'},'new failed service'
   history,_=control.shell(phase,'boot-list','journalctl --list-boots --no-pager',timeout=8)
   ids=[l.split()[1] for l in history.splitlines() if re.match(r'^\s*-?\d+\s+[a-f0-9]{32}\s',l)]
   assert ids[-1]==boot.replace('-',''),'unexpected successor'
   if not production:
    source=json.loads((control.P/'preflight/source.json').read_text())['boot_id'].replace('-','')
    assert source in ids and ids[ids.index(source)+1:]==[boot.replace('-','')],'unexpected retained intermediate boot'
  except Exception as exc:
   if verdict.get('verdict') not in ['failure_observed','suspect']:verdict['verdict']='inconclusive'
   verdict['error']=repr(exc)
  finally:
   running=proc.poll() is None
   if running:proc.terminate()
   try:status=proc.wait(timeout=3)
   except subprocess.TimeoutExpired:proc.kill();status=proc.wait(timeout=3)
   procmeta.update(status=status,host_stopped_at_observation_end=running,elapsed_host_seconds=time.monotonic()-started)
   (p/'kernel-follow.json').write_text(json.dumps(procmeta,indent=2)+'\n')
   (p/'verdict.json').write_text(json.dumps(verdict,indent=2)+'\n')
 print(verdict,flush=True)
 assert verdict.get('verdict')=='clean_window','stop for evidence/recovery review'

if __name__=='__main__':
 import sys
 run('--production' in sys.argv)
