import control,json,time,importlib.util,sys
control.P=control.P/sys.argv[1]
spec=importlib.util.spec_from_file_location('evidence',control.ROOT/'scripts/lastactivity-evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s,_=control.shell('target','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_lastactivity/parameters/capture_id; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /proc/cmdline; cat /proc/sys/kernel/random/boot_id',timeout=8)
l=s.splitlines();boot=l[0];cap=l[2]
assert l[-1]==boot and l[3:8]==['64','1','1','1','10'] and 'gts9_lastactivity=1' in l[8] and 'test_enable' not in l[8]
(control.P/'target/identity.json').write_text(json.dumps({'boot_id':boot,'capture_id':cap,'runtime_arming_verified':True},indent=2)+'\n')
verdict={'boot_id':boot,'capture_id':cap,'root_cause':'unresolved'}
for i in range(35):
 s,rc=control.shell('target','identity-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',timeout=6,check=False)
 if rc!=0:
  verdict.update(verdict='unattributed',reason='identity transport failure');break
 lines=s.splitlines()
 if lines[0]!=lines[-1] or lines[0]!=boot:
  verdict.update(verdict='unattributed',reason='unexpected boot change');break
 uptime=float(lines[1].split()[0]);print('target uptime',uptime,flush=True)
 j,rc=control.shell('target','journal-'+str(i),'journalctl -b '+boot.replace('-','')+' --no-pager -o short-monotonic',timeout=8,check=False)
 if 'GTS9_LA_BEGIN id='+cap in j:
  try:
   result=m.parse(j,cap)
   (control.P/'target/snapshot.json').write_text(json.dumps(result,indent=2)+'\n')
   (control.P/'target/snapshot-reference.txt').write_bytes((control.P/'target'/('journal-'+str(i)+'.txt')).read_bytes())
   print('Saved automatic snapshot',result['snapshot_sha256'],flush=True)
  except ValueError as e: print('Snapshot not yet complete:',e,flush=True)
 bad=[x for x in ("CPUS still haven't responded",'unresponsive','BUG: workqueue lockup','soft lockup','detected stalls','CSD lock') if x in j]
 if bad:
  verdict.update(verdict='failure_observed',markers=bad,uptime=uptime,journal='journal-'+str(i)+'.txt');break
 if rc!=0 or not j:
  verdict.update(verdict='unattributed',reason='journal fetch failure');break
 suspect=[x for x in ('vblank wait timed out','CTL_START timeout','Timeout waiting for hardware cmd interrupt','rpmh_rsc_send_data: Error') if x in j]
 if suspect:
  verdict.update(verdict='suspect',markers=suspect,uptime=uptime);break
 if uptime>=180:
  verdict.update(verdict='clean_window',uptime=uptime,journal='journal-'+str(i)+'.txt');break
 time.sleep(10)
else: verdict.update(verdict='unattributed',reason='iteration budget exhausted')
(control.P/'target/verdict.json').write_text(json.dumps(verdict,indent=2)+'\n');print(verdict,flush=True)
