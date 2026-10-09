import ast
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-368-usb-cable-reconnect'
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
P=load('teardown',ROOT/'userspace/adbd/teardown-evidence.py')
D=load('scope368_device',R/'device.py')
H=load('scope368_host',R/'host_flow.py')
BOOT='01234567-89ab-cdef-0123-456789abcdef'
UNIT='gts9-test368-lifecycle.service'


class TeardownTests(unittest.TestCase):
    def row(self,**changes):
        return dict(dict(__CURSOR='new',_BOOT_ID=BOOT.replace('-',''),_TRANSPORT='kernel',
                         __MONOTONIC_TIMESTAMP='10004000',_SOURCE_MONOTONIC_TIMESTAMP='10004000',PRIORITY='3',
                         MESSAGE='dwc3-qcom a600000.usb: request 00000000f31e7287 was not queued to ep0out'),**changes)
    def events(self,stamps=(10,),boot=BOOT,unit=UNIT):
        return '\n'.join(json.dumps(dict(_BOOT_ID=boot.replace('-',''),_SYSTEMD_UNIT=unit,
                MESSAGE=json.dumps(dict(boot_id=boot,event='unbind',monotonic=t)))) for t in stamps)
    def classify(self,rows,events=None):
        return P.classify(rows,[],self.events() if events is None else events,BOOT,UNIT)

    def test_real_test367_raw_pair_matches_with_source_time(self):
        old=ROOT/'reference/boot-tests/test-367-usb-typec-lifecycle'
        d=json.loads(next(old.glob('install-*/initial-detached.json')).read_text())
        initial=json.loads((old/'active-preflight.json').read_text())['snapshot']
        rows=[json.loads(l) for l in d['kernel']['stdout'].splitlines()]
        before=[json.loads(l) for l in initial['kernel']['stdout'].splitlines()]
        out=P.classify(rows,before,d['lifecycle']['stdout'],d['boot_id'],'gts9-test367-lifecycle.service')
        self.assertEqual(len(out),1)
        self.assertLess(abs(out[0]['source_monotonic']-out[0]['unbind_monotonic']),.01)
        self.assertIn('pending transport gate',out[0]['classification'])

    def test_classifies_one_and_preserves_message(self):
        row=self.row()
        out=self.classify([row])
        self.assertEqual(out[0]['message'],row['MESSAGE'])
        self.assertIn('MESSAGE',row)

    def test_missing_event_or_source_timestamp_stops(self):
        with self.assertRaises(ValueError):self.classify([self.row()],events='')
        row=self.row();del row['_SOURCE_MONOTONIC_TIMESTAMP']
        with self.assertRaises(ValueError):self.classify([row])

    def test_outside_bound_and_ambiguous_events_stop(self):
        with self.assertRaises(ValueError):self.classify([self.row(_SOURCE_MONOTONIC_TIMESTAMP='11000000')])
        with self.assertRaises(ValueError):self.classify([self.row()],self.events((10,10.01)))

    def test_second_error_on_same_unbind_stops(self):
        with self.assertRaises(ValueError):self.classify([self.row(),self.row(__CURSOR='second')])

    def test_other_endpoint_message_or_severity_stops(self):
        for changes in (dict(MESSAGE='dwc3-qcom a600000.usb: request 00000000f31e7287 was not queued to ep1in'),
                        dict(MESSAGE='dwc3-qcom a600000.usb: transfer failed'),dict(PRIORITY='2')):
            with self.subTest(changes=changes),self.assertRaises(ValueError):self.classify([self.row(**changes)])

    def test_wrong_boot_or_foreign_unit_stops(self):
        for events in (self.events(boot='other'),self.events(unit='foreign.service')):
            with self.assertRaises(ValueError):self.classify([self.row()],events)
        with self.assertRaises(ValueError):self.classify([self.row(_BOOT_ID='other')])

    def test_no_teardown_error_is_allowed_and_old_error_remains_baseline(self):
        self.assertEqual(self.classify([]),[])
        row=self.row()
        self.assertEqual(P.classify([row],[row],'',BOOT,UNIT),[])

    def test_cpu_and_other_new_error_gates_remain_strict(self):
        row=self.row(MESSAGE='rcu: INFO: rcu_preempt detected stalls',PRIORITY='4')
        self.assertEqual(self.classify([row]),[])
        with self.assertRaises(ValueError):H.health([row],[],{})
        with self.assertRaises(ValueError):self.classify([self.row(MESSAGE='GMU message timed out')])


class RunnerReuseTests(unittest.TestCase):
    def test_transaction_functions_reused_without_logic_change(self):
        def funcs(path):
            return {n.name:ast.dump(n,include_attributes=False) for n in ast.parse(path.read_text()).body if isinstance(n,ast.FunctionDef)}
        old=funcs(ROOT/'reference/boot-tests/test-367-usb-typec-lifecycle/device.py')
        new=funcs(R/'device.py')
        for name in ('safe','digest','qualified','save_ledger','verify_files','install','restore_files','capture'):
            # Only the independent numeric test owner changes in ledger checks.
            self.assertEqual(old[name].replace('value=367','value=368').replace('test367-pending','test368-pending'),new[name])

    def test_actual_three_payload_transaction_restores_absent_files(self):
        rows=H.payload()
        with tempfile.TemporaryDirectory() as temp:
            D.install(temp,rows,BOOT)
            D.verify_files(temp,rows)
            self.assertEqual(D.restore_files(temp,rows,BOOT)['status'],'rolled_back')
            self.assertTrue(all(not (Path(temp)/p).exists() for p in D.PATHS))

    def test_guard_requires_frozen_source_and_does_not_import_or_cache(self):
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        source='class Gadget:\n def __init__(self, root, profile):\n  self.profile=profile\n'
        with patch.object(D.importlib.util,'spec_from_loader',side_effect=AssertionError('no bytecode import')):
            result=D.guard({'accepted':True},boot,source)
        self.assertEqual(result.profile,{'accepted':True})
        with self.assertRaises(ValueError):D.guard({},boot)


if __name__=='__main__':unittest.main()
