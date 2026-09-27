import control,hashlib,json,re,subprocess
s,_=control.shell('target','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_lastactivity/parameters/capture_id; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /proc/cmdline; cat /sys/kernel/notes | sha256sum; grep -E " (_text|_stext|do_nothing|rcu_barrier_handler|irq_work_run|ipi_types)$" /proc/kallsyms; cat /proc/sys/kernel/random/boot_id',timeout=8)
l=s.splitlines();boot=l[0];cap=l[2]
assert l[-1]==boot and l[3:8]==['64','1','1','1','10'] and 'gts9_lastactivity=1' in l[8] and 'test_enable' not in l[8]
subprocess.run(['llvm-objcopy','--dump-section','.notes=out/test240/kernel-notes.bin','out/test240/vmlinux'],check=True)
from pathlib import Path
assert hashlib.sha256(Path('out/test240/kernel-notes.bin').read_bytes()).hexdigest() in l[9]
link={}
for row in Path('out/test240/System.map').read_text().splitlines():
 a,t,n=row.split()[:3];link[n]=int(a,16)
anchors={row.split()[2]:int(row.split()[0],16)-link[row.split()[2]] for row in l[10:-1]}
assert len(anchors)==6 and len(set(anchors.values()))==1
(control.P/'target/identity.json').write_text(json.dumps({'boot_id':boot,'capture_id':cap,'runtime_arming_verified':True,'notes_match_vmlinux':True,'runtime_minus_link':next(iter(anchors.values())),'anchors':anchors},indent=2)+'\n')
print(boot,cap,anchors)
control.shell('target','boot-list','journalctl --list-boots --no-pager',timeout=12)
