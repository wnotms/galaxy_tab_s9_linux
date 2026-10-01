"""Host-only parser/gate checks. No device command, flash, or observer load."""
import copy
import json
from pathlib import Path
import unittest
import gate

A = Path(__file__).resolve().parent


def record(state=1, status=0, count=8):
    head = dict(gate.HEADER, state=str(state), count=str(count))
    rows = []
    for i in range(count):
        start = 1000 + i * 1050
        row = dict(row=i+1, request_ms=start, return_ms=start+50,
                   provider_status=status if i+1 == count else 0,
                   status=status if i+1 == count else 0, usable=int(not status or i+1 != count),
                   acquisition_ms=start+1, raw_vbus_uv=5000000, raw_vbat_uv=4000000,
                   raw_ibus_ua=0, raw_die_decic=300, raw_online=1)
        rows.append(' '.join(f'{k}={v}' for k, v in row.items()))
    return '\n'.join([f'{k}={v}' for k, v in head.items()] + rows)


class Observer(unittest.TestCase):
    def test_eight_calls(self):
        out = gate.observer(record())
        self.assertEqual((out['count'], out['delivery_ms_max'], out['acquisition_outcome']), (8, 50, 'EIGHT_FRESH_DELIVERIES'))
        self.assertFalse(out['charging_authorized'])

    def test_first_busy_refusal(self):
        out = gate.observer(record(2, -16, 1))
        self.assertEqual((out['first_refusal'], out['rows'][0]['status']), (1, -16))

    def test_timeout_refusal_not_pass(self):
        self.assertEqual(gate.observer(record(2, -110, 1))['acquisition_outcome'], 'REFUSED')

    def test_running_not_pass(self):
        self.assertEqual(gate.observer(record(0, 0, 1))['acquisition_outcome'], 'INCOMPLETE')

    def test_malformed(self):
        cases = ['', record().replace('count=8', 'count=7'), record()+'\nstate=1',
                 record().replace('row=2 ', 'row=1 '), record().replace('maximum_calls=8', 'maximum_calls=9'),
                 record().replace('PPS_authorized=0', 'PPS_authorized=1'),
                 record().replace('usable=1', 'usable=0'), record(2, -16, 1).replace('status=-16', 'status=0'),
                 record().replace('return_ms=1050', 'return_ms=1101'),
                 record().replace('acquisition_ms=1001', 'acquisition_ms=999'),
                 record().replace('raw_ibus_ua=0', 'raw_ibus_ua=100'),
                 record().replace('raw_vbus_uv=5000000', 'raw_vbus_uv=9000000'),
                 record().replace('raw_vbat_uv=4000000', 'raw_vbat_uv=4300000'),
                 record().replace('raw_die_decic=300', 'raw_die_decic=420'),
                 record().replace('request_ms=2050', 'request_ms=2049')]
        for case in cases:
            with self.subTest(case=case[:70]):
                with self.assertRaises(ValueError): gate.observer(case)

    def test_no_call_after_error(self):
        bad = record().replace('provider_status=0 status=0 usable=1', 'provider_status=-16 status=-16 usable=0', 1)
        with self.assertRaises(ValueError): gate.observer(bad.replace('state=1', 'state=2'))


class Baseline(unittest.TestCase):
    def setUp(self):
        self.plan = json.loads((A/'registration.json').read_text())
        self.sec = gate.baseline.sections((A/'preflight/current-state.txt').read_text())

    def test_baseline(self):
        boot, _ = gate.identity(self.sec, self.plan, self.plan['baseline_notes_sha256'])
        self.assertEqual(boot, self.plan['before_boot_id'])

    def test_identity_and_safety_changes(self):
        for key, value in [('dcc', 'present'), ('failed', 'bad.service failed'), ('roles', '[source]\n[host]'),
                           ('network', 'lo'), ('identity', self.sec['identity'].replace('fea0613f', '00000000')),
                           ('cmdline', self.sec['cmdline']+' unsafe=1'), ('snapshot', self.sec['snapshot'].replace('fault=0', 'fault=1'))]:
            with self.subTest(key=key):
                sec = copy.deepcopy(self.sec); sec[key] = value
                with self.assertRaises(ValueError): gate.identity(sec, self.plan, self.plan['baseline_notes_sha256'])

    def test_unexpected_boot(self):
        with self.assertRaises(ValueError): gate.identity(self.sec, self.plan, self.plan['baseline_notes_sha256'], '1'*32)

    def test_original_kernel_diagnosis(self):
        raw = (A/'preflight/kernel-json.txt').read_text()
        # Known priority3 records are drawn from accepted254, not arbitrary current errors.
        path = gate.ROOT/'reference/boot-tests/test-254-debian-container-kernel/attempt-03/final-acceptance/kernel-journal-json.txt'
        known = {r['MESSAGE'] for r in map(json.loads, path.read_text().splitlines()) if int(r.get('PRIORITY', 7)) <= 3}
        out = gate.journal(raw, self.plan['before_boot_id'], known, float(self.sec['uptime'].split()[0]))
        self.assertEqual(out['unresolved_counts'], {'context': 10, 'syndrome': 10})
        self.assertFalse(out['stability_clean_claim'])
        for fault in ['Kernel panic - not syncing', 'BUG: soft lockup', 'rcu: INFO: detected stalls', 'CSD non-responsive']:
            row = json.loads(raw.splitlines()[0]); row.update(MESSAGE=fault, _SOURCE_BOOTTIME_TIMESTAMP='300000')
            with self.subTest(fault=fault):
                with self.assertRaises(ValueError): gate.journal(raw+'\n'+json.dumps(row), self.plan['before_boot_id'], known, 300)
        for changed in [raw.replace('00660021', '00670021'), raw.replace('fsynr=0x660021', 'fsynr=0x670021'),
                        raw+'\n'+next(x for x in raw.splitlines() if '00660021' in x), '']:
            with self.assertRaises(ValueError): gate.journal(changed, self.plan['before_boot_id'], known, 300)

    def test_runner_single_load_and_unload(self):
        src = (A/'run.py').read_text()
        self.assertEqual(src.count('insmod /tmp/test275-observer.ko'), 1)
        self.assertIn('attempted = True', src)
        self.assertIn('rmmod sm5440_fresh_observer', src)
        self.assertIn('finally:', src)
        self.assertNotIn('force', src)


if __name__ == '__main__':
    unittest.main()
