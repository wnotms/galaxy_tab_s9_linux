"""ADB-first ordering, retained startup events and independent NCM attribution."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import sm5440_passive_admission as a

BOOT = '1' * 32
CONFIG = 'a' * 64
NOTES = 'b' * 64
PREFIX = 'sm5440-passive 0-0063: '
PENDING = PREFIX + 'passive startup REVBLK awaiting two fresh confirmations'
CONFIRMED = PREFIX + 'passive startup REVBLK confirmed inactive; event retained'
EVENT = PREFIX + ('passive fault bitmap=0x80 INT=00 00 62 00 STATUS=00 00 20 00 '
                  'INT4-disable=00 INT4-wait=01 mode=01/01 CNTL2=f2 VBUSCNTL=e7 '
                  'VBATCNTL=37 PRTNCNTL=fe ADC=18 18 7a e0 00 00 5d 38 0c 76 20 '
                  'VBUS=4867000uV VBAT=3938000uV IBUS=0uA die=285 deciC')


def journal(*entries):
    rows = [(0, 'Linux version 7.2.0-rc3', 6), *entries]
    return '\n'.join(json.dumps({'_BOOT_ID': BOOT, '_SOURCE_BOOTTIME_TIMESTAMP': str(t),
                                 'PRIORITY': str(p), 'MESSAGE': msg}) for t, msg, p in rows)


class FakeRecorder:
    def __init__(self, folder):
        self.folder = folder
        self.calls = []
        self.raw = journal()
        self.health = 'Good'
        self.auth_status = 0
        self.auth_boot = BOOT
        self.failed = ''
        self.config = CONFIG
        self.code43 = []
        self.banner_ok = True
        self.health_boot = BOOT

    def adb(self, name, script, *args, **kwargs):
        self.calls.append(('adb', name))
        if name == 'identity':
            return f'{BOOT}\n10.0 40.0\n{self.config}  -\n{NOTES}  /sys/kernel/notes\n', 0
        if name == 'kernel-json':
            return self.raw, 0
        if name == 'health':
            return ('@@battery\nPOWER_SUPPLY_HEALTH=Good\nPOWER_SUPPLY_PRESENT=1\n'
                    'POWER_SUPPLY_CAPACITY=62\nPOWER_SUPPLY_TEMP=284\nPOWER_SUPPLY_VOLTAGE_NOW=3980000\n'
                    f'@@passive\nPOWER_SUPPLY_HEALTH={self.health}\nPOWER_SUPPLY_STATUS=Not charging\n'
                    'POWER_SUPPLY_ONLINE=1\nPOWER_SUPPLY_TEMP=285\nPOWER_SUPPLY_VOLTAGE_NOW=4867000\n'
                    'POWER_SUPPLY_CURRENT_NOW=0\n@@power-role\n[sink]\n@@data-role\n[device]\n'
                    f'@@failed\n{self.failed}\n@@boot\n{self.health_boot}\n'), 0
        return BOOT, 0

    def command(self, name, *args, **kwargs):
        self.calls.append(('host', name))
        return '[]', 0

    def ps(self, name, script, *args, **kwargs):
        self.calls.append(('ps', name))
        if name == 'windows-topology':
            return json.dumps({'adapters': [], 'addresses': [], 'routes': [],
                               'code43': self.code43}), 0
        return json.dumps({'ok': self.banner_ok}), 0 if self.banner_ok else 1

    def ssh(self, name, script, *args, **kwargs):
        self.calls.append(('ssh', name))
        return self.auth_boot, self.auth_status


class PassiveAdmissionTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.r = FakeRecorder(Path(tmp.name))

    def run_gate(self):
        return a.admit(self.r, BOOT, CONFIG, NOTES)

    def no_transport(self):
        self.assertFalse(any(method in ('host', 'ps', 'ssh') for method, name in self.r.calls))

    def test_clean_adb_evidence_precedes_ncm_and_never_retries(self):
        result = self.run_gate()
        self.assertEqual(self.r.calls[:3], [('adb', 'identity'), ('adb', 'kernel-json'), ('adb', 'health')])
        self.assertEqual(self.r.calls[-1], ('ssh', 'ncm-auth'))
        self.assertEqual(result['transport_retries'], 0)
        self.assertFalse(result['physical_window_completed'])

    def test_first_hardware_fault_saved_before_any_ssh(self):
        self.r.health = 'Unspecified failure'
        with self.assertRaisesRegex(a.p.CaptureError, 'passive health'):
            self.run_gate()
        self.assertIn(('adb', 'kernel-json'), self.r.calls)
        self.no_transport()

    def test_pending_health_is_not_accepted(self):
        self.r.health = 'Unknown'
        with self.assertRaises(a.p.CaptureError): self.run_gate()
        self.no_transport()

    def test_vbat_fault_never_whitelisted(self):
        self.r.raw = journal((1_000_000, PENDING, 4), (1_001_000, EVENT.replace('0x80', '0x82'), 4),
                             (3_000_000, CONFIRMED, 6))
        with self.assertRaisesRegex(a.p.CaptureError, 'non-REVBLK'): self.run_gate()
        self.no_transport()

    def test_accepted_startup_still_preserves_warning_classification(self):
        self.r.raw = journal((1_000_000, PENDING, 4), (1_001_000, EVENT, 4), (3_000_000, CONFIRMED, 6))
        result = self.run_gate()
        self.assertEqual(result['startup']['classification'], 'confirmed-inactive-startup-latch')
        self.assertTrue(result['startup']['warning_retained'])

    def test_missing_late_repeated_or_reordered_confirmation_stops(self):
        for rows in (
            ((1_000_000, PENDING, 4), (1_001_000, EVENT, 4)),
            ((1_000_000, PENDING, 4), (1_001_000, EVENT, 4), (6_000_001, CONFIRMED, 6)),
            ((1_000_000, PENDING, 4), (1_001_000, EVENT, 4), (3_000_000, CONFIRMED, 6), (4_000_000, EVENT, 4)),
            ((1_000_000, CONFIRMED, 6), (2_000_000, PENDING, 4), (2_001_000, EVENT, 4)),
        ):
            with self.assertRaises(a.p.CaptureError): a.startup_evidence(journal(*rows), BOOT)

    def test_real_test259_latch_has_no_confirmation(self):
        root = Path(__file__).resolve().parents[1]
        raw = (root / 'reference/boot-tests/test-259-sm5440-fault-provenance/attempt-02/first-fault-raw/kernel-json.txt').read_text()
        with self.assertRaisesRegex(a.p.CaptureError, 'missing/repeated'):
            a.startup_evidence(raw, '08af1c86643545918043f69d36d93807')

    def test_identity_and_cross_boot_refused(self):
        self.r.config = 'c' * 64
        with self.assertRaisesRegex(a.p.CaptureError, 'config/notes'): self.run_gate()
        self.no_transport()
        self.r.config = CONFIG; self.r.health_boot = '2' * 32
        with self.assertRaisesRegex(a.p.CaptureError, 'crossed reboot'): self.run_gate()
        self.no_transport()

    def test_empty_journal_kernel_panic_and_failed_unit_stop(self):
        for raw in ('', journal((1_000_000, 'Kernel panic - not syncing: test', 2))):
            self.r.raw = raw
            with self.assertRaises((a.p.CaptureError, ValueError)): self.run_gate()
            self.no_transport()
        self.r.raw = journal(); self.r.failed = 'bad.service failed'
        with self.assertRaisesRegex(a.p.CaptureError, 'systemd failed'): self.run_gate()
        self.no_transport()

    def test_ncm_failure_keeps_device_evidence_without_retry(self):
        self.r.auth_status = 255
        with self.assertRaisesRegex(a.p.CaptureError, 'no retry'): self.run_gate()
        self.assertEqual(self.r.calls.count(('ssh', 'ncm-auth')), 1)
        self.assertEqual(self.r.calls[-1], ('adb', 'ncm-failure-device'))
        self.assertIn(('host', 'wsl-route'), self.r.calls)
        self.assertIn(('ps', 'windows-topology'), self.r.calls)

    def test_ncm_wrong_boot_does_not_pass(self):
        self.r.auth_boot = '2' * 32
        with self.assertRaisesRegex(a.p.CaptureError, 'NCM boot attribution'): self.run_gate()

    def test_code43_and_banner_failure_stop_before_auth(self):
        self.r.code43 = [{'ConfigManagerErrorCode': 43}]
        with self.assertRaisesRegex(a.p.CaptureError, 'Code43'): self.run_gate()
        self.assertNotIn(('ssh', 'ncm-auth'), self.r.calls)
        self.r.code43 = []; self.r.banner_ok = False
        with self.assertRaisesRegex(a.p.CaptureError, 'bound banner'): self.run_gate()
        self.assertNotIn(('ssh', 'ncm-auth'), self.r.calls)
