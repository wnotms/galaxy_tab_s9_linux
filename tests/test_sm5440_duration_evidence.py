"""Duration identity and retained native safety proofs; no hardware access."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
import test_sm5440_bounded_direct as fixture
import test_sm5440_refresh_reserve_deployment as legacy

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('duration_evidence',ROOT/'scripts/sm5440_bounded_evidence.py')
e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)


def long_journal(window_ms=300000):
    row=fixture.row
    deadline=window_ms+900
    rows=[row('Linux boot',0),
          row('one-shot parked settled: samples=3 waited=120ms raw_ibus=0 pump_OFF=1',900000),
          row('direct charge started: PPS 8940 mV/1800 mA, ibus limit 1700 mA',1000000),
          row(f'one-shot pump started: target=8940mV/1800mA deadline={deadline}ms max_ms={window_ms} no_restart=1',1000100)]
    for n in range(window_ms//5000):
        t=5000000+n*4900000
        rows.extend([row('one-shot refresh parked: pump_OFF=1',t),
                     row('one-shot parked settled: samples=3 waited=120ms raw_ibus=0 pump_OFF=1',t+120000),
                     row(f'one-shot refresh resumed: target=8940mV/1800mA deadline={deadline}ms',t+150000)])
    rows.extend([row(f'one-shot refresh deferred: remaining=1000ms deadline={deadline}ms pump_unchanged=1',window_ms*1000-100000),
                 row('fixed return verified: source=9 lease=1 vbus=9267000uV samples=3 range=9267..9267mV settled=100ms raw_ibus=0 pump_off=1',window_ms*1000+1010000),
                 row('one-shot pump complete: lease=0 fixed_return=1 positive_samples=2400 no_restart=1',window_ms*1000+1011000)])
    return rows


class DurationEvidenceTests(unittest.TestCase):
    def proof(self,rows,ms=300000):
        return e.native_proof(rows,fixture.BOOT,expected_window_ms=ms,required=True)

    def test_short_parser_compatibility_and_actual_test345_replay(self):
        rows=legacy.journal()
        expected=legacy.g.native_proof(rows,fixture.BOOT,required=True)
        got=self.proof(rows,30000);self.assertEqual(got.pop('window_ms'),30000)
        self.assertEqual(got,expected)
        r=ROOT/'reference/boot-tests/test-345-final-refresh-reserve'
        rows=[json.loads(x) for x in (r/'physical-collection/kernel-json.txt').read_text().splitlines()]
        expected=json.loads((r/'physical-collection/native-proof.json').read_text())
        got=e.native_proof(rows,rows[0]['_BOOT_ID'],expected_window_ms=30000,required=True)
        self.assertEqual(got.pop('window_ms'),30000);self.assertEqual(got,expected)

    def test_full_long_history_binds_declared_duration_and_keeps_proofs(self):
        result=self.proof(long_journal())
        self.assertEqual((result['window_ms'],result['refreshes'],result['parked_zero_proofs'],result['refresh_deferrals']),(300000,60,61,1))
        self.assertEqual((result['hardware_input_ma'],result['target_ma']),(1700,1800))

    def test_wrong_missing_unknown_or_untyped_duration_cannot_pass(self):
        for rows,ms in ((long_journal(),30000),(legacy.journal(),300000)):
            with self.subTest(ms=ms),self.assertRaises(ValueError):self.proof(rows,ms)
        for ms in (0,30001,60000,300001,True,300000.0,'300000',None):
            with self.subTest(ms=ms),self.assertRaises(ValueError):self.proof(long_journal(),ms)
        with self.assertRaises(TypeError):e.native_proof(long_journal(),fixture.BOOT)

    def test_bad_start_duration_deadline_and_repeated_start_rejected(self):
        for a,b in (('max_ms=300000','max_ms=30000'),('deadline=300900','deadline=30900'),
                    ('1800mA','2000mA'),('no_restart=1','no_restart=0')):
            rows=long_journal();rows[3]['MESSAGE']=rows[3]['MESSAGE'].replace(a,b)
            with self.subTest(a=a),self.assertRaises(ValueError):self.proof(rows)
        rows=long_journal();rows.insert(4,copy.deepcopy(rows[3]))
        with self.assertRaises(ValueError):self.proof(rows)

    def test_long_run_fault_and_partial_evidence_never_complete(self):
        for msg in ('one-shot pump stopped: primary=-5 cleanup=0 lease=0 no_restart=1',
                    'one-shot parked settle failed: zero_samples=0 waited=1470ms pump_OFF=1',
                    'Kernel panic','soft lockup','rcu: detected stalls','CSD non-responsive'):
            rows=long_journal();rows.insert(70,fixture.row(msg,110000000))
            with self.subTest(msg=msg),self.assertRaises(ValueError):self.proof(rows)
        for rows in ([],long_journal()[:-1],long_journal()[4:]):
            with self.assertRaises(ValueError):self.proof(rows)

    def test_park_bounds_fixed_return_and_cleanup_deadline_unchanged(self):
        for index,change in ((5,{'MESSAGE':'one-shot parked settled: samples=2 waited=120ms raw_ibus=0 pump_OFF=1'}),
                             (6,{'_SOURCE_MONOTONIC_TIMESTAMP':'7000001'}),
                             (-2,{'MESSAGE':'fixed return verified: source=9 lease=1 vbus=9600000uV samples=3 range=9600..9600mV settled=100ms raw_ibus=0 pump_off=1'}),
                             (-1,{'_SOURCE_MONOTONIC_TIMESTAMP':'303900001'})):
            rows=long_journal();rows[index].update(change)
            with self.subTest(index=index),self.assertRaises(ValueError):self.proof(rows)

    def test_refreshed_deadline_and_deferral_after_which_rearm_is_rejected(self):
        rows=long_journal();rows[6]['MESSAGE']=rows[6]['MESSAGE'].replace('300900','301900')
        with self.assertRaises(ValueError):self.proof(rows)
        rows=long_journal();rows.insert(-2,fixture.row('one-shot refresh parked: pump_OFF=1',300000000))
        with self.assertRaises(ValueError):self.proof(rows)

    def test_unexplained_boot_and_historical_test344_stop_remain_failures(self):
        rows=long_journal();rows[60]['_BOOT_ID']='b'*32
        with self.assertRaises(ValueError):self.proof(rows)
        p=ROOT/'reference/boot-tests/test-344-parked-current-settle/physical-collection/kernel-json.txt'
        rows=[json.loads(x) for x in p.read_text().splitlines()]
        with self.assertRaisesRegex(ValueError,'first native/kernel fault'):
            e.native_proof(rows,rows[0]['_BOOT_ID'],expected_window_ms=30000,required=True)

    def test_twenty_minute_history_requires_registered_exact_duration(self):
        rows=long_journal(1200000)
        result=self.proof(rows,1200000)
        self.assertEqual((result['window_ms'],result['refreshes'],result['parked_zero_proofs']),
                         (1200000,240,241))
        for duration in (30000,300000,1199999,1200001):
            with self.subTest(duration=duration),self.assertRaises(ValueError):
                self.proof(rows,duration)
        for short in (legacy.journal(),long_journal()):
            with self.assertRaises(ValueError):self.proof(short,1200000)

    def test_twenty_minute_late_fault_missing_park_and_extended_deadline_rejected(self):
        for message in ('one-shot pump stopped: primary=-5 cleanup=0 lease=0 no_restart=1',
                        'Kernel panic','CSD non-responsive','I2C timeout'):
            rows=long_journal(1200000)
            rows.insert(-2,fixture.row(message,1199901000))
            with self.subTest(message=message),self.assertRaises(ValueError):
                self.proof(rows,1200000)
        rows=long_journal(1200000);rows.pop(-6)
        with self.assertRaises(ValueError):self.proof(rows,1200000)
        rows=long_journal(1200000)
        rows[6]['MESSAGE']=rows[6]['MESSAGE'].replace('1200900','1201900')
        with self.assertRaises(ValueError):self.proof(rows,1200000)

    def test_actual_test347_pass_preserved_and_not_twenty_minute_acceptance(self):
        r=ROOT/'reference/boot-tests/test-347-confirmed-c1-five-minute'
        rows=[json.loads(x) for x in (r/'physical-collection/kernel-json.txt').read_text().splitlines()]
        expected=json.loads((r/'physical-summary.json').read_text())['native']
        self.assertEqual(e.native_proof(rows,rows[0]['_BOOT_ID'],expected_window_ms=300000,required=True),expected)
        with self.assertRaises(ValueError):
            e.native_proof(rows,rows[0]['_BOOT_ID'],expected_window_ms=1200000,required=True)
