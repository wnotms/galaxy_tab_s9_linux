import control,json,time,re,subprocess
meta=json.loads((control.P/'target/identity.json').read_text());boot=meta['boot_id'];cal=meta['calibration_id']
s,_=control.shell('calibration','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /proc/sys/kernel/printk; cat /sys/module/gts9_pnmi_test/parameters/status; timeout 5 systemctl --failed --no-pager; cat /proc/sys/kernel/random/boot_id',timeout=10)
l=s.splitlines();assert l[0]==l[-1]==boot and float(l[1].split()[0])>=150 and l[2:6]==['1','1','1','10'] and int(l[6].split()[0])>=5 and 'started=0' in l[7] and '0 loaded units listed.' in s
j,_=control.shell('calibration','before-journal','journalctl -b --no-pager -o short-monotonic',timeout=12)
assert not any(x in j for x in ('GTS9_LA_BEGIN','detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup'))
control.shell('calibration','trigger','printf 1 > /sys/module/gts9_pnmi_test/parameters/run',timeout=6)
for i in range(10):
 time.sleep(2)
 s,_=control.shell('calibration','status-'+str(i),'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_pnmi_test/parameters/status; cat /proc/sys/kernel/random/boot_id',timeout=6)
 l=s.splitlines();assert l[0]==l[-1]==boot
 fields=dict(x.split('=',1) for x in l[2].split());print(fields,flush=True)
 if fields['receiver_done']==fields['sender_done']=='1':break
else:raise SystemExit('Calibration workers did not finish within collection window')
for key in ('started','observed','nmi','saved_irq_disabled','prio_masking'):assert fields[key]=='1',(key,fields)
assert fields['holding']=='0' and fields['error']=='0'
start,end,seen=[int(fields[k]) for k in ('start_ns','end_ns','seen_ns')]
assert start<=seen<=end and end-start>=200000000 and int(fields['pc'],16)!=0 and (int(fields['pstate'],16)&0x80)==0
for i in range(4):
 j,_=control.shell('calibration','journal-'+str(i),'journalctl -b --no-pager -o short-monotonic',timeout=12)
 if 'GTS9_PNMI_TEST_END id='+cal in j and 'NMI backtrace for cpu 0' in j and 'gts9_pnmi_masked_region+' in j:break
 time.sleep(2)
else:raise SystemExit('No complete target backtrace for calibration')
assert not any(x in j for x in ('GTS9_LA_BEGIN','detected stalls',"CPUS still haven't responded",'BUG: workqueue lockup','soft lockup','Unexpected pseudo-NMI'))
pc=int(fields['pc'],16)-meta['runtime_minus_link']
r=subprocess.run(['llvm-addr2line','-e','out/test241/vmlinux','-f','-i',hex(pc)],capture_output=True,text=True,check=True)
(control.P/'calibration/pc-symbol.txt').write_text(r.stdout)
verdict={'boot_id':boot,'calibration_id':cal,'status':fields,'masked_elapsed_ns':end-start,'observed_ns_after_start':seen-start,'interrupted_pc_link_address':hex(pc),'pc_symbol':r.stdout,'in_window_nmi_capture':True,'cpu_stall_repair_established':False}
(control.P/'calibration/verdict.json').write_text(json.dumps(verdict,indent=2)+'\n');print(verdict)
_,rc=control.shell('calibration','second-trigger','printf 1 > /sys/module/gts9_pnmi_test/parameters/run',timeout=6,check=False);assert rc!=0
