#!/usr/bin/env python3
"""Mock-only integration; no physical commands or tracefs access."""
import ast
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

A = Path(__file__).resolve().parent
OLD = A.parent / 'test-279-fresh-trace-collector-offline'
sys.path[:0] = [str(A), str(OLD)]
import coordinator
import collector
from observer_gate import HEADER, FIELDS
spec = importlib.util.spec_from_file_location('frozen279_host_fixtures', OLD / 'host_tests.py')
fixtures = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixtures)


def refusal():
    header = dict(HEADER, state='2', count='1')
    row = {k: 0 for k in FIELDS}
    row.update(row=1, request_ms=1000, return_ms=1101, provider_status=-110, status=-110)
    return ''.join(k+'='+v+'\n' for k,v in header.items()) + ' '.join(k+'='+str(row[k]) for k in ['row'] + sorted(FIELDS - {'row'}))+'\n'


class Ops:
    def __init__(self, fs, error=None):
        self.fs, self.error = fs, error
        self.calls = []
        self.module = False
        self.now = 0

    def verified_identity(self):
        self.calls.append('verified')
        return {'verdict': 'STOP_READONLY_PREFLIGHT_CMDLINE_IDENTITY' if self.error == 'preflight' else 'READY_FOR_REGISTERED_PASSIVE_TRACE',
                'paired_install_verified': True, 'normal_cmdline_verified': self.error != 'cmdline',
                'observer_sha256': 'old' if self.error == 'old-module' else coordinator.OBSERVER_SHA256,
                'observer_absent': self.error != 'preloaded', 'health_rescue_verified': True,
                'boot_id': fixtures.BOOT}

    def boot(self):
        self.calls.append('boot')
        if self.error == 'boot-before' or (self.error == 'boot-live' and self.module):
            return 'aaaaaaaa-2222-4333-8444-555555555555'
        return fixtures.BOOT

    def kallsyms(self):
        return fixtures.SYMS

    def load(self, timeout):
        self.calls.append(('load', timeout))
        self.module = True
        if self.error == 'load':
            raise TimeoutError('ambiguous insmod')
        if self.error == 'deadline':
            self.now = 31
        instance = next(iter(self.fs.instances))
        group = instance.rsplit('/',1)[1]
        names = {k: group+'_'+k for k in collector.PROBES}
        class NamedSession: pass
        session = NamedSession(); session.names = names
        raw = fixtures.trace(session)
        self.fs.values[instance+'/trace'] = raw.encode()
        self.fs.values[instance+'/per_cpu/cpu0/stats'] = fixtures.STAT.format(n=7).encode()
        for name in names.values(): self.fs.hits[name] = 1

    def cached_result(self):
        self.calls.append('cached')
        if self.error == 'cache': raise OSError('cached result unavailable')
        if self.error == 'malformed': return 'invalid cached format\n'
        return refusal()

    def unload(self, timeout):
        self.calls.append(('unload', timeout))
        # No trace instance/probe may remain at the module-release boundary.
        if self.error != 'cleanup':
            assert not self.fs.instances
            assert len(self.fs.definitions) == 1
        if self.error == 'unload': raise TimeoutError('unload timeout')
        self.module = False

    def pause(self, seconds):
        self.calls.append(('pause', seconds))
        self.now += seconds
        if self.error == 'interrupt': raise KeyboardInterrupt('mock interrupt')
        if self.error == 'cleanup':
            self.fs.fail = lambda p,v: p == 'kprobe_events' and v.startswith('-:')


class CoordinatorTests(unittest.TestCase):
    def exercise(self, error=None, setup_failure=False):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)/'capture'; fs = fixtures.MockFS(); ops = Ops(fs,error)
            if setup_failure: fs.clock = b'[local] global\n'
            result = coordinator.run_once(fs, output, ops, lambda: ops.now, ops.pause)
            persisted = json.loads((output/'summary.json').read_text())
            self.assertEqual(result, persisted)
            return result, ops.calls, fs

    def test_one_refusal_bound_then_cleanup_unload(self):
        result, calls, fs = self.exercise()
        self.assertEqual(result['verdict'], 'PASSIVE_REFUSAL_CAPTURED',result)
        self.assertTrue(result['observer_unloaded'])
        self.assertTrue(result['binding']['observer_trace_bound'])
        self.assertEqual(result['observer']['count'],1)
        self.assertEqual(calls.count(('load',5)),1)
        self.assertEqual(calls.count(('unload',10)),1)
        self.assertEqual(calls.count(('pause',.5)),1)
        self.assertEqual(calls.count('cached'),2) # one terminal, one preservation
        self.assertFalse(result['PPS'] or result['pump_ON'] or result['current_increase'])
        self.assertFalse(result['timing_acceptance'] or result['device_endpoint_qualified'])
        self.assertFalse(fs.instances)

    def test_rejected_preflight_never_touches_trace_or_module(self):
        result,calls,fs = self.exercise('preflight')
        self.assertEqual(result['verdict'],'STOP')
        self.assertFalse(result['observer_load_attempted'])
        self.assertFalse(fs.operations)
        self.assertNotIn(('unload',10),calls)

    def test_wrong_cmdline_never_touches_trace(self):
        _,calls,fs = self.exercise('cmdline')
        self.assertFalse(fs.operations)
        self.assertNotIn(('load',5),calls)

    def test_old_module_forbidden(self):
        _,calls,fs = self.exercise('old-module')
        self.assertFalse(fs.operations)
        self.assertNotIn(('load',5),calls)

    def test_preloaded_observer_not_adopted_or_unloaded(self):
        _,calls,fs = self.exercise('preloaded')
        self.assertFalse(fs.operations)
        self.assertNotIn(('unload',10),calls)

    def test_boot_changes_before_setup(self):
        _,calls,fs = self.exercise('boot-before')
        self.assertFalse(fs.operations)
        self.assertNotIn(('load',5),calls)

    def test_setup_failure_cleans_without_loading(self):
        result,calls,fs = self.exercise(setup_failure=True)
        self.assertEqual(result['verdict'],'STOP')
        self.assertFalse(fs.instances)
        self.assertNotIn(('load',5),calls)

    def test_ambiguous_load_timeout_no_reload(self):
        result,calls,fs = self.exercise('load')
        self.assertEqual(result['verdict'],'STOP')
        self.assertEqual(calls.count(('load',5)),1)
        self.assertEqual(calls.count(('unload',10)),1)
        self.assertFalse(fs.instances)

    def test_cache_failure_no_new_request(self):
        result,calls,_ = self.exercise('cache')
        self.assertEqual(result['verdict'],'STOP')
        self.assertEqual(calls.count(('load',5)),1)
        self.assertEqual(calls.count(('unload',10)),1)
        self.assertNotIn(('pause',.5),calls)

    def test_malformed_terminal_is_stop(self):
        result,calls,_ = self.exercise('malformed')
        self.assertEqual(result['verdict'],'STOP')
        self.assertEqual(calls.count(('unload',10)),1)

    def test_deadline_no_observation_retry(self):
        result,calls,_ = self.exercise('deadline')
        self.assertEqual(result['verdict'],'STOP')
        self.assertTrue(any('deadline' in e for e in result['errors']))
        self.assertEqual(calls.count(('load',5)),1)
        self.assertNotIn(('pause',.5),calls)

    def test_live_boot_change_no_pass(self):
        result,calls,_ = self.exercise('boot-live')
        self.assertEqual(result['verdict'],'STOP')
        self.assertTrue(any('boot changed' in e for e in result['errors']))
        self.assertEqual(calls.count(('load',5)),1)

    def test_tail_interruption_still_cleans_unloads(self):
        result,calls,fs = self.exercise('interrupt')
        self.assertEqual(result['verdict'],'STOP')
        self.assertFalse(fs.instances)
        self.assertEqual(calls.count(('unload',10)),1)

    def test_unload_failure_preserved(self):
        result,calls,_ = self.exercise('unload')
        self.assertEqual(result['verdict'],'STOP')
        self.assertFalse(result['observer_unloaded'])
        self.assertEqual(calls.count(('unload',10)),1)

    def test_cleanup_failure_preserved(self):
        result,_,_ = self.exercise('cleanup')
        self.assertEqual(result['verdict'],'STOP')
        self.assertTrue(any('trace cleanup' in e for e in result['errors']))

    def test_existing_output_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            output=Path(tmp); fs=fixtures.MockFS(); ops=Ops(fs)
            with self.assertRaises(FileExistsError):coordinator.run_once(fs,output,ops)
            self.assertFalse(ops.calls or fs.operations)

    def test_counter_loss_never_grants_timing(self):
        with tempfile.TemporaryDirectory() as tmp:
            fs=fixtures.MockFS(); ops=Ops(fs)
            original=ops.pause
            def loss(seconds):
                original(seconds)
                instance=next(iter(fs.instances))
                fs.values[instance+'/per_cpu/cpu0/stats']=fixtures.STAT.format(n=7).replace('overrun: 0','overrun: 1',1).encode()
            result=coordinator.run_once(fs,Path(tmp)/'capture',ops,lambda:ops.now,loss)
            self.assertEqual(result['verdict'],'STOP')
            self.assertTrue(result['observer_unloaded'])
            self.assertEqual(result['trace_analysis']['verdict'],'UNKNOWN')

    def test_gate_ast_identical_to_frozen275(self):
        before=ast.parse((A.parent/'test-275-passive-fresh-acquisition/gate.py').read_text())
        after=ast.parse((A/'observer_gate.py').read_text())
        for name in ('require','observer'):
            a=next(n for n in before.body if isinstance(n,ast.FunctionDef) and n.name==name)
            b=next(n for n in after.body if isinstance(n,ast.FunctionDef) and n.name==name)
            self.assertEqual(ast.dump(a),ast.dump(b))
        for name in ('HEADER','FIELDS'):
            def value(tree):
                return next(n.value for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id==name for t in n.targets))
            self.assertEqual(ast.dump(value(before)),ast.dump(value(after)))


class BindingTests(unittest.TestCase):
    def parsed(self):return coordinator.observer(refusal())
    def trace(self):
        return {'verdict':'BOUNDED_TRACE_ATTRIBUTED','requests':[{'return_code':-110,'entry_ns':1000000000,'return_ns':1101000000}]}
    def test_millisecond_floor_envelope(self):
        trace=self.trace();trace['requests'][0]['entry_ns']+=999999
        trace['requests'][0]['return_ns']+=999999
        self.assertTrue(coordinator.bind(trace,self.parsed())['observer_trace_bound'])
    def test_clock_before_request_rejected(self):
        trace=self.trace();trace['requests'][0]['entry_ns']-=1
        with self.assertRaisesRegex(ValueError,'BOOTTIME envelope'):coordinator.bind(trace,self.parsed())
    def test_clock_at_upper_boundary_rejected(self):
        trace=self.trace();trace['requests'][0]['return_ns']=1102000000
        with self.assertRaisesRegex(ValueError,'BOOTTIME envelope'):coordinator.bind(trace,self.parsed())
    def test_provider_return_mismatch(self):
        trace=self.trace();trace['requests'][0]['return_code']=0
        with self.assertRaisesRegex(ValueError,'provider return differs'):coordinator.bind(trace,self.parsed())
    def test_request_count_mismatch(self):
        trace=self.trace();trace['requests']*=2
        with self.assertRaisesRegex(ValueError,'request count differs'):coordinator.bind(trace,self.parsed())
    def test_unknown_trace_rejected(self):
        trace=self.trace();trace['verdict']='UNKNOWN'
        with self.assertRaisesRegex(ValueError,'attribution UNKNOWN'):coordinator.bind(trace,self.parsed())


if __name__=='__main__': unittest.main(verbosity=2)
