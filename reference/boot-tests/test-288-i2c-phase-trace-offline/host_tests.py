#!/usr/bin/env python3
"""Offline transaction/phase/ownership/first-refusal mocks. No device access."""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest

A = Path(__file__).resolve().parent
OLD = A.parent / 'test-279-fresh-trace-collector-offline'
sys.path[:0] = [str(A), str(OLD), str(A.parent / 'test-280-passive-fresh-trace')]
import analyse as frozen_analyse
import collector
import phase_analyse
import phase_collector
import phase_coordinator
import phase_decode


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


old = load('frozen279_fixtures', OLD / 'host_tests.py')
old280 = load('frozen280_fixtures', A.parent / 'test-280-passive-fresh-trace/host_tests.py')
MESSAGE_FORMAT = ('field:int adapter_nr; offset:8; size:4; signed:1;\n'
                  'field:__u16 msg_nr; offset:12; size:2; signed:0;\n'
                  'field:__u16 addr; offset:14; size:2; signed:0;\n'
                  'field:__u16 flags; offset:16; size:2; signed:0;\n'
                  'field:__u16 len; offset:18; size:2; signed:0;\n')
RESULT_FORMAT = ('field:int adapter_nr; offset:8; size:4; signed:1;\n'
                 'field:__u16 nr_msgs; offset:12; size:2; signed:0;\n'
                 'field:__s16 ret; offset:14; size:2; signed:1;\n')


class MockFS(old.MockFS):
    def mkdir(self, path):
        super().mkdir(path)
        for event in phase_collector.I2C_EVENTS:
            fmt = RESULT_FORMAT if event == 'i2c_result' else MESSAGE_FORMAT
            if event in ('i2c_write', 'i2c_reply'):
                fmt += 'field:__data_loc __u8[] buf; offset:20; size:4; signed:0;\n'
            self.values[path + '/events/i2c/' + event + '/format'] = fmt.encode()


def i2c_line(event, ns, payload, pid=60):
    return old.line(event, f'{ns // 10**9}.{ns % 10**9:09d}', pid=pid, payload=payload)


def transfer(kind, reg, data, start, result=None, pid=60):
    payload = lambda n, flags, values: f'i2c-0 #{n} a=063 f={flags:04x} l={len(values)}'
    wire = lambda values: ' [' + '-'.join(f'{v:02x}' for v in values) + ']'
    if kind == 'write':
        values = [reg] + data
        lines = [i2c_line('i2c_write', start, payload(0, 0, values) + wire(values), pid)]
        count = 1
    else:
        lines = [i2c_line('i2c_write', start, payload(0, 0, [reg]) + wire([reg]), pid),
                 i2c_line('i2c_read', start + 1000, payload(1, 1, data), pid)]
        count = 2
        if result is None or result == 2:
            lines.append(i2c_line('i2c_reply', start + 50000, payload(1, 1, data) + wire(data), pid))
    lines.append(i2c_line('i2c_result', start + 100000,
                         f'i2c-0 n={count} ret={count if result is None else result}', pid))
    return lines


def sequence():
    setup = [('read', 0x10, [1]), ('read', 0x00, [0]*4),
             ('read', 0x1c, [9]), ('write', 0x1c, [8]), ('read', 0x03, [0]),
             ('write', 0x1d, [0xdf]), ('read', 0x1c, [8]), ('write', 0x1c, [9])]
    rows = [dict(kind=k, reg=r, data=d, ns=1011001000 + i*200000) for i, (k, r, d) in enumerate(setup)]
    rows += [dict(kind='read', reg=3, data=[v], ns=n) for v, n in
             [(0, 1040000000), (0, 1068000000), (0, 1096000000), (1, 1123000000)]]
    tail = [(0x1e, [0x19, 0x78, 0x7b, 0x10, 0, 0, 0x67, 0x38, 5, 0x76, 0x78]),
            (0x08, [0, 0, 0x20, 0]), (0x10, [1]), (0x0d, [0xf2]),
            (0x13, [0xe7]), (0x14, [0x37]), (0x19, [0xfe])]
    rows += [dict(kind='read', reg=r, data=d, ns=1123200000 + i*200000) for i, (r, d) in enumerate(tail)]
    return rows


def raw_trace(session, operations=None, extra=()):
    lines = old.trace(session).splitlines(True)[1:]
    for operation in sequence() if operations is None else operations:
        lines += transfer(operation['kind'], operation['reg'], operation['data'],
                          operation['ns'], operation.get('result'), operation.get('pid', 60))
    lines.extend(extra)
    lines.sort(key=lambda line: int(phase_decode.LINE.fullmatch(line.rstrip('\n'))[3])*10**9 +
               int(phase_decode.LINE.fullmatch(line.rstrip('\n'))[4].ljust(9, '0')))
    return '# tracer: nop\n' + ''.join(lines)


def populate(fs, session, raw):
    fs.values[session.instance + '/trace'] = raw.encode()
    fs.values[session.instance + '/per_cpu/cpu0/stats'] = old.STAT.format(n=len(raw.splitlines())-1).encode()
    for kind, name in session.names.items():
        fs.hits[name] = len(re.findall(': ' + re.escape(name) + ':', raw))


def fixture(path, operations=None, extra=()):
    fs = MockFS(); session = phase_collector.Session(fs, path, old.TOKEN)
    session.setup(old.SYMS, old.BOOT); session.start()
    populate(fs, session, raw_trace(session, operations, extra))
    session.snapshot(old.BOOT); session.finish()
    return fs, session


class Parser(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'capture'

    def report(self, operations=None, extra=()):
        fixture(self.path, operations, extra)
        return phase_analyse.analyse(self.path)

    def seal(self, filename, text):
        (self.path / filename).write_text(text)
        p = self.path / 'manifest.json'; meta = json.loads(p.read_text())
        data = (self.path / filename).read_bytes()
        meta['files'][filename] = dict(bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        p.write_text(json.dumps(meta))

    def test_source_recipe_four_observed_polls_not_elapsed_guess(self):
        out = self.report(); self.assertEqual(out['verdict'], 'BOUNDED_TRACE_ATTRIBUTED', out)
        cycle = out['i2c_phases']['workers'][0]['phase']
        self.assertEqual(cycle['poll_count'], 4)
        self.assertEqual(cycle['poll_values'], [0, 0, 0, 1])
        self.assertEqual(cycle['adc_read']['data'], sequence()[12]['data'])
        self.assertGreater(cycle['between_transaction_wall_ns_sum'], cycle['transaction_wall_ns_sum'])
        self.assertIsNone(cycle['adc_duration_ns'])
        self.assertFalse(cycle['hardware_acceptance'] or out['hardware_acceptance'])
        self.assertEqual(out['request_timeout_branch'], 'UNKNOWN')

    def test_287_without_i2c_is_unknown_not_fabricated_phase_evidence(self):
        path = A.parent / 'test-287-passive-fresh-trace/observation/device-capture/observation/trace'
        self.assertEqual(frozen_analyse.analyse(path)['verdict'], 'BOUNDED_TRACE_ATTRIBUTED')
        self.assertEqual(phase_analyse.analyse(path)['verdict'], 'UNKNOWN')

    def test_background_other_pid_retained_unassigned(self):
        out = self.report(extra=transfer('read', 1, [0], 1005000000, pid=99))
        self.assertEqual(out['verdict'], 'BOUNDED_TRACE_ATTRIBUTED', out)
        self.assertEqual(out['i2c_phases']['unassigned_background_i2c_records'], 4)

    def test_each_missing_message_reply_result_stops(self):
        self.report()
        original = (self.path/'trace.txt').read_text()
        for event in phase_collector.I2C_EVENTS:
            with self.subTest(event=event):
                lines = original.splitlines(True)
                lines.pop(next(i for i, line in enumerate(lines) if ': '+event+':' in line))
                self.seal('trace.txt', ''.join(lines))
                self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_wrong_adapter_address_flags_or_buffer_never_admitted(self):
        self.report(); original = (self.path/'trace.txt').read_text()
        for before, after in [('i2c-0 #', 'i2c-1 #'), ('a=063', 'a=062'),
                              ('f=0001', 'f=0011'), ('[10]', '[10-11]'), ('[10]', '[1g]'),
                              ('n=2 ret=2', 'n=3 ret=2'), ('#1 a=', '#0 a=')]:
            with self.subTest(field=before):
                self.seal('trace.txt', original.replace(before, after, 1))
                self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_duplicate_reply_rejected(self):
        self.report(); raw = (self.path/'trace.txt').read_text(); lines = raw.splitlines(True)
        i = next(i for i, line in enumerate(lines) if ': i2c_reply:' in line); lines.insert(i, lines[i])
        self.seal('trace.txt', ''.join(lines))
        self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_i2c_negative_result_retained_no_retry_or_adc_grant(self):
        operations = sequence()[:10]; operations[-1]['result'] = -5
        out = self.report(operations); self.assertEqual(out['verdict'], 'BOUNDED_TRACE_ATTRIBUTED', out)
        phase = out['i2c_phases']['workers'][0]['phase']
        self.assertEqual(phase['verdict'], 'I2C_FAILURE_OBSERVED')
        self.assertEqual(phase['first_transfer_failure']['result']['ret'], -5)
        self.assertIsNone(phase['adc_duration_ns'])

    def test_short_i2c_transfer_failure_retained(self):
        operations = sequence()[:10]; operations[-1]['result'] = 1
        phase = self.report(operations)['i2c_phases']['workers'][0]['phase']
        self.assertEqual(phase['verdict'], 'I2C_FAILURE_OBSERVED')

    def test_register_activity_after_failure_unknown(self):
        operations = sequence(); operations[9]['result'] = -5
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_changed_channel_sequence_unknown(self):
        operations = sequence(); operations[5]['data'] = [0xff]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_changed_adc_write_or_rate_unknown(self):
        operations = sequence(); operations[7]['data'] = [0x0b]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_disable_write_can_be_skipped_when_adc_already_disabled(self):
        operations = sequence(); operations[2]['data'] = [8]; operations.pop(3)
        out = self.report(operations)
        self.assertEqual(out['verdict'], 'BOUNDED_TRACE_ATTRIBUTED', out)
        self.assertEqual(out['i2c_phases']['workers'][0]['phase']['poll_count'], 4)

    def test_no_new_enable_edge_unknown(self):
        operations = sequence(); operations[6]['data'] = [9]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_pump_on_before_or_after_unknown(self):
        operations = sequence(); operations[0]['data'] = [5]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_pump_on_after_adc_unknown(self):
        operations = sequence(); operations[14]['data'] = [5]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_extra_poll_after_ready_unknown(self):
        operations = sequence(); operations.insert(12, dict(kind='read', reg=3, data=[1], ns=1123150000))
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_changed_protection_unknown(self):
        operations = sequence(); operations[-1]['data'] = [0xff]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_missing_ready_unknown(self):
        operations = sequence(); operations[11]['data'] = [0]
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_extra_register_write_unknown(self):
        operations = sequence(); operations.append(dict(kind='write', reg=0x10, data=[5], ns=1125000000))
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_unrelated_pid_cannot_supply_missing_worker_read(self):
        operations = sequence(); operations[12]['pid'] = 99
        self.assertEqual(self.report(operations)['verdict'], 'UNKNOWN')

    def test_clock_reversal_and_truncation_unknown(self):
        self.report(); raw = (self.path/'trace.txt').read_text()
        for bad in [raw[:-1], raw.replace('1.123000000', '0.123000000', 1)]:
            with self.subTest(raw=bad[-10:]):
                self.seal('trace.txt', bad)
                self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_lost_events_probe_miss_and_bad_clock_unknown(self):
        self.report()
        for name, before, after in [('cpu0-after.stats', 'overrun: 0', 'overrun: 1'),
                                    ('profile-after.txt', '1 0', '1 1'),
                                    ('clock.txt', '[boot]', '[local]')]:
            with self.subTest(file=name):
                original = (self.path/name).read_text(); self.seal(name, original.replace(before, after, 1))
                self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')
                self.seal(name, original)

    def test_hash_mismatch_unknown(self):
        self.report(); (self.path/'trace.txt').write_text('changed\n')
        self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_full_trace_entry_count_not_just_probe_count_required(self):
        self.report(); name = 'cpu0-after.stats'; raw = (self.path/name).read_text()
        self.seal(name, re.sub(r'entries: \d+', 'entries: 7', raw))
        self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_probe_hit_without_record_unknown(self):
        self.report(); name = 'profile-after.txt'; raw = (self.path/name).read_text()
        self.seal(name, raw.replace('1 0', '2 0', 1))
        self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')

    def test_i2c_filters_formats_and_enabled_set_verified(self):
        self.report()
        for name, value in [('i2c_write.filter', 'adapter_nr == 1\n'),
                             ('i2c_result.format', RESULT_FORMAT.replace('signed:1;', 'signed:0;', 1)),
                             ('enabled-events-i2c.txt', 'i2c:i2c_write\n')]:
            with self.subTest(file=name):
                original = (self.path/name).read_text(); self.seal(name, value)
                self.assertEqual(phase_analyse.analyse(self.path)['verdict'], 'UNKNOWN')
                self.seal(name, original)


class Ownership(unittest.TestCase):
    def exercise(self, failure=None):
        with tempfile.TemporaryDirectory() as temp:
            fs = MockFS(); fs.fail = failure
            session = phase_collector.Session(fs, Path(temp)/'capture', old.TOKEN)
            error = None
            try:
                session.setup(old.SYMS, old.BOOT)
                session.start(); populate(fs, session, raw_trace(session)); session.snapshot(old.BOOT)
            except Exception as exc: error = str(exc)
            session.finish(error)
            return fs, session.meta

    def test_private_i2c_scope_cleanup_and_unrelated_probe_preserved(self):
        fs, meta = self.exercise()
        self.assertTrue(meta['collection_complete'])
        self.assertEqual(fs.definitions, ['p:unrelated/preserved some_function'])
        self.assertFalse(fs.instances or fs.enabled)
        self.assertFalse(meta['new_register_access'])
        for operation in fs.operations:
            if operation[0] == 'write':
                self.assertTrue(operation[1] == 'kprobe_events' or operation[1].startswith('instances/gts9t279_'))
                self.assertNotIn('trace_pipe', operation[1])

    def test_partial_extra_event_setup_cleans_all_owned_state(self):
        fs, meta = self.exercise(lambda path, value: path.endswith('/i2c_read/enable') and value == '1')
        self.assertFalse(meta['collection_complete'])
        self.assertFalse(fs.instances or fs.enabled)
        self.assertEqual(fs.definitions, ['p:unrelated/preserved some_function'])

    def test_snapshot_failure_keeps_raw_and_stops(self):
        fs, meta = self.exercise(lambda path, value: path.endswith('/i2c_read/enable') and value == '0')
        self.assertFalse(meta['collection_complete'])
        self.assertIn('trace.txt', meta['files'])
        self.assertFalse(fs.instances or fs.enabled)

    def test_all_extra_filters_bus_only_not_address_only(self):
        fs, _ = self.exercise()
        values = [op[2] for op in fs.operations if op[0] == 'write' and '/i2c/' in op[1] and op[1].endswith('/filter')]
        self.assertEqual(values, ['adapter_nr == 0'] * 4)

    def test_runtime_field_type_change_rejected(self):
        with self.assertRaises(ValueError):
            phase_collector.check_format('i2c_result', RESULT_FORMAT.replace('__s16 ret;', '__s16 other;'))


class Ops(old280.Ops):
    def load(self, timeout):
        super().load(timeout)
        instance = next(iter(self.fs.instances)); group = instance.rsplit('/', 1)[1]
        class NamedSession: pass
        session = NamedSession(); session.instance = instance
        session.names = {k: group + '_' + k for k in collector.PROBES}
        populate(self.fs, session, raw_trace(session))


class Coordination(unittest.TestCase):
    def exercise(self, error=None, setup_failure=False):
        with tempfile.TemporaryDirectory() as temp:
            fs = MockFS(); ops = Ops(fs, error)
            if setup_failure:
                fs.fail = lambda path, value: path.endswith('/i2c_reply/enable') and value == '1'
            result = phase_coordinator.run_once(fs, Path(temp)/'capture', ops, lambda: ops.now, ops.pause)
            return result, ops.calls, fs

    def test_one_refusal_binding_cleanup_before_unload_and_no_grant(self):
        out, calls, fs = self.exercise()
        self.assertEqual(out['verdict'], 'PASSIVE_REFUSAL_CAPTURED', out)
        self.assertTrue(out['binding']['observer_trace_bound'])
        self.assertEqual(calls.count(('load', 5)), 1)
        self.assertEqual(calls.count(('unload', 10)), 1)
        self.assertEqual(calls.count(('pause', .5)), 1)
        self.assertFalse(out['PPS'] or out['pump_ON'] or out['timing_acceptance'])
        self.assertEqual(out['trace_analysis']['i2c_phases']['workers'][0]['phase']['poll_count'], 4)
        self.assertFalse(fs.instances or fs.enabled)

    def test_preflight_failure_no_trace_or_load(self):
        out, calls, fs = self.exercise('preflight')
        self.assertEqual(out['verdict'], 'STOP'); self.assertFalse(fs.operations)
        self.assertNotIn(('load', 5), calls)

    def test_extra_trace_setup_failure_no_observer_load(self):
        out, calls, fs = self.exercise(setup_failure=True)
        self.assertEqual(out['verdict'], 'STOP'); self.assertNotIn(('load', 5), calls)
        self.assertFalse(fs.instances or fs.enabled)

    def test_load_cache_boot_deadline_interrupt_unload_failures_stop_without_retry(self):
        for error in ('load', 'cache', 'malformed', 'boot-live', 'deadline', 'interrupt', 'unload'):
            with self.subTest(error=error):
                out, calls, fs = self.exercise(error)
                self.assertEqual(out['verdict'], 'STOP')
                self.assertEqual(calls.count(('load', 5)), 1)
                self.assertEqual(calls.count(('unload', 10)), 1)
                self.assertFalse(fs.instances or fs.enabled)

    def test_frozen_coordinator_functions_and_worker_pairing_ast_preserved(self):
        for filename, previous, functions in [
                ('phase_coordinator.py', 'test-280-passive-fresh-trace/coordinator.py', ('bind', 'run_once')),
                ('phase_analyse.py', 'test-279-fresh-trace-collector-offline/analyse.py', ('pair',))]:
            before = ast.parse((A.parent/previous).read_text()); after = ast.parse((A/filename).read_text())
            for name in functions:
                a = next(n for n in before.body if isinstance(n, ast.FunctionDef) and n.name == name)
                b = next(n for n in after.body if isinstance(n, ast.FunctionDef) and n.name == name)
                self.assertEqual(ast.dump(a), ast.dump(b))


if __name__ == '__main__': unittest.main(verbosity=2)
