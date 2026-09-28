"""Read-only Test253 evidence/identity gate; no deployment or gadget operations."""
from pathlib import Path
import sys, json, hashlib, base64, re, os
sys.path.insert(0, str(Path('scripts').resolve()))
import production_reboot_stability as p
from adbd_reconnect_evidence import classify_failed_units, same_cmdline
TEST253 = Path('reference/boot-tests/test-253-adbd-usb-reconnect')
ROOT = TEST253/'attempt-03'
T252 = Path('reference/boot-tests/test-252-sm5714-stage1')
WIFI = os.environ.get('GTS9_TEST253_WIFI', '10.191.121.195')
p.P = p.TEST250_ROOT/'attempt-05'
base = p.baseline()
art = json.loads((T252/'ARTIFACTS.json').read_text())
expected = dict(base, config_sha256=art['kernel_artifacts']['config'], notes_sha256=art['kernel_notes_sha256'])
phase = sys.argv[1]
full = '--full' in sys.argv
allow_offline = '--offline-allowed' in sys.argv
allow_absent = '--native-absent' in sys.argv
folder = ROOT/phase
class WifiRecorder(p.Recorder):
    def adb(self, name, script, timeout=15, required=True):
        return self.command(name, ['env', 'GTS9_DEVICE='+WIFI, p.SSH, script], timeout, required)
rec = WifiRecorder(folder)
try:
    try:
        state = p.production_state(rec, expected, full=False)
    except p.CaptureError:
        state = json.loads((folder/'production-state.json').read_text())
        # Preserve the original false identity_ok result, then independently
        # require every identity gate and the explicitly recognized failed unit.
        assert state['profile_ok'] and state['dcc_absent']
        assert state['config_sha256'] == expected['config_sha256']
        assert state['notes_sha256'] == expected['notes_sha256']
        assert p.RELEASE in state['uname']
        assert p.evidence.canonical_boot_id((folder/'boot-id-confirm.txt').read_text().strip()) == state['boot_id']
        assert state['failed_units']
    up_props = rec.adb('upower-properties', 'systemctl show upower.service -p Result -p ExecMainStatus -p PrivateUsers')[0]
    up_sha = rec.adb('upower-unit-sha256', 'sha256sum /usr/lib/systemd/system/upower.service')[0].split()[0]
    up_config = rec.adb('upower-config', 'zcat /proc/config.gz | grep CONFIG_USER_NS')[0]
    units = classify_failed_units((folder/'systemd-failed.txt').read_text(), up_props, up_sha, up_config)
    p.write_json(folder/'systemd-classification.json', units)
    assert same_cmdline((folder/'cmdline.txt').read_bytes(), (T252/'attempt-01/boot/acceptance/cmdline.txt').read_bytes())
    cfg = rec.adb('embedded-config', 'zcat /proc/config.gz', 25)[0]
    assert hashlib.sha256(cfg.encode()).hexdigest() == expected['config_sha256']
    notes = base64.b64decode(''.join(rec.adb('notes-base64', 'base64 /sys/kernel/notes')[0].split()), validate=True)
    assert hashlib.sha256(notes).hexdigest() == expected['notes_sha256']
    (folder/'kernel-notes.bin').write_bytes(notes)
    if full:
        parts = rec.adb('partitions', 'for n in boot vendor_boot init_boot dtbo vbmeta; do sha256sum /dev/disk/by-partlabel/$n; done', 45)[0]
        exparts = {n:v['accepted_device_sha256'] for n,v in art['partitions'].items()}
        exparts['boot'] = art['partitions']['boot']['candidate_sha256']
        assert p.parse_hashes(parts, '/dev/disk/by-partlabel/') == exparts
        mods = rec.adb('module-hashes', f'find {p.MODULE_ROOT} -type f -exec sha256sum {{}} +', 45)[0]
        assert p.parse_hashes(mods, p.MODULE_ROOT+'/') == json.loads((T252/'validation/module-hashes.json').read_text())
        old = rec.adb('backup-module-hashes', 'find /usr/lib/modules/.gts9-test252-original -type f -exec sha256sum {} +', 45)[0]
        assert p.parse_hashes(old, '/usr/lib/modules/.gts9-test252-original/') == base['modules']
        rec.adb('module-directories', 'find /usr/lib/modules -maxdepth 1 -type d -print')
    settings = rec.adb('protected-settings-hashes', r'''set -eu
for f in /etc/gts9-usb-net /etc/gts9-usb-adb /usr/libexec/gts9-adbd-can-start /usr/libexec/gts9-usb-adb-hold /usr/libexec/gts9-usb-adb-prepare /usr/libexec/gts9-usb-acm /usr/lib/systemd/system/gts9-usb-acm.service /usr/lib/systemd/system/gts9-usb-adb-hold.service /usr/lib/systemd/system/gts9-usb-adb-prepare.service /usr/lib/android-sdk/platform-tools/adbd /root/.ssh/authorized_keys; do sha256sum "$f"; done
find /etc/ssh -type f -exec sha256sum {} + | sort
''')[0]
    assert settings == (TEST253/'attempt-02/preflight-verified/protected-settings-hashes.txt').read_text()
    rec.adb('userspace-state', r'''set -eu
systemctl cat gts9-adbd.service
p=$(systemctl show -p MainPID --value gts9-adbd.service)
printf 'PID=%s\n' "$p"
readlink /proc/$p/exe
sha256sum /proc/$p/exe
ps -T -p "$p" -o pid,tid,comm,wchan:32
printf 'UDC='; cat /sys/kernel/config/usb_gadget/gts9/UDC
find /sys/kernel/config/usb_gadget -maxdepth 5 -type l -print
cat /proc/self/mountinfo | grep usb-ffs
''')[0]
    rec.adb('usb-adbd-journal', 'journalctl -b --no-pager -o short-monotonic -u gts9-adbd -u gts9-usb-acm -u gts9-usb-adb-hold -u gts9-usb-adb-prepare', 30)
    raw = rec.adb('kernel-journal-json', 'journalctl -k -b --no-pager -o json', 35)[0]
    rec.adb('kernel-journal', 'journalctl -k -b --no-pager -o short-monotonic', 35)
    scan = p.inspect(raw, state['boot_id'], base, state['uptime_seconds'])
    p.write_json(folder/'kernel-scan.json', scan)
    assert not scan['fault_counts'] and not scan['suspects'], scan
    history = rec.adb('boot-history', 'journalctl --list-boots --no-pager', 20)[0]
    assert p.evidence.boot_list(history)[-1] == state['boot_id']
    sup = rec.adb('supplies', 'cat /sys/class/power_supply/sm5714-battery/uevent; cat /sys/class/power_supply/sm5714-usb/uevent')[0]
    props = dict(line.split('=',1) for line in sup.splitlines() if line.startswith('POWER_SUPPLY_'))
    assert props['POWER_SUPPLY_HEALTH'] == 'Good'
    assert 100 <= int(props['POWER_SUPPLY_TEMP']) < 420
    assert int(props['POWER_SUPPLY_VOLTAGE_NOW']) <= 4440000
    adb, _ = rec.host_adb('adb-state', 'devices', '-l')
    adb_ok = re.search(r'^gts9wifi-0001\s+device\b', adb, re.M) is not None
    if allow_absent:
        assert adb.strip() == 'List of devices attached', adb
        actual = rec.adb('absent-target-daemon', 'p=$(systemctl show -p MainPID --value gts9-adbd.service); echo "$p"; readlink /proc/$p/exe; sha256sum /proc/$p/exe')[0].splitlines()
        assert actual[0] == '834' and actual[1] == '/usr/local/libexec/gts9-adbd-reconnect'
        assert actual[2].split()[0] == json.loads((TEST253/'build/manifest.json').read_text())['binary_sha256']
    elif allow_offline:
        assert re.search(r'^gts9wifi-0001\s+offline\b', adb, re.M)
    else:
        assert adb_ok, adb
        adb_boot, _ = rec.host_adb('native-adb-shell', '-s', p.SERIAL, 'shell', 'cat /proc/sys/kernel/random/boot_id', timeout=12)
        assert p.evidence.canonical_boot_id(adb_boot.strip()) == state['boot_id']
        patched = json.loads((TEST253/'build/manifest.json').read_text())['binary_sha256']
        exe = rec.adb('patched-executable', 'p=$(systemctl show -p MainPID --value gts9-adbd.service); readlink /proc/$p/exe; sha256sum /proc/$p/exe')[0]
        assert exe.splitlines()[0] == '/usr/local/libexec/gts9-adbd-reconnect'
        assert exe.splitlines()[1].split()[0] == patched
    pnp, _ = rec.ps('windows-pnp', p.PS_USB, timeout=30)
    assert not p.has_code43(pnp)
    banner, _ = rec.ps('windows-ncm-banner', p.PS_NCM_BOUND_BANNER, timeout=30)
    assert p.bound_banner_ok(banner), banner
    ncm, _ = rec.ssh('ncm-authenticated-ssh', 'cat /proc/sys/kernel/random/boot_id', timeout=18)
    assert p.evidence.canonical_boot_id(ncm.strip()) == state['boot_id']
    after = rec.adb('end-boot-id', 'cat /proc/sys/kernel/random/boot_id')[0]
    assert p.evidence.canonical_boot_id(after.strip()) == state['boot_id']
    report = dict(verdict='passed', phase=phase, boot_id=state['boot_id'], uptime_seconds=state['uptime_seconds'], full_identity=full, candidate_config_sha256=expected['config_sha256'], notes_sha256=expected['notes_sha256'], dcc_absent=True, kernel_scan=scan, failed_units=units['failed_units'], systemd_classification=units, adb_ok=adb_ok, adb_offline_repair_target=allow_offline, native_absent_repair_target=allow_absent, ncm_ssh_ok=True, wifi_ssh_ok=True, code43=False, protected_settings_unchanged=True, pack_temperature_deciC=int(props['POWER_SUPPLY_TEMP']), soc=int(props['POWER_SUPPLY_CAPACITY']))
    p.write_json(folder/'summary.json', report)
    print(json.dumps(report, indent=2))
except Exception as exc:
    p.write_json(folder/'failure.json', dict(phase=phase, error=repr(exc)))
    raise
