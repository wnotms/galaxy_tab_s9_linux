import control,importlib.util,json,time
spec=importlib.util.spec_from_file_location('evidence',control.ROOT/'scripts/lastactivity-evidence.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
s,_=control.shell('source','injection-preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_lastactivity/parameters/capture_id; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /proc/sys/kernel/printk; cat /proc/sys/kernel/panic_on_rcu_stall; cat /sys/module/rcupdate/parameters/rcu_cpu_stall_timeout /sys/module/rcupdate/parameters/rcu_cpu_stall_suppress; cat /sys/module/gts9_lastactivity/parameters/test_enable /sys/module/gts9_lastactivity/parameters/test_status; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=12)
l=s.splitlines();boot=l[0];cap=l[2]
assert float(l[1].split()[0])>=150 and l[3]=='64' and l[4:8]==['1','1','1','10'] and int(l[8].split()[0])>0
assert l[9:14]==['0','21','0','Y','started=0 finished=0 gp_done=0'],l
assert l[-1]==boot and '0 loaded units listed.' in s
j,_=control.shell('source','before-injection-journal','journalctl -b --no-pager -o short-monotonic',timeout=12)
assert 'GTS9_LA_READY id='+cap in j and 'GTS9_LA_BEGIN' not in j
bad=('detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup')
assert not any(x in j for x in bad)
(control.P/'source/identity.json').write_text(json.dumps({'boot_id':boot,'capture_id':cap},indent=2)+'\n')
control.shell('source','trigger','printf 1 > /sys/module/gts9_lastactivity/parameters/test_run',timeout=8)
for i in range(12):
 time.sleep(5)
 s,_=control.shell('source','status-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_lastactivity/parameters/test_status',timeout=5)
 print(s,flush=True);assert s.splitlines()[0]==boot
 if 'finished=1 gp_done=1' in s:break
else:raise SystemExit('Reader/callback did not finish in bounded collection window')
for i in range(4):
 j,_=control.shell('source','auto-snapshot-'+str(i),'journalctl -b --no-pager -o short-monotonic',timeout=12)
 assert not any(x in j for x in ("CPUS still haven't responded",'BUG: workqueue lockup','soft lockup'))
 try:r=m.parse(j,cap)
 except ValueError:
  time.sleep(2);continue
 if 'GTS9_LA_TEST_END id='+cap not in j:
  time.sleep(2);continue
 assert r['trigger']=='rcu' and len(r['records'])==48 and all(c['valid'] for c in r['cpus'].values())
 assert 'GTS9_LA_TEST_BEGIN id='+cap in j and 'detected stalls' in j
 (control.P/'source/snapshot.json').write_text(json.dumps(r,indent=2)+'\n')
 (control.P/'source/snapshot-journal-complete.txt').write_bytes((control.P/'source'/('auto-snapshot-'+str(i)+'.txt')).read_bytes())
 print({k:v for k,v in r.items() if k not in ('cpus','records')},flush=True)
 break
else:raise SystemExit('No complete attributed automatic capture')
control.shell('source','boot-list','journalctl --list-boots --no-pager',timeout=12)
# Controlled panic is separate, after human-readable review of this evidence.
