import importlib.util,json,sys
from pathlib import Path
r=Path('reference/boot-tests/test-292-passive-observation');s=importlib.util.spec_from_file_location('h292',r/'host_flow.py');h=importlib.util.module_from_spec(s);s.loader.exec_module(h)
args=['ssh','-i','/home/ms/.ssh/gts9_ed25519','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','StrictHostKeyChecking=yes','-o','UserKnownHostsFile='+str(h.TRUST),'-o','HostKeyAlias=gts9-test292','root@10.125.29.240']
rec=h.p.Recorder(r/'stopped-endpoint')
jobs=h.parallel({'kernel':lambda:rec.command('kernel-json-wifi',args+['journalctl -k -b -o json --no-pager'],timeout=15),'boots':lambda:rec.command('boots-after-wifi',args+['journalctl --list-boots --no-pager'],timeout=10),'absence':lambda:rec.command('observer-absent-wifi',args+['set -e; test ! -e /sys/module/sm5440_passive_observer; test ! -e /sys/kernel/debug/sm5440-passive-observer; cat /proc/sys/kernel/random/boot_id'],timeout=10)})
sec=h.g.baseline.sections((rec.folder/'current-state-wifi.txt').read_text());boot,health=h.g.identity(sec,h.PLAN,h.PLAN['candidate_notes_sha256'],'b8945a982675454582302d26fbd232d4');known={x['MESSAGE'] for line in (r.parent/'test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt').read_text().splitlines() if int((x:=json.loads(line)).get('PRIORITY',7))<=3}
scan=h.g.journal(jobs['kernel'][0],boot,known,float(sec['uptime'].split()[0]),sec,h.PLAN,h.PLAN['candidate_notes_sha256']);h.write(rec.folder/'journal-classification.json',scan)
assert h.g.evidence.attribute(h.PLAN['before_boot_id'],boot,(r/'preflight/boots-before.txt').read_text(),jobs['boots'][0])=='attributed'
# Record source boot solely for rollback attribution, not acquisition admission.
h.write(r/'candidate-admission/rollback-source.json',dict(boot_id=boot,verdict='STOP_ADB_TRANSPORT',observer_loads=0,observer_calls=0));(r/'candidate-admission/boots-after.txt').write_text(jobs['boots'][0])
print('STOP raw journal and unique boot saved; Wi-Fi safety recovery',flush=True)
rec=h.p.Recorder(r/'rollback-install')
rec.command('helper-check-wifi',args+['TMPDIR=/tmp gts9-debian-to-recovery --check'],timeout=10)
rec.command('bcb-request-wifi',args+['TMPDIR=/tmp gts9-debian-to-recovery --yes --no-reboot'],timeout=10)
rec.command('ordinary-reboot-wifi',args+['systemctl reboot'],timeout=10,required=False)
h.write(rec.folder/'recovery-wait.json',h.recovery.wait_recovery(rec));h.p.SERIAL='R52X10045LT'
identity,_=rec.adb('twrp-identity','set -e; getprop ro.product.device; uname -a; id; test "$(blockdev --getsize64 /dev/block/by-name/boot)" = 100663296; test "$(blockdev --getsize64 /dev/block/by-name/misc)" = 1048576',timeout=10)
assert 'gts9wifi' in identity and 'uid=0' in identity and '7.2.0-rc3' not in identity
rec.adb('ancillary','echo @@recovery-dmesg; dmesg; echo @@pstore; ls -la /sys/fs/pstore; for f in /sys/fs/pstore/* /proc/last_kmsg; do if test -f "$f"; then echo @@source=$f; cat "$f"; else echo unavailable=$f; fi; done',timeout=15)
h.transfer(rec)
raw,_=rec.adb('partitions-before',h.PARTS,timeout=20);h.require_partitions(raw,h.PACKAGE['candidate_partitions'])
rec.adb('remount-rw','mount -o remount,rw /mnt/debian',timeout=10)
rec.adb('restore-modules',f'sh {h.TMP}/module-swap.sh /mnt/debian restore {h.TMP}/rollback-modules.sha256',timeout=25)
h.write_boot(rec,'restore-boot','rollback-test263-boot.img',h.PACKAGE['candidate_partitions']['boot'],h.PACKAGE['baseline_partitions']['boot'])
raw,_=rec.adb('partitions-after',h.PARTS,timeout=20);h.require_partitions(raw,h.PACKAGE['baseline_partitions'])
rec.adb('backup-list','find /mnt/debian/usr/lib/modules -maxdepth 1 -name ".gts9-test*"',timeout=10)
h.clear_unmount(rec);h.write(rec.folder/'summary.json',dict(verdict='EXACT263_ROLLBACK_READBACK_VERIFIED',partitions=h.PACKAGE['baseline_partitions'],modules=181,rescue_entry='strictauthenticatedWi-Fi; ADBunavailable'))
print('exact263 all5/181 restored; final baseline boot',flush=True)
rec.host_adb('normal-reboot','-s',h.p.SERIAL,'reboot',timeout=10)
summary,boots=h.boundary(r/'final-acceptance',h.PLAN['baseline_notes_sha256'],boot,jobs['boots'][0]);print(json.dumps(summary,indent=2),flush=True)
