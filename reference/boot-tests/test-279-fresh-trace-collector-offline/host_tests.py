#!/usr/bin/env python3
"""No device calls. TraceFS is replaced with an in-memory kernel interface."""
import hashlib
import json
from pathlib import Path
import re
import tempfile
from collections import Counter
import unittest

import analyse
import collector

BOOT = '11111111-2222-4333-8444-555555555555'
SYMS = 'ffffffc0810579a0 T sm5440_passive_request_fresh\nffffffc081058264 t sm5440_poll\n'
TOKEN = 'abcdef012345'
FMT = 'field:void * work; offset:8; size:8; signed:0;\nfield:void * function; offset:16; size:8; signed:0;\n'
STAT = 'entries: {n}\noverrun: 0\ncommit overrun: 0\ndropped events: 0\nread events: 0\n'


class MockFS:
    def __init__(self):
        self.values = {'kprobe_events': b'p:unrelated/preserved some_function\n',
                       'kprobe_profile': b'preserved 42 0\n'}
        self.operations = []
        self.definitions = ['p:unrelated/preserved some_function']
        self.instances = set()
        self.enabled = set()
        self.fail = None
        self.clock = b'[local] boot global\n'
        self.hits = Counter()

    def read(self, path):
        if path == 'kprobe_events':
            return ('\n'.join(self.definitions) + '\n').encode()
        if path == 'kprobe_profile':
            names = [line.split()[0].split('/')[-1] for line in self.definitions]
            return ''.join(f'{n} {self.hits[n]} 0\n' for n in names).encode()
        if path.endswith('/set_event'):
            return ('\n'.join(sorted(self.enabled)) + ('\n' if self.enabled else '')).encode()
        return self.values[path]

    def mkdir(self, path):
        if path in self.instances:
            raise FileExistsError(path)
        self.instances.add(path)
        self.operations.append(('mkdir', path))
        for name, value in {'tracing_on': b'1\n', 'trace_clock': self.clock,
                            'trace_options': b'context-info nooverwrite\n', 'trace': b'# tracer: nop\n'}.items():
            self.values[path + '/' + name] = value
        for cpu in ('cpu0', 'cpu1'):
            self.values[path + '/per_cpu/' + cpu + '/stats'] = STAT.format(n=0).encode()
        for event in collector.WORK:
            self.values[path + '/events/workqueue/' + event + '/format'] = FMT.encode()

    def rmdir(self, path):
        self.operations.append(('rmdir', path))
        self.instances.remove(path)
        self.values = {k: v for k, v in self.values.items() if not k.startswith(path + '/')}

    def list(self, path):
        return ['cpu0', 'cpu1']

    def write(self, path, value):
        self.operations.append(('write', path, value))
        if self.fail and self.fail(path, value):
            self.fail = None
            raise OSError('injected tracefs failure')
        if path == 'kprobe_events':
            if value.startswith('-:'):
                target = value[2:]
                self.definitions = [v for v in self.definitions if v.split()[0].split(':', 1)[1] != target]
            else:
                self.definitions.append(value)
                group, name = value.split()[0].split(':', 1)[1].split('/')
                inst = next(iter(self.instances))
                fmt = 'field:s32 ret; offset:24; size:4; signed:1;\n' if 'ret=' in value else 'field:unsigned long __probe_ip;\n'
                self.values[inst + '/events/' + group + '/' + name + '/format'] = fmt.encode()
            return
        if path.endswith('/enable'):
            group, name = path.split('/')[-3:-1]
            key = group + ':' + name
            if value == '1':
                self.enabled.add(key)
            else:
                self.enabled.discard(key)
        if path.endswith('/trace_clock'):
            self.values[path] = b'local [boot] global\n'
        else:
            self.values[path] = (value + '\n').encode()


def line(event, stamp, pid=40, cpu=0, payload='(symbol)'):
    return f'     task-{pid} [{cpu:03d}] .... {stamp}: {event}: {payload}\n'


def trace(session, older=False, ret=-110):
    n = session.names
    wq, ws, we = collector.WORK
    queue = 'work struct=000000001234abcd function=sm5440_poll workqueue=events req_cpu=0 cpu=0'
    start = 'work struct 000000001234abcd: function sm5440_poll'
    def worker_end(t, et):
        return line(n['poll_return'], t, pid=60) + line(we, et, pid=60, payload=start)
    result = ''
    if older:
        result += line(wq, '0.980000', payload=queue)
        result += line(ws, '0.990000', pid=60, payload=start)
        result += line(n['poll_enter'], '0.991000', pid=60)
    result += line(n['request_enter'], '1.000000')
    result += line(wq, '1.001000', payload=queue)
    if not older:
        result += line(ws, '1.010000', pid=60, payload=start)
        result += line(n['poll_enter'], '1.011000', pid=60)
    result += line(n['request_return'], '1.101000', payload=f'(symbol) ret={ret}')
    result += worker_end('1.130000', '1.131000')
    if older:
        result += line(ws, '1.132000', pid=60, payload=start)
        result += line(n['poll_enter'], '1.133000', pid=60)
        result += worker_end('1.180000', '1.181000')
    return '# tracer: nop\n' + result


def fixture(output, older=False, ret=-110):
    fs = MockFS()
    session = collector.Session(fs, output, TOKEN)
    session.setup(SYMS, BOOT)
    session.start()
    raw = trace(session, older, ret)
    fs.values[session.instance + '/trace'] = raw.encode()
    fs.values[session.instance + '/per_cpu/cpu0/stats'] = STAT.format(n=len(raw.splitlines()) - 1).encode()
    for kind, name in session.names.items():
        fs.hits[name] = len(re.findall(': ' + re.escape(name) + ':', raw))
    session.snapshot(BOOT)
    session.finish()
    return session, fs


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'capture'
        self.fs = MockFS()
        self.session = collector.Session(self.fs, self.out, TOKEN)

    def test_success_only_owned_writes_and_cleanup(self):
        _, fs = fixture(self.out)
        self.assertEqual(fs.definitions, ['p:unrelated/preserved some_function'])
        self.assertFalse(fs.instances)
        for op in fs.operations:
            if op[0] == 'write':
                self.assertTrue(op[1] == 'kprobe_events' or op[1].startswith('instances/gts9t279_'))
                self.assertNotEqual(op[2], '')
                self.assertNotIn('trace_pipe', op[1])
        commands = [op[2] for op in fs.operations if op[:2] == ('write', 'kprobe_events')]
        self.assertTrue(any('ret=$retval:s32' in c for c in commands))
        self.assertFalse(any('@' in c or '+0x' in c for c in commands))

    def test_missing_runtime_symbol_no_mutation(self):
        with self.assertRaises(ValueError):
            self.session.setup(SYMS.replace('sm5440_poll', 'other'), BOOT)
        self.session.finish('missing symbol')
        self.assertFalse(self.fs.operations)

    def test_hidden_runtime_address(self):
        with self.assertRaises(ValueError):
            collector.symbols(SYMS.replace('ffffffc081058264', '0000000000000000'))

    def test_duplicate_symbol(self):
        with self.assertRaises(ValueError):
            collector.symbols(SYMS + SYMS)

    def test_collision_does_not_adopt_instance(self):
        self.fs.instances.add(self.session.instance)
        with self.assertRaises(FileExistsError):
            self.session.setup(SYMS, BOOT)
        self.session.finish('collision')
        self.assertIn(self.session.instance, self.fs.instances)
        self.assertFalse(self.session.created)

    def test_probe_collision(self):
        self.fs.definitions.append('p:other/' + self.session.names['request_enter'] + ' sm5440_poll')
        with self.assertRaises(ValueError):
            self.session.setup(SYMS, BOOT)
        self.session.finish('collision')
        self.assertEqual(len(self.fs.definitions), 2)
        self.assertFalse(self.fs.operations)

    def test_missing_clock_cleanup(self):
        self.fs.clock = b'[local] global\n'
        with self.assertRaises(ValueError):
            self.session.setup(SYMS, BOOT)
        self.session.finish('clock')
        self.assertFalse(self.fs.instances)
        self.assertEqual(len(self.fs.definitions), 1)

    def test_partial_probe_setup_cleanup(self):
        self.fs.fail = lambda p, v: p == 'kprobe_events' and v.startswith('r16:')
        with self.assertRaises(OSError):
            self.session.setup(SYMS, BOOT)
        self.session.finish('setup')
        self.assertFalse(self.fs.instances)
        self.assertEqual(len(self.fs.definitions), 1)
        self.assertFalse(json.loads((self.out / 'manifest.json').read_text())['collection_complete'])

    def test_timeout_still_collects_then_cleans(self):
        self.session.setup(SYMS, BOOT)
        self.session.start()
        self.session.snapshot(BOOT)
        self.session.finish('deadline expired')
        self.assertFalse(self.fs.instances)
        self.assertTrue((self.out / 'trace.txt').exists())
        self.assertEqual(analyse.analyse(self.out)['verdict'], 'UNKNOWN')

    def test_cleanup_error_is_retained(self):
        self.session.setup(SYMS, BOOT)
        self.fs.fail = lambda p, v: p == 'kprobe_events' and v.startswith('-:')
        self.session.finish('collection failed')
        manifest = json.loads((self.out / 'manifest.json').read_text())
        self.assertTrue(manifest['cleanup_errors'])
        self.assertFalse(manifest['collection_complete'])

    def test_no_output_overwrite(self):
        self.out.mkdir()
        with self.assertRaises(FileExistsError):
            self.session.setup(SYMS, BOOT)
        self.assertFalse(self.fs.operations)

    def test_real_adapter_does_not_truncate_probe_commands(self):
        root = Path(self.tmp.name) / 'tracefs'
        root.mkdir()
        path = root / 'kprobe_events'
        path.write_text('p:unrelated/preserved some_function\n')
        adapter = collector.TraceFS(root)
        adapter.write('kprobe_events', 'p:owned/probe sm5440_poll')
        self.assertTrue(path.read_text().startswith('p:unrelated/preserved some_function\n'))
        self.assertTrue(path.read_text().endswith('p:owned/probe sm5440_poll\n'))

    def test_bad_token(self):
        with self.assertRaises(ValueError):
            collector.Session(self.fs, self.out, '../other')

    def test_orchestration_deadline_no_retry(self):
        ticks = iter((0, 36))
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT,
                                         elapsed=lambda: next(ticks)))
        self.assertFalse(self.fs.instances)
        self.assertEqual(len([op for op in self.fs.operations if op[0] == 'mkdir']), 1)
        self.assertIn('deadline expired', json.loads((self.out / 'manifest.json').read_text())['collection_error'])

    def test_orchestration_interruption_cleanup(self):
        def interrupted(seconds):
            raise InterruptedError('fixture SIGTERM')
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT,
                                         elapsed=lambda: 0, pause=interrupted))
        self.assertFalse(self.fs.instances)
        self.assertEqual(len(self.fs.definitions), 1)
        self.assertTrue((self.out / 'trace.txt').exists())

    def test_orchestration_terminal_marker(self):
        def terminal(seconds):
            (self.out / 'STOP').write_text('observer-terminal\n')
        self.assertTrue(collector.record(self.session, SYMS, lambda: BOOT,
                                        elapsed=lambda: 0, pause=terminal))
        self.assertFalse(self.fs.instances)
        # Complete collection of an EMPTY fixture still cannot grant attribution.
        self.assertEqual(analyse.analyse(self.out)['verdict'], 'UNKNOWN')

    def test_orchestration_bad_marker(self):
        def terminal(seconds):
            (self.out / 'STOP').write_text('retry\n')
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT,
                                         elapsed=lambda: 0, pause=terminal))
        self.assertFalse(self.fs.instances)

    def test_deadline_bounds(self):
        for duration in (0, -1, 36, float('nan')):
            with self.assertRaises(ValueError):
                collector.record(self.session, SYMS, lambda: BOOT, duration)
        self.assertFalse(self.fs.operations)

    def test_format_failure_before_start(self):
        original = self.fs.read
        def invalid(path):
            if path.endswith('request_return/format'):
                return b'field:u32 ret; signed:0;\n'
            return original(path)
        self.fs.read = invalid
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT))
        self.assertFalse(any(op[0] == 'write' and op[1].endswith('/tracing_on') and op[2] == '1' for op in self.fs.operations))
        self.assertFalse(self.fs.instances)

    def test_failed_filter_before_start(self):
        original = self.fs.read
        self.fs.read = lambda path: b'none\n' if path.endswith('/filter') else original(path)
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT))
        self.assertFalse(any(op[0] == 'write' and op[1].endswith('/tracing_on') and op[2] == '1' for op in self.fs.operations))

    def test_snapshot_failure_is_not_success(self):
        def terminal(seconds):
            (self.out / 'STOP').write_text('observer-terminal\n')
            self.fs.fail = lambda p, v: p.endswith('/tracing_on') and v == '0'
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT,
                                         elapsed=lambda: 0, pause=terminal))
        self.assertFalse(self.fs.instances)
        self.assertIn('snapshot', json.loads((self.out / 'manifest.json').read_text())['collection_error'])
        self.assertTrue((self.out / 'trace.txt').exists())

    def test_counter_read_failure_retains_raw_trace(self):
        original = self.fs.read
        def terminal(seconds):
            (self.out / 'STOP').write_text('observer-terminal\n')
            def unavailable(path):
                if '/per_cpu/' in path:
                    raise OSError('stats unavailable')
                return original(path)
            self.fs.read = unavailable
        self.assertFalse(collector.record(self.session, SYMS, lambda: BOOT,
                                         elapsed=lambda: 0, pause=terminal))
        self.assertTrue((self.out / 'trace.txt').exists())
        self.assertFalse(self.fs.instances)


class ParserTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name) / 'capture'
        self.session, self.fs = fixture(self.out)

    def replace(self, name, value):
        raw = value.encode()
        (self.out / name).write_bytes(raw)
        meta = json.loads((self.out / 'manifest.json').read_text())
        meta['files'][name] = {'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()}
        (self.out / 'manifest.json').write_text(json.dumps(meta))

    def metadata(self, key, value):
        meta = json.loads((self.out / 'manifest.json').read_text())
        meta[key] = value
        (self.out / 'manifest.json').write_text(json.dumps(meta))

    def unknown(self, expected):
        result = analyse.analyse(self.out)
        self.assertEqual(result['verdict'], 'UNKNOWN', result)
        self.assertIn(expected, result['reason'])
        self.assertIsNone(result['adc_duration_ns'])
        self.assertFalse(result['hardware_acceptance'])

    def test_paired_timeout_is_not_adc_or_hardware_acceptance(self):
        result = analyse.analyse(self.out)
        self.assertEqual(result['verdict'], 'BOUNDED_TRACE_ATTRIBUTED', result)
        self.assertEqual(result['requests'][0]['elapsed_ns'], 101000000)
        self.assertEqual(result['requests'][0]['return_code'], -110)
        self.assertEqual(result['requests'][0]['timeout_branch'], 'UNKNOWN')
        self.assertEqual(result['workers'][0]['queue_delay_ns'], 9000000)
        self.assertEqual(result['workers'][0]['worker_elapsed_ns'], 121000000)
        self.assertIsNone(result['adc_duration_ns'])
        self.assertFalse(result['hardware_acceptance'])
        self.assertIsNone(result['requests'][0]['causal_worker_assignment'])

    def test_old_inflight_worker_is_distinguished(self):
        other = Path(self.tmp.name) / 'old'
        fixture(other, older=True)
        result = analyse.analyse(other)
        self.assertEqual(result['verdict'], 'BOUNDED_TRACE_ATTRIBUTED', result)
        overlap = result['requests'][0]['overlapping_workers']
        self.assertEqual(len(overlap), 1)
        self.assertTrue(overlap[0]['already_running_at_entry'])
        self.assertFalse(overlap[0]['queued_during_request'])
        self.assertEqual(len(result['workers']), 2)
        self.assertIsNone(result['requests'][0]['causal_worker_assignment'])

    def test_zero_return_still_does_not_grant_acceptance(self):
        other = Path(self.tmp.name) / 'zero'
        fixture(other, ret=0)
        result = analyse.analyse(other)
        self.assertEqual(result['verdict'], 'BOUNDED_TRACE_ATTRIBUTED')
        self.assertFalse(result['uninstrumented_timing_acceptance'])
        self.assertFalse(result['hardware_acceptance'])

    def test_boot_changed(self):
        self.metadata('boot_after', '64710000-a2e0-4f34-8167-9632e38ac997')
        self.unknown('boot changed')

    def test_wrong_clock(self):
        self.replace('clock.txt', '[local] boot global\n')
        self.unknown('boot clock')

    def test_invalid_manifest_schema(self):
        self.metadata('probes', list(collector.PROBES))
        self.unknown('not an object')

    def test_consumed_events(self):
        self.replace('cpu0-after.stats', STAT.format(n=7).replace('read events: 0', 'read events: 1'))
        self.unknown('lost/consumed')

    def test_missing_cpu_stats(self):
        (self.out / 'cpu1-after.stats').unlink()
        self.unknown('cpu1-after.stats')

    def test_tamper(self):
        (self.out / 'trace.txt').write_bytes(b'bad\n')
        self.unknown('hash mismatch')

    def test_missing_trace(self):
        (self.out / 'trace.txt').unlink()
        self.unknown('trace.txt')

    def test_empty_trace(self):
        self.replace('trace.txt', '# tracer: nop\n')
        self.unknown('empty trace')

    def test_partial_last_line(self):
        self.replace('trace.txt', (self.out / 'trace.txt').read_text().rstrip('\n'))
        self.unknown('truncated trace')

    def test_clock_reversal(self):
        self.replace('trace.txt', (self.out / 'trace.txt').read_text().replace('1.101000', '0.901000'))
        self.unknown('clock reversal')

    def test_trace_loss(self):
        self.replace('cpu0-after.stats', STAT.format(n=7).replace('overrun: 0', 'overrun: 1', 1))
        self.unknown('lost/consumed')

    def test_count_truncation(self):
        self.replace('cpu0-after.stats', STAT.format(n=8))
        self.unknown('entry mismatch')

    def test_missed_return_probe(self):
        raw = (self.out / 'profile-after.txt').read_text()
        self.replace('profile-after.txt', raw.replace(self.session.names['request_return'] + ' 1 0', self.session.names['request_return'] + ' 1 1'))
        self.unknown('probe miss')

    def test_duplicate_profile(self):
        raw = (self.out / 'profile-after.txt').read_text()
        self.replace('profile-after.txt', raw + self.session.names['request_enter'] + ' 1 0\n')
        self.unknown('ambiguous')

    def test_probe_hits_not_in_trace(self):
        raw = (self.out / 'profile-after.txt').read_text()
        self.replace('profile-after.txt', raw.replace(self.session.names['request_enter'] + ' 1 0', self.session.names['request_enter'] + ' 2 0'))
        self.unknown('not fully represented')

    def test_wrong_filter(self):
        self.replace('workqueue_execute_start.filter', 'function == 0xffffffc080e80264\n')
        self.unknown('wrong work filter')

    def test_cleanup_failure(self):
        self.metadata('cleanup_errors', ['probe remains'])
        self.unknown('collection/cleanup')

    def test_bad_signed_return_format(self):
        self.replace('request_return.format', 'field:u32 ret; offset:24; size:4; signed:0;\n')
        self.unknown('wrong return format')

    def test_unknown_cpu(self):
        self.replace('trace.txt', (self.out / 'trace.txt').read_text().replace('[000]', '[009]'))
        self.unknown('unknown trace CPU')

    def test_nested_request_pairing(self):
        with self.assertRaisesRegex(ValueError, 'nested request'):
            analyse.pair([{'event': 'request_enter', 'pid': 1, 'ns': 0},
                          {'event': 'request_enter', 'pid': 1, 'ns': 1}])

    def test_unpaired_work_end(self):
        with self.assertRaisesRegex(ValueError, 'end without start'):
            analyse.pair([{'event': 'workqueue_execute_end', 'pid': 1, 'ns': 0, 'work': 'a'}])

    def test_pending_queue_is_incomplete(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            analyse.pair([{'event': 'workqueue_queue_work', 'pid': 1, 'ns': 0, 'work': 'a'}])

    def test_return_without_entry(self):
        with self.assertRaisesRegex(ValueError, 'return without entry'):
            analyse.pair([{'event': 'request_return', 'pid': 1, 'ns': 0, 'ret': -110}])

    def test_request_after_first_refusal_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'after first refusal'):
            analyse.pair([{'event': 'request_enter', 'pid': 1, 'ns': 0},
                          {'event': 'request_return', 'pid': 1, 'ns': 1, 'ret': -110},
                          {'event': 'request_enter', 'pid': 1, 'ns': 2},
                          {'event': 'request_return', 'pid': 1, 'ns': 3, 'ret': 0}])

    def test_missing_old_queue_is_not_zero_delay(self):
        rows = analyse.records((self.out / 'trace.txt').read_text(), self.session.names)
        rows = [r for r in rows if r['event'] != 'workqueue_queue_work']
        _, workers = analyse.pair(rows)
        self.assertIsNone(workers[0]['queue_delay_ns'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
