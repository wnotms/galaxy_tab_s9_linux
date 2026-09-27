import control,json,hashlib,subprocess
from pathlib import Path
s,_=control.shell('target','preflight','cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /sys/module/gts9_lastactivity/parameters/capture_id; cat /sys/module/ramoops/parameters/ecc; cat /proc/sys/kernel/watchdog /proc/sys/kernel/soft_watchdog /proc/sys/kernel/softlockup_panic /proc/sys/kernel/panic; cat /proc/sys/kernel/printk; cat /sys/module/gts9_pnmi_test/parameters/enable; cat /sys/module/gts9_pnmi_test/parameters/status; cat /proc/cmdline; cat /sys/kernel/notes | sha256sum; grep -E " (_text|_stext|do_nothing|rcu_barrier_handler|irq_work_run|ipi_types)$" /proc/kallsyms; cat /proc/sys/kernel/random/boot_id',timeout=10)
l=s.splitlines();boot=l[0];cap=l[2]
assert l[-1]==boot and l[3:8]==['64','1','1','1','10'] and int(l[8].split()[0])==5 and int(l[8].split()[1])==4
assert l[9]=='N' and 'prio_masking=1' in l[10] and 'started=0' in l[10] and 'error=0' in l[10]
assert 'irqchip.gicv3_pseudo_nmi=1' in l[11] and 'gts9_pnmi_test.enable=0' in l[11] and 'gts9_pnmi_test.enable=1' not in l[11]
assert hashlib.sha256(Path('out/test241/kernel-notes.bin').read_bytes()).hexdigest()==l[12].split()[0]
link={}
for line in Path('out/test241/System.map').read_text().splitlines():
 a,t,n=line.split()[:3];link[n]=int(a,16)
anchors={row.split()[2]:int(row.split()[0],16)-link[row.split()[2]] for row in l[13:-1]};assert len(anchors)==6 and len(set(anchors.values()))==1
# Save verified identity before journal inspection so an early positive failure
# still retains this target's symbol/arming evidence.
(control.P/'target/identity.json').write_text(json.dumps({'boot_id':boot,'capture_id':cap,'runtime_arming_verified':True,'notes_match_vmlinux':True,'runtime_minus_link':next(iter(anchors.values())),'anchors':anchors,'calibration_enabled':False,'calibration_started':False,'pseudo_nmi_priority_masking':True},indent=2)+'\n')
j,_=control.shell('target','journal','journalctl -b '+boot.replace('-','')+' --no-pager -o short-monotonic',timeout=12)
assert 'Pseudo-NMIs enabled using' in j and 'GTS9_LA_READY id='+cap in j
assert not any(x in j for x in ('Could not request IRQ','Unexpected pseudo-NMI','pNMI forbidden','GTS9_PNMI_TEST_READY'))
control.shell('target','boot-list','journalctl --list-boots --no-pager',timeout=12)
print('Target identity and inactive calibration verified:',boot,cap,anchors)
