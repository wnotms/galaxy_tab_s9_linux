import sys,json,subprocess,time,hashlib
from pathlib import Path
sys.path.insert(0,str(Path('scripts').resolve()));import production_reboot_stability as p
A=Path('reference/boot-tests/test-254-debian-container-kernel/attempt-02');reg=json.loads((A/'registration.json').read_text());r=p.Recorder(A/'enter-recovery')
head=subprocess.check_output(['git','rev-parse','HEAD']).strip();assert head==subprocess.check_output(['git','rev-parse','origin/test']).strip();assert subprocess.check_output(['git','status','--porcelain']).strip()==b''
raw=r.adb('immediate-baseline','cat /proc/sys/kernel/random/boot_id; zcat /proc/config.gz | sha256sum; sha256sum /sys/kernel/notes; for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done',45)[0]
lines=raw.splitlines();assert p.evidence.canonical_boot_id(lines[0])==reg['preflight_boot_id'];assert lines[1].split()[0]==reg['rollback_config_sha256'];assert p.parse_hashes('\n'.join(lines[3:]),'/dev/disk/by-partlabel/')==reg['original_partitions']
r.host_adb('push-helper','-s',p.SERIAL,'push','D:/android/gts9-active/gts9-test254/to-recovery.sh','/tmp/test254-to-recovery.sh',timeout=20)
raw=r.adb('helper-hash','sha256sum /tmp/test254-to-recovery.sh')[0];assert raw.split()[0]==hashlib.sha256(Path('boot/gts9-debian-to-recovery.sh').read_bytes()).hexdigest()
raw=r.adb('bcb-check','TMPDIR=/tmp sh /tmp/test254-to-recovery.sh --check')[0];assert '(empty, boots mainline)' in raw
r.adb('bcb-request','TMPDIR=/tmp sh /tmp/test254-to-recovery.sh --yes --no-reboot',25)
r.adb('plain-reboot','systemctl reboot',20,required=False)
start=time.monotonic()
for n in range(35):
    raw,code=r.host_adb('wait-recovery-%02d'%n,'devices','-l',timeout=8,required=False)
    if 'R52X10045LT' in raw and 'recovery' in raw:print('TWRP available',time.monotonic()-start,flush=True);break
    time.sleep(2)
else:raise RuntimeError('recovery not observed within bounded wait; no flash')
