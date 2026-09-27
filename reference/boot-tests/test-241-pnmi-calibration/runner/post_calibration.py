import control,json,time
v=json.loads((control.P/'calibration/verdict.json').read_text());boot=v['boot_id'];end=int(v['status']['end_ns'])/1e9
for i in range(5):
 s,_=control.shell('post-calibration','identity-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=10)
 l=s.splitlines();assert l[0]==l[-1]==boot and '0 loaded units listed.' in s
 uptime=float(l[1].split()[0]);print('uptime',uptime,'after calibration',uptime-end,flush=True)
 j,_=control.shell('post-calibration','journal-'+str(i),'journalctl -b --no-pager -o short-monotonic',timeout=12)
 assert not any(t in j for t in ('GTS9_LA_BEGIN','detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup','Unexpected pseudo-NMI'))
 if uptime-end>=60:break
 time.sleep(20)
else:raise SystemExit('Post-calibration observation incomplete')
(control.P/'post-calibration/verdict.json').write_text(json.dumps({'boot_id':boot,'uptime':uptime,'seconds_after_calibration':uptime-end,'no_detected_cpu_failure':True,'cpu_stall_repair_established':False},indent=2)+'\n')
