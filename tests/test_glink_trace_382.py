import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('glink_trace_382', ROOT / 'userspace/sensors/glink_trace_382.py')
g = importlib.util.module_from_spec(spec); spec.loader.exec_module(g)
BOOT = '11111111-1111-1111-1111-111111111111'


class GlinkTraceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory(); self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        def put(name, value):
            p = self.root / name; p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(value if isinstance(value, bytes) else value.encode())
        self.put = put
        put('proc/sys/kernel/random/boot_id', BOOT)
        put('etc/machine-id', g.MACHINE)
        put('proc/config.gz', gzip.compress(b'# CONFIG_HVC_DCC is not set\n'))
        put('sys/kernel/notes', b'notes')
        self.addCleanup(patch.stopall)
        patch.object(g, 'CONFIG', hashlib.sha256(b'# CONFIG_HVC_DCC is not set\n').hexdigest()).start()
        patch.object(g, 'NOTES', hashlib.sha256(b'notes').hexdigest()).start()
        put('proc/cmdline', 'console=tty0 ' + g.BOOT_ARGS)
        put('proc/uptime', '100 500')
        self.base = 'sys/kernel/tracing/instances/' + g.INSTANCE + '/'
        for name, value in [('current_tracer', 'nop'), ('buffer_size_kb', '131'), ('buffer_subbuf_size_kb', '4'),
                            ('tracing_on', '1'), ('trace_clock', '[local] global mono'),
                            ('set_event', '\n'.join('qcom_glink:' + n for n in g.EVENTS)),
                            ('trace', 'kernel-1 [004] 1.0: qcom_glink_cmd_open: rx remote: lpass channel: DIAG[1/2]\n')]:
            put(self.base + name, value)
        put('sys/kernel/tracing/events/header_page', 'field: char data; offset:16; size:4080; signed:0;')
        for cpu in range(8): put(self.base + 'per_cpu/cpu%d/buffer_size_kb' % cpu, '131')
        for name in g.EVENTS: put(self.base + 'events/qcom_glink/' + name + '/enable', '1')
        for cpu in range(8): put(self.base + 'per_cpu/cpu%d/stats' % cpu, 'entries: 1\noverrun: 0\ncommit overrun: 0\ndropped events: 0\n')
        put('sys/kernel/tracing/tracing_on', '1')

    def test_collect_owned_complete_trace_without_sensor_claim(self):
        result = g.Trace(self.root).collect(BOOT)
        self.assertTrue(result['complete']); self.assertTrue(result['trace_stopped'])
        self.assertFalse(result['SSC_publication_proved'])
        self.assertEqual(result['trace_clock'], '[local] global mono')
        self.assertEqual((self.root / self.base / 'tracing_on').read_text(), '0\n')
        self.assertEqual((self.root / 'sys/kernel/tracing/tracing_on').read_text(), '1')

    def test_wrong_expected_boot_or_new_boot_rejects_without_write(self):
        observer = g.Trace(self.root)
        with self.assertRaises(ValueError): observer.collect('22222222-2222-2222-2222-222222222222')
        self.put('proc/sys/kernel/random/boot_id', '22222222-2222-2222-2222-222222222222')
        with self.assertRaises(ValueError): observer.stop()
        self.assertEqual((self.root / self.base / 'tracing_on').read_text(), '1')

    def test_missing_or_duplicate_boot_argument_does_not_stop_foreign_trace(self):
        for cmd in ['console=tty0', g.BOOT_ARGS + ' ' + g.ARG]:
            self.put('proc/cmdline', cmd)
            with self.assertRaises(ValueError): g.Trace(self.root).collect(BOOT)
            self.assertEqual((self.root / self.base / 'tracing_on').read_text(), '1')

    def test_changed_config_notes_machine_rejected(self):
        for name, value in [('etc/machine-id', 'other'), ('sys/kernel/notes', 'other'),
                            ('proc/config.gz', gzip.compress(b'CONFIG_HVC_DCC=y\n'))]:
            p = self.root / name; saved = p.read_bytes(); self.put(name, value)
            with self.assertRaises(ValueError): g.Trace(self.root).collect(BOOT)
            p.write_bytes(saved)

    def test_extra_event_buffer_or_tracer_drift_rejected(self):
        for name, value in [('set_event', 'qcom_glink:qcom_glink_cmd_tx_data'),
                            ('buffer_size_kb', '1024'), ('current_tracer', 'function_graph'),
                            ('events/qcom_glink/' + g.EVENTS[0] + '/enable', '0')]:
            p = self.root / self.base / name; saved = p.read_text(); p.write_text(value)
            with self.assertRaises(ValueError): g.Trace(self.root).collect(BOOT)
            p.write_text(saved)

    def test_lost_records_preserve_raw_evidence_but_cannot_pass(self):
        self.put(self.base + 'per_cpu/cpu0/stats', 'overrun: 4\ncommit overrun: 0\ndropped events: 0\n')
        result = g.Trace(self.root).collect(BOOT)
        self.assertFalse(result['complete']); self.assertTrue(result['trace'])
        self.assertIn('overrun: 4', result['raw_per_cpu_stats']['cpu0'])

    def test_missing_stats_no_adsp_or_oversize_cannot_pass(self):
        (self.root / self.base / 'per_cpu/cpu0/stats').unlink()
        result = g.Trace(self.root).collect(BOOT); self.assertFalse(result['complete'])
        self.put(self.base + 'trace', '# no ADSP event\n')
        result = g.Trace(self.root).collect(BOOT); self.assertFalse(result['complete'])
        self.put(self.base + 'trace', 'x' * (g.MAX_BYTES // 2 + 100))
        result = g.Trace(self.root).collect(BOOT); self.assertFalse(result['complete'])
        self.assertEqual(result['trace_bytes'], g.MAX_BYTES // 2)

    def test_invalid_or_missing_overrun_fields_fail(self):
        for raw in ['', 'overrun: -1\n', 'overrun: x\n',
                    'overrun: 0\ncommit overrun: 0\ndropped events: 1\n']:
            with self.assertRaises(ValueError): g.parse_stats(raw)

    def test_deadline_stops_owned_instance_without_wait(self):
        self.put('proc/uptime', '301 500')
        with patch.object(g.time, 'sleep', side_effect=AssertionError('should not sleep')):
            result = g.Trace(self.root).watch()
        self.assertEqual(result['reason'], 'boot-time trace deadline')

    def test_already_stopped_watch_does_not_restart(self):
        self.put(self.base + 'tracing_on', '0')
        self.assertEqual(g.Trace(self.root).watch()['reason'], 'host stopped owned trace')

    def test_rpmsg_inventory_keeps_endpoint_ancestry_driver_and_address(self):
        self.put('sys/bus/rpmsg/devices/channel/name', 'DIAG')
        self.put('sys/bus/rpmsg/devices/channel/src', '1')
        result = g.Trace(self.root).inventory()
        self.assertEqual(result[0]['name'], 'DIAG'); self.assertEqual(result[0]['src'], '1')
        self.assertIsNone(result[0]['driver'])

    def test_exact_page_quantization_not_a_loose_capacity_range(self):
        state = g.Trace(self.root).describe()
        geometry = g.validate_geometry(state)
        self.assertEqual(geometry['requested_bytes'], 131072)
        self.assertEqual(geometry['actual_payload_bytes_per_cpu'], 134640)
        self.assertEqual(geometry['reported_kb'], 131)
        for bad in ('128', '130', '132', '1024', '131 (expanded: 128)', 'X'):
            self.put(self.base+'buffer_size_kb', bad)
            with self.assertRaisesRegex(ValueError, 'geometry'): g.Trace(self.root).collect(BOOT)
            self.assertEqual((self.root/self.base/'tracing_on').read_text(), '1')

    def test_wrong_page_header_or_per_cpu_capacity_refused(self):
        observer = g.Trace(self.root); state = observer.describe()
        for key, value in [('header_page', 'field: char data; offset:32; size:4064; signed:0;'),
                           ('buffer_subbuf_size_kb', '8'),
                           ('per_cpu_buffer_size_kb', {'cpu0': '131'})]:
            with self.assertRaises(ValueError): g.validate_geometry(state | {key:value})
        self.put(self.base+'per_cpu/cpu7/buffer_size_kb', '132')
        with self.assertRaises(ValueError): observer.collect(BOOT)

    def test_pre_admission_state_keeps_wrong_value_and_never_writes(self):
        self.put(self.base+'buffer_size_kb', '128')
        state = g.Trace(self.root).describe(); self.assertEqual(state['buffer_size_kb'], '128')
        self.assertEqual((self.root/self.base/'tracing_on').read_text(), '1')

    def test_clock_change_and_instance_symlink_refused(self):
        self.put(self.base+'trace_clock', 'local [global] mono')
        with self.assertRaisesRegex(ValueError, 'clock'): g.Trace(self.root).collect(BOOT)
        import shutil
        shutil.rmtree(self.root/self.base)
        (self.root/self.base).symlink_to(self.root/'sys/kernel/tracing')
        state=g.Trace(self.root).describe();self.assertTrue(state['instance_symlink'])
        self.assertEqual(state['current_tracer'], 'SYMLINK_REFUSED')
        with self.assertRaises(ValueError): g.Trace(self.root).collect(BOOT)


if __name__ == '__main__': unittest.main()
