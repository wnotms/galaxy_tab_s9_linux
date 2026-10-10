import copy
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('ssc_provider_trace', ROOT / 'userspace/sensors/smp2p_trace.py')
g = importlib.util.module_from_spec(spec)
spec.loader.exec_module(g)
REAL = ROOT / 'reference/boot-tests/test-398-readdir-initialization/runtime-discovery/glink-complete.json'
CAPABILITY = ROOT / 'reference/desktop-bringup/ssc-smp2p-initialization/trace-capability.stdout'


def recalculate(d):
    payload = d['trace'].encode()
    d['trace_bytes'] = len(payload)
    d['trace_sha256'] = hashlib.sha256(payload).hexdigest()
    return d


def appended(*events):
    d = json.loads(REAL.read_text())
    count = len(events)
    # Explicit host-only extension of actual398, never a rewrite of raw evidence.
    d['trace'] = d['trace'].replace('17/17', '%d/%d' % (17 + count, 17 + count))
    for i, event in enumerate(events):
        d['trace'] += 'host-fixture-1 [000] ..... 0.%06d: %s\n' % (700000 + i, event)
    raw = d['raw_per_cpu_stats']['cpu0'].replace('entries: 16\n', 'entries: %d\n' % (16 + count))
    d['raw_per_cpu_stats']['cpu0'] = raw
    d['per_cpu_stats']['cpu0'] = g.geometry.parse_stats(raw)
    return recalculate(d)


OPEN = 'smp2p_negotiate: smp2p-adsp: state=open out_features=SMP2P_FEATURE_SSR_ACK'


class ProviderEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.d = appended(OPEN)
        self.boot = self.d['boot_id']

    def test_actual398_complete_without_provider_is_absence_not_failure(self):
        actual = json.loads(REAL.read_text())
        result = g.analyze(actual, actual['boot_id'])
        self.assertEqual(result['record_count'], 17)
        self.assertTrue(result['complete'])
        self.assertEqual(result['observation'], 'NEGOTIATION_NOT_OBSERVED')
        self.assertFalse(result['absent_event_proves_negotiation_failure'])
        self.assertFalse(result['SSC_publication_proved'])
        self.assertFalse(result['unconfigured_remote_entries_inventoried'])

    def test_all_native_event_types_and_original_timestamps(self):
        d = appended(OPEN, 'smp2p_notify_in: smp2p-adsp: slave-kernel: status:0x2 val:0x2',
                     'smp2p_update_bits: smp2p-adsp: master-kernel: orig:0x1 new:0x0',
                     'smp2p_ssr_ack: smp2p-adsp: SSR detected')
        result = g.analyze(d, self.boot)
        self.assertTrue(result['adsp_negotiation_observed'])
        self.assertEqual(result['record_count'], 21)
        self.assertEqual(result['negotiation_timestamps'], ['0.700000'])
        self.assertEqual(result['ssr_ack_count'], 1)
        self.assertEqual(result['adsp_events'][1]['value'], 2)
        self.assertEqual(result['adsp_events'][2]['original'], 1)
        self.assertFalse(result['SSC_publication_proved'])

    def test_other_processors_are_preserved_but_cannot_prove_adsp_open(self):
        d = appended(OPEN.replace('smp2p-adsp', 'smp2p-cdsp'))
        result = g.analyze(d, self.boot)
        self.assertEqual(result['native_smp2p_devices'], ['smp2p-cdsp'])
        self.assertFalse(result['adsp_negotiation_observed'])

    def test_empty_zero_feature_print_is_actual_kernel_semantics(self):
        d = appended('smp2p_negotiate: smp2p-adsp: state=open out_features=')
        self.assertEqual(g.analyze(d, self.boot)['adsp_events'][0]['features'], 0)

    def test_unknown_or_malformed_native_formats_are_not_silently_dropped(self):
        for event in ['smp2p_negotiate: smp2p-adsp: state=closed out_features=',
                      'smp2p_negotiate: smp2p-adsp: state=open out_features=0x2',
                      'smp2p_notify_in: smp2p-adsp: slave-kernel: val:0x2',
                      'smp2p_ssr_ack: smp2p-adsp: SSR guessed',
                      'unregistered: smp2p-adsp: open']:
            with self.subTest(event=event), self.assertRaises(ValueError):
                g.analyze(appended(event), self.boot)

    def test_integer_widths_are_enforced(self):
        for event in ['smp2p_notify_in: smp2p-adsp: slave-kernel: status:0x10000000000000000 val:0x1',
                      'smp2p_notify_in: smp2p-adsp: slave-kernel: status:0x1 val:0x100000000',
                      'smp2p_update_bits: smp2p-adsp: master-kernel: orig:0x100000000 new:0x0',
                      'qcom_glink_cmd_open: rx remote: lpass channel: test[65536/0]',
                      'qcom_glink_cmd_version: rx remote: lpass version: 4294967296 features: 0x1']:
            with self.subTest(event=event), self.assertRaises(ValueError):
                g.analyze(appended(event), self.boot)

    def test_stale_boot_and_incomplete_evidence_rejected(self):
        with self.assertRaises(ValueError):
            g.analyze(self.d, '22222222-2222-4222-8222-222222222222')
        for field in ['complete', 'trace_stopped']:
            with self.assertRaises(ValueError):
                g.analyze(self.d | {field: False}, self.boot)

    def test_raw_hash_and_length_mismatch_rejected(self):
        for field, value in [('trace_bytes', 1), ('trace_sha256', '0' * 64)]:
            with self.assertRaises(ValueError):
                g.analyze(self.d | {field: value}, self.boot)

    def test_actual_raw_loss_not_hidden_by_derived_clean_stats(self):
        for key in ['overrun', 'commit overrun', 'dropped events']:
            d = copy.deepcopy(self.d)
            d['raw_per_cpu_stats']['cpu1'] = d['raw_per_cpu_stats']['cpu1'].replace(key + ': 0', key + ': 1')
            with self.assertRaises(ValueError):
                g.analyze(d, self.boot)

    def test_missing_cpu_or_changed_derived_stats_rejected(self):
        for field in ['per_cpu_stats', 'raw_per_cpu_stats']:
            d = copy.deepcopy(self.d)
            del d[field]['cpu7']
            with self.assertRaises(ValueError):
                g.analyze(d, self.boot)
        d = copy.deepcopy(self.d)
        d['per_cpu_stats']['cpu0']['entries'] = '1'
        with self.assertRaises(ValueError):
            g.analyze(d, self.boot)

    def test_consumed_trace_rejected_even_with_consistent_stats(self):
        d = copy.deepcopy(self.d)
        raw = d['raw_per_cpu_stats']['cpu0'].replace('read events: 0', 'read events: 1')
        d['raw_per_cpu_stats']['cpu0'] = raw
        d['per_cpu_stats']['cpu0'] = g.geometry.parse_stats(raw)
        with self.assertRaises(ValueError):
            g.analyze(d, self.boot)

    def test_headers_missing_duplicate_or_wrong_count_rejected(self):
        for raw in [self.d['trace'].replace('18/18', '17/18'),
                    self.d['trace'].replace('# entries-in-buffer/entries-written: 18/18   #P:8', ''),
                    self.d['trace'] + '# entries-in-buffer/entries-written: 18/18   #P:8\n']:
            with self.assertRaises(ValueError):
                g.analyze(recalculate(self.d | {'trace': raw}), self.boot)

    def test_unknown_lines_cannot_be_hidden_behind_valid_counts(self):
        with self.assertRaises(ValueError):
            g.analyze(recalculate(self.d | {'trace': self.d['trace'] + 'TRUNCATED EVENT\n'}), self.boot)

    def test_per_cpu_counts_are_checked_not_just_total(self):
        d = recalculate(self.d | {'trace': self.d['trace'].replace('host-fixture-1 [000]', 'host-fixture-1 [001]')})
        with self.assertRaises(ValueError):
            g.analyze(d, self.boot)

    def test_future_timestamp_and_unknown_cpu_rejected(self):
        for raw in [self.d['trace'].replace('0.700000', '10000.000000'),
                    self.d['trace'].replace('host-fixture-1 [000]', 'host-fixture-1 [008]')]:
            with self.assertRaises(ValueError):
                g.analyze(recalculate(self.d | {'trace': raw}), self.boot)

    def test_local_clock_order_checked_only_within_cpu(self):
        d = recalculate(self.d | {'trace': self.d['trace'].replace('0.700000', '0.001000')})
        with self.assertRaisesRegex(ValueError, 'timestamp reversal'):
            g.analyze(d, self.boot)
        # CPU2 is at0.669683; CPU0's first row may have a smaller timestamp.
        d = recalculate(self.d | {'trace': self.d['trace'].replace('0.669798', '0.669680')})
        self.assertTrue(g.analyze(d, self.boot)['complete'])


class ProviderCollectorTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.d = appended(OPEN)
        self.boot = self.d['boot_id']
        self.base = 'sys/kernel/tracing/instances/' + g.INSTANCE + '/'
        self.config = b'# CONFIG_HVC_DCC is not set\n'
        self.addCleanup(patch.stopall)
        patch.object(g.geometry, 'CONFIG', hashlib.sha256(self.config).hexdigest()).start()
        patch.object(g.geometry, 'NOTES', hashlib.sha256(b'notes').hexdigest()).start()
        for name, value in [('proc/sys/kernel/random/boot_id', self.boot),
                            ('etc/machine-id', g.geometry.MACHINE),
                            ('proc/config.gz', gzip.compress(self.config)),
                            ('sys/kernel/notes', b'notes'), ('proc/cmdline', 'console=tty0 ' + g.BOOT_ARGS),
                            ('proc/uptime', '100 500'), ('sys/kernel/tracing/tracing_on', '1'),
                            ('sys/kernel/tracing/events/header_page', 'field: char data; offset:16; size:4080; signed:0;')]:
            self.put(name, value)
        for name, value in [('current_tracer', 'nop'), ('trace_clock', '[local] global mono'),
                            ('buffer_size_kb', '131'), ('buffer_subbuf_size_kb', '4'),
                            ('set_event', '\n'.join(g.EVENTS)), ('tracing_on', '1'), ('trace', self.d['trace'])]:
            self.put(self.base + name, value)
        formats = dict(re.findall(r'EVENT=(\w+)\n(.*?)ENABLE=', CAPABILITY.read_text(), re.S))
        for event in g.EVENTS:
            group, name = event.split(':')
            self.put(self.base + 'events/' + group + '/' + name + '/enable', '1')
            self.put(self.base + 'events/' + group + '/' + name + '/filter', 'none')
            if group == 'qcom_smp2p':
                self.put(self.base + 'events/' + group + '/' + name + '/format', formats[name])
        for cpu, raw in self.d['raw_per_cpu_stats'].items():
            self.put(self.base + 'per_cpu/' + cpu + '/stats', raw)
            self.put(self.base + 'per_cpu/' + cpu + '/buffer_size_kb', '131')

    def put(self, name, value):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(value if isinstance(value, bytes) else value.encode())

    def snapshot(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob('*') if p.is_file()}

    def test_actual_collector_changes_only_owned_tracing_on(self):
        before = self.snapshot()
        result = g.Trace(self.root).collect(self.boot)
        self.assertTrue(result['complete'])
        self.assertEqual(result['provider']['observation'], 'NEGOTIATION_OBSERVED')
        after = self.snapshot()
        self.assertEqual(set(before), set(after))
        self.assertEqual([name for name in before if before[name] != after[name]], [self.base + 'tracing_on'])
        self.assertEqual(after[self.base + 'tracing_on'], b'0\n')
        self.assertEqual(result['trace'], self.d['trace'])
        self.assertEqual(g.Trace(self.root).describe()['instance'], g.INSTANCE)

    def test_unfiltered_exact_event_set_and_formats_required_before_write(self):
        name = self.base + 'events/qcom_smp2p/smp2p_negotiate/'
        for path, value in [(name + 'filter', 'dev_name == "smp2p-adsp"'), (name + 'enable', '0'),
                            (name + 'format', 'name: smp2p_negotiate\nID: 1\nwrong-format\n'),
                            (self.base + 'set_event', '\n'.join(g.EVENTS[:-1])),
                            (self.base + 'set_event', '\n'.join(g.EVENTS) + '\n' + g.EVENTS[0])]:
            p = self.root / path
            saved = p.read_bytes()
            self.put(path, value)
            before = self.snapshot()
            with self.assertRaises(ValueError):
                g.Trace(self.root).collect(self.boot)
            self.assertEqual(before, self.snapshot())
            p.write_bytes(saved)

    def test_event_id_change_allowed_but_field_width_change_refused(self):
        p = self.root / (self.base + 'events/qcom_smp2p/smp2p_notify_in/format')
        raw = p.read_text()
        p.write_text(re.sub(r'^ID: \d+$', 'ID: 12345', raw, flags=re.M))
        self.assertTrue(g.Trace(self.root).collect(self.boot)['complete'])
        p.write_text(raw.replace('size:8;', 'size:4;'))
        with self.assertRaises(ValueError):
            g.Trace(self.root).admit()

    def test_stale_boot_and_other_trace_instance_refused_before_write(self):
        before = self.snapshot()
        with self.assertRaises(ValueError):
            g.Trace(self.root).collect('22222222-2222-4222-8222-222222222222')
        self.assertEqual(before, self.snapshot())
        self.put('proc/cmdline', g.BOOT_ARGS + ' trace_instance=another')
        before = self.snapshot()
        with self.assertRaises(ValueError):
            g.Trace(self.root).collect(self.boot)
        self.assertEqual(before, self.snapshot())

    def test_parser_failure_keeps_raw_and_stops_only_owned_trace(self):
        self.put(self.base + 'trace', self.d['trace'] + 'CORRUPT ROW\n')
        result = g.Trace(self.root).collect(self.boot)
        self.assertFalse(result['complete'])
        self.assertIn('CORRUPT ROW', result['trace'])
        self.assertIn('provider analysis', result['faults'][-1]['reason'])
        self.assertEqual((self.root / (self.base + 'tracing_on')).read_text(), '0\n')
        self.assertEqual((self.root / 'sys/kernel/tracing/tracing_on').read_text(), '1')

    def test_loss_keeps_raw_counters_and_does_not_claim_negotiation(self):
        self.put(self.base + 'per_cpu/cpu0/stats', self.d['raw_per_cpu_stats']['cpu0'].replace('overrun: 0', 'overrun: 2'))
        result = g.Trace(self.root).collect(self.boot)
        self.assertFalse(result['complete'])
        self.assertIn('overrun: 2', result['raw_per_cpu_stats']['cpu0'])
        self.assertNotIn('provider', result)

    def test_reused_deadline_stops_only_owned_trace(self):
        self.put('proc/uptime', '301 500')
        with patch.object(g.geometry.time, 'sleep', side_effect=AssertionError('no wait expected')):
            result = g.Trace(self.root).watch()
        self.assertEqual(result['reason'], 'boot-time trace deadline')
        self.assertEqual((self.root / 'sys/kernel/tracing/tracing_on').read_text(), '1')

    def test_actual_formats_require_one_id(self):
        for raw in ['name: x\n', 'ID: 1\nID: 2\n']:
            with self.assertRaises(ValueError):
                g.format_hash(raw)


if __name__ == '__main__':
    unittest.main()
