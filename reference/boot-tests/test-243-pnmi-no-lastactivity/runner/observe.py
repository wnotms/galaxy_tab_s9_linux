import control,time,sys,json
phase=sys.argv[1];boot=None
for i in range(7):
 s,r=control.shell(phase,'sample-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/cmdline; cat /sys/module/ramoops/parameters/ecc; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=10,check=False)
 if r!=0:raise SystemExit('Unresponsive observation')
 l=s.splitlines();assert l[0]==l[-1]
 if boot is None:boot=l[0]
 assert l[0]==boot
 print(l[:2],flush=True)
 j,_=control.shell(phase,'journal-'+str(i),'journalctl -b --no-pager -o short-monotonic',timeout=10)
 assert not any(x in j for x in ('detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup'))
 if float(l[1].split()[0])>=150:break
 time.sleep(25)
else:raise SystemExit('150 second target not reached')
