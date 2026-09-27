import control,json,subprocess,sys,re,hashlib
from pathlib import Path
sys.path.insert(0,'out/test244');import monitor
source='2094eeee-8fe2-48e5-aea6-abbc1788ea92'
s,_=control.shell('source','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; gts9_capture=$(cat /sys/module/gts9_lastactivity/parameters/capture_id); printf "capture=%s\n" "$gts9_capture"; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /proc/sys/kernel/printk; cat /sys/module/gts9_pnmi_test/parameters/enable; cat /sys/module/gts9_pnmi_test/parameters/status; cat /proc/cmdline; cat /sys/kernel/notes | sha256sum; cat /proc/sys/kernel/random/boot_id',timeout=10)
l=s.splitlines();assert l[0]==l[-1]==source and l[2]=='capture=' and l[3:8]==['64','1','1','1','10'] and l[8].split()[:2]==['5','4'] and l[9]=='N'
assert 'started=0' in l[10] and 'prio_masking=1' in l[10] and 'gts9_lastactivity=0' in l[11] and 'gts9_pnmi_test.enable=0' in l[11]
assert hashlib.sha256(Path('out/test241/kernel-notes.bin').read_bytes()).hexdigest()==l[12].split()[0]
j,_=control.shell('source','kernel-json','journalctl -b '+source.replace('-','')+' -k --no-pager -o json',timeout=12)
assert j and monitor.classify(j)[0] is None
control.shell('source','boot-list','journalctl --list-boots --no-pager',timeout=12)
control.shell('direct-reboot','sync','journalctl --sync; sync',timeout=15)
control.shell('direct-reboot','reboot','systemctl reboot',timeout=15)
subprocess.run([sys.executable,'out/test244/poll.py','target-poll',source],check=True)
subprocess.run([sys.executable,'out/test244/preflight.py'],check=True)
meta=json.loads((control.P/'target/identity.json').read_text());target=meta['boot_id']
history=(control.P/'target/boot-list.txt').read_text()
ids=[line.split()[1] for line in history.splitlines() if re.match(r'^\s*-?\d+\s+[0-9a-f]{32}\s',line)]
assert ids[ids.index(source.replace('-',''))+1]==target.replace('-','')
(control.P/'target/adjacency.json').write_text(json.dumps({'predecessor_boot_id':source,'target_boot_id':target,'immediate_retained_successor':True,'unrecorded_boots_excluded':False},indent=2)+'\n')
subprocess.run([sys.executable,'out/test244/monitor.py'],check=True)
