"""Pure timing evidence tests; no build, transport, request, probe or device."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parent))
import analyse as a


class Timing(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs=a.checked_inputs(a.ROOT,json.loads((a.A/'INPUTS.json').read_text()))
        cls.report=a.analyse(cls.inputs)
        cls.base='reference/boot-tests/test-277-revised-passive-observer/observation/'
        cls.frame=cls.inputs[cls.base+'sample-00.txt'].decode()
        cls.observer=cls.inputs[cls.base+'terminal-observer.txt'].decode()

    def test_actual_profile_and_quantization(self):
        p=self.report['profile']
        self.assertEqual([p[k] for k in ['hz','deadline_ms','poll_requested_ms','poll_timeout_ticks','poll_timeout_nominal_ms','maximum_polls']],[250,100,25,7,28,12])
        self.assertEqual(p['nominal_four_poll_timeout_sum_ms'],112)
        self.assertIsNone(p['actual_sleep_or_conversion_ms'])

    def test_jiffy_rounding_not_real_sleep_measurement(self):
        self.assertEqual(a.timeout_ticks(25,1000),25)
        self.assertEqual(a.timeout_ticks(25,250),7)
        self.assertEqual(a.timeout_ticks(100,250),25)
        for ms,hz in [(0,250),(25,0),(25,333)]:
            with self.assertRaises(ValueError): a.timeout_ticks(ms,hz)

    def test_observed_101_and_108_are_caller_elapsed_only(self):
        self.assertEqual([c['observer_elapsed_ms'] for c in self.report['cases']],[108,101])
        for c in self.report['cases']:
            self.assertEqual(c['timeout_branch'],'UNKNOWN')
            self.assertTrue(all(v is None for v in c['phase_durations_ms'].values()))
            self.assertFalse(c['hardware_ADC_fault_proven'])

    def test_cache_publication_delta_is_not_conversion(self):
        delta=self.report['cases'][1]['publication_deltas'][-1]
        self.assertEqual((delta['publication_delta_ticks'],delta['publication_delta_ms']),(92,368))
        self.assertTrue(delta['cache_advanced'])
        self.assertFalse(delta['proves_request_conversion_duration'])

    def test_no_absolute_boottime_from_jiffies(self):
        for c in self.report['cases']:
            for s in c['snapshots']:
                self.assertFalse(s['clock_anchor_available'])
                self.assertIsNone(s['absolute_publication_boottime_ms'])
                self.assertIsNone(s['actual_conversion_ms'])

    def test_no_false_measurement_or_charge_grant(self):
        for c in self.report['cases']:
            self.assertFalse(c['cleared_fields_are_measurements'])
            self.assertFalse(c['usable'] or c['charging_authorized'])
        self.assertFalse(self.report['device_commands_executed'] or self.report['kernel_or_hardware_changed'])
        self.assertEqual(self.report['active_Stage3'],'NOT READY')

    def test_original_stop_and_safe_unload_are_distinct(self):
        old,new=self.report['cases']
        self.assertFalse(old['unload_confirmed'])
        self.assertTrue(new['unload_confirmed'])
        self.assertNotEqual(old['original_verdict'],new['original_verdict'])

    def test_changed_input_hash_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'record';p.write_bytes(b'abc')
            manifest={'record':dict(bytes=3,sha256=hashlib.sha256(b'abc').hexdigest())}
            self.assertEqual(a.checked_inputs(Path(d),manifest)['record'],b'abc')
            p.write_bytes(b'xyz')
            with self.assertRaises(ValueError): a.checked_inputs(Path(d),manifest)

    def test_duplicate_markers_and_content_are_rejected(self):
        for raw in ['@@boot\na\n@@boot\nb','bad\n@@boot\na','@@\na']:
            with self.assertRaises(ValueError): a.packet(raw)

    def test_snapshot_age_disagreement_rejected(self):
        raw=a.packet(self.frame)['snapshot']
        with self.assertRaises(ValueError): a.snapshot(raw.replace('sample_age_ms=340','sample_age_ms=341'),250)

    def test_64bit_jiffies_crossing_32bit_boundary(self):
        raw=a.packet(self.frame)['snapshot']
        parsed=a.snapshot(raw,250)
        stamp=(1<<32)+10;capture=stamp+85
        raw=raw.replace('sample_stamp_jiffies='+str(parsed['publication_jiffies']),'sample_stamp_jiffies='+str(stamp)).replace('capture_jiffies='+str(parsed['capture_jiffies']),'capture_jiffies='+str(capture))
        self.assertEqual(a.snapshot(raw,250)['publication_age_ms'],340)
        with self.assertRaises(ValueError): a.snapshot(raw,250,32)

    def test_unsigned_wrap_and_backward_clock(self):
        raw=a.packet(self.frame)['snapshot'];s=a.snapshot(raw,250)
        def changed(stamp,capture,age):
            return raw.replace('sample_stamp_jiffies='+str(s['publication_jiffies']),'sample_stamp_jiffies='+str(stamp)).replace('capture_jiffies='+str(s['capture_jiffies']),'capture_jiffies='+str(capture)).replace('sample_age_ms=340','sample_age_ms='+str(age))
        self.assertEqual(a.snapshot(changed((1<<64)-10,10,80),250)['publication_age_ms'],80)
        with self.assertRaises(ValueError): a.snapshot(changed(100,99,0),250)

    def test_boot_or_identity_change_is_rejected(self):
        sec=a.packet(self.frame)
        for raw in [self.frame.replace(sec['boot'],'00000000-0000-0000-0000-000000000001'),self.frame.replace(sec['identity'].split()[0],'0'*64)]:
            with self.assertRaises(ValueError): a.case('changed',[('a',self.frame),('b',raw)],self.observer,250)

    def test_missing_and_faulted_snapshots_are_rejected(self):
        with self.assertRaises(ValueError): a.case('empty',[],self.observer,250)
        raw=a.packet(self.frame)['snapshot']
        for old,new in [('sample_valid=1','sample_valid=0'),('fault=0','fault=1'),('sample_int4_wait=0x01','sample_int4_wait=0x00'),('sample_ibus_ua=0','sample_ibus_ua=625')]:
            with self.assertRaises(ValueError): a.snapshot(raw.replace(old,new),250)
        with self.assertRaises(ValueError): a.snapshot('',250)

    def test_refused_provider_cannot_return_physical_raw_values(self):
        with self.assertRaises(ValueError): a.case('invalid',[('a',self.frame)],self.observer.replace('raw_vbus_uv=0','raw_vbus_uv=5000000'),250)

    def test_old_budget_or_queue_does_not_silently_enter_report(self):
        source=self.inputs['kernel/drivers/sm5440-direct.c'].decode()
        header=self.inputs['kernel/drivers/sm5440-hw.h'].decode();config=self.inputs['out/kernel-x710-272-passive/config'].decode()
        for src,hdr in [(source,header.replace('100U','150U')),(source.replace('msleep(25)','msleep(20)'),header),(source.replace('system_percpu_wq','system_wq'),header)]:
            with self.assertRaises(ValueError): a.profile(src,hdr,config)


if __name__=='__main__': unittest.main()
