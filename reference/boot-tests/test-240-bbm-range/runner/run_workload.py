import control,json,hashlib,pathlib
meta=json.loads((control.P/'target/identity.json').read_text());boot=meta['boot_id']
s,_=control.shell('workload','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; timeout 5 systemctl --failed --no-pager; cat /sys/kernel/tracing/kprobe_events; cat /proc/sys/kernel/random/boot_id',timeout=10)
l=s.splitlines();assert l[0]==l[-1]==boot and float(l[1].split()[0])>=150 and l[2:6]==['1','1','1','10'] and '0 loaded units listed.' in s
j,_=control.shell('workload','before-journal','journalctl -b --no-pager -o short-monotonic',timeout=12)
assert 'GTS9_LA_BEGIN' not in j and not any(x in j for x in ('detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup'))
f=control.ROOT/'out/test240/bbm_workload.py';digest=hashlib.sha256(f.read_bytes()).hexdigest()
control.capture('workload','push',['push','D:\\android\\gts9-test240\\bbm_workload.py','/tmp/gts9-bbm-workload-240.py'],timeout=10)
s,_=control.shell('workload','hash','sha256sum /tmp/gts9-bbm-workload-240.py',timeout=6);assert s.split()[0]==digest
s,rc=control.shell('workload','run','timeout -k 2 40 python3 /tmp/gts9-bbm-workload-240.py',timeout=45,check=False)
print(s,flush=True)
control.shell('workload','after-identity','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/kernel/tracing/kprobe_events; test ! -d /sys/kernel/tracing/instances/gts9_bbm_240; echo instance_absent=$?; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=10,check=False)
control.shell('workload','after-journal','journalctl -b --no-pager -o short-monotonic',timeout=12,check=False)
assert rc==0,'workload failure or timeout; inspect archived output before any repeat'
rows=[json.loads(l) for l in s.splitlines() if l.startswith('{')]
assert all(r['boot_id']==boot for r in rows)
assert rows[-1]['phase']=='complete'
cpu=[r for r in rows if r['phase']=='cpu_complete'];assert {r['cpu'] for r in cpu}=={3,4} and all(r['iterations']>0 and r['seconds']>=8 for r in cpu)
assert any(r['phase']=='trace_verified' for r in rows)
(control.P/'workload/verdict.json').write_text(json.dumps({'boot_id':boot,'process_script_sha256':digest,'rows':rows,'cpu_stall_fix_established':False},indent=2)+'\n')
