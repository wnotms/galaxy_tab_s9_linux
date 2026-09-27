"""One registered target; stops for evidence review on any non-clean result."""
import hashlib,json,re
from pathlib import Path
import control,modules,observe
P=control.P
source=json.loads((P/'preflight/source.json').read_text())
# Require the built/package evidence before initiating a reboot.
assert json.loads((P/'validation/build.json').read_text())['status']==0
assert json.loads((P/'validation/bundle-validation.json').read_text())['status']==0
assert not (P/'target-run').exists(), 'one-target budget already used'
for name,entry in json.loads((P/'validation/package-artifacts.json').read_text()).items():
    assert hashlib.sha256((control.ROOT/name).read_bytes()).hexdigest()==entry['sha256']
s,_=control.shell('deploy-preflight','source',
    'cat /proc/sys/kernel/random/boot_id; cat /proc/uptime; cat /proc/sys/kernel/random/boot_id',timeout=6)
l=s.splitlines();assert l[0]==l[-1]==source['boot_id']
s,_=control.shell('deploy-preflight','module-hashes',
    'find /usr/lib/modules/7.2.0-rc3-gts9wifi-dirty -type f -exec sha256sum {} +',timeout=8)
actual={r.split()[1].removeprefix('/usr/lib/modules/7.2.0-rc3-gts9wifi-dirty/'):r.split()[0]
        for r in s.splitlines() if re.match(r'^[a-f0-9]{64}\s',r)}
expected={r.split(maxsplit=1)[1]:r.split()[0] for r in
          (P/'validation/original-module-checksums.txt').read_text().splitlines()}
assert actual==expected and len(actual)==181
control.recover('initial-to-recovery')
control.poll('baseline-poll',recovery=True,tries=10)
control.recovery_capture('baseline')
expected={
    'boot':'71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d',
    'vendor_boot':'49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9',
    'init_boot':'1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0',
    'dtbo':'c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3',
    'vbmeta':'9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4',
}
actual={r.split()[1].rsplit('/',1)[-1]:r.split()[0] for r in
        (P/'baseline/partitions.txt').read_text().splitlines() if '/dev/block/by-name/' in r}
assert actual==expected
modules.swap('module-install')
control.flash('flash')
modules.reboot('target-reboot','flash','module-install')
observe.run()
