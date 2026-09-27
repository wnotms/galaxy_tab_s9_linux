import control,json,time,re
v=json.loads((control.P/'workload-retry/verdict.json').read_text());boot=v['boot_id'];end=v['rows'][-1]['monotonic']
s=(control.P/'workload-retry/after-identity.txt').read_text();assert s.splitlines()[0]==s.splitlines()[-1]==boot and 'instance_absent=0' in s and 'gts9_bbm_240' not in s
j=(control.P/'workload-retry/after-journal.txt').read_text();assert not any(t in j for t in ('detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup'))
for i in range(5):
 s,_=control.shell('post-workload','identity-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=10)
 l=s.splitlines();assert l[0]==l[-1]==boot and '0 loaded units listed.' in s
 uptime=float(l[1].split()[0]);print('uptime',uptime,'after workload',uptime-end,flush=True)
 j,_=control.shell('post-workload','journal-'+str(i),'journalctl -b --no-pager -o short-monotonic',timeout=12)
 assert not any(t in j for t in ('GTS9_LA_BEGIN','detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup'))
 if uptime-end>=60:break
 time.sleep(20)
else:raise SystemExit('Post-workload window not completed')
(control.P/'post-workload/verdict.json').write_text(json.dumps({'boot_id':boot,'uptime':uptime,'seconds_after_workload':uptime-end,'no_detected_cpu_failure':True,'cpu_stall_repair_established':False},indent=2)+'\n')
control.shell('post-workload','remove-temp','rm /tmp/gts9-bbm-workload-240.py',timeout=6)
