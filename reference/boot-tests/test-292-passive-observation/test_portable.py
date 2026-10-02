"""Offline Test292 packaging/boundary checks; never contacts hardware."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tarfile
import unittest
from unittest.mock import Mock
R=Path(__file__).resolve().parent
ROOT=R.parents[2]
sys.path.insert(0,str(R/'portable'))
def read(p):return json.loads(Path(p).read_text())
spec=importlib.util.spec_from_file_location('flow292',R/'host_flow.py');flow=importlib.util.module_from_spec(spec);spec.loader.exec_module(flow)
class PortableTests(unittest.TestCase):
 def test_one_call_registration(self):
  p=flow.PLAN;self.assertEqual(p['test'],'Test292');self.assertEqual(p['maximum_calls'],1);self.assertEqual(p['normal_candidate_boots'],1);self.assertEqual(p['observer_loads'],1);self.assertEqual(p['observer_cache_wait_seconds'],5)
 def test_no_activation(self):
  for k in ['PPS','pump_ON','current_increase','trace','direct_charging_authorized']:self.assertIs(flow.PLAN[k],False)
  self.assertEqual(flow.PLAN['diagnostic_collection_ms'],500)
 def test_exact_provider_consumer(self):
  q=read(R.parent/'test-291-passive-observer-offline/ARTIFACTS.json');self.assertEqual(flow.PLAN['candidate_notes_sha256'],q['provider']['kernel-notes.bin']['sha256']);self.assertEqual(flow.PLAN['observer_sha256'],q['observer']['sha256'])
 def test_only_boot_changed(self):
  a=flow.PACKAGE['baseline_partitions'];b=flow.PACKAGE['candidate_partitions'];self.assertEqual([x for x in a if a[x]!=b[x]],['boot']);self.assertEqual(flow.PACKAGE['write_partitions'],['boot'])
 def test_module_pairing(self):
  q=read(R.parent/'test-290-passive-observation-api/validation/module-hashes.json');q=q.get('modules',q)
  actual={x.split(maxsplit=1)[1]:x.split()[0] for x in (R/'candidate-modules.sha256').read_text().splitlines()};self.assertEqual(actual,q);self.assertEqual(len(actual),181)
 def test_original_manifest(self):
  q=read(R.parent/'test-263-sm5440-adc-snapshot/validation/artifact-audit.json')['modules'];actual={x.split(maxsplit=1)[1]:x.split()[0] for x in (R/'rollback-modules.sha256').read_text().splitlines()};self.assertEqual(q,actual)
 def test_unique_slots_only_name_change(self):
  old=(R.parent/'test-289-passive-i2c-phase-trace/module-swap.sh').read_text();self.assertEqual((R/'module-swap.sh').read_text(),old.replace('Test289','Test292').replace('test289','test292'))
 def test_frozen_portable(self):
  for f in ['device_ops.py','health_gate.py','coordinator.py','observation_gate.py']:self.assertEqual((R/'portable'/f).read_bytes(),(R.parent/'test-291-passive-observer-offline'/f).read_bytes())
 def test_flat_imports(self):
  import device_ops,health_gate,coordinator,observation_gate
  self.assertEqual(device_ops.PROVIDER_NOTES_SHA256,flow.PLAN['candidate_notes_sha256']);self.assertEqual(coordinator.OBSERVER_SHA256,flow.PLAN['observer_sha256'])
 def test_stage_hashes(self):
  for name,m in flow.STAGED.items():
   b=(Path('/mnt/d/android/gts9-active/gts9-test292')/name).read_bytes();self.assertEqual(hashlib.sha256(b).hexdigest(),m['sha256']);self.assertEqual(len(b),m['bytes'])
 def test_partition_missing_and_duplicate(self):
  with self.assertRaises(ValueError):flow.require_partitions('',flow.PACKAGE['baseline_partitions'])
  with self.assertRaises(ValueError):flow.partitions('aa /dev/block/by-name/boot\naa /dev/block/by-name/boot\n')
 def test_partition_match(self):
  expected=flow.PACKAGE['baseline_partitions'];flow.require_partitions('\n'.join(v+' /dev/block/by-name/'+k for k,v in expected.items()),expected)
 def test_parallel_failure_inspects_all(self):
  a=Mock(side_effect=ValueError('first'));b=Mock(return_value='second')
  with self.assertRaises(RuntimeError):flow.parallel(dict(a=a,b=b))
  a.assert_called_once();b.assert_called_once()
 def test_strict_authenticated_ssh(self):
  rec=Mock();rec.command.return_value=('ab'*16+'\nLinux\n',0);flow.ssh(rec,'wifi','127.0.0.1','ab'*16);args=rec.command.call_args.args[1];self.assertIn('StrictHostKeyChecking=yes',args);self.assertIn('HostKeyAlias=gts9-test292',args)
 def test_wrong_ssh_boot_stops(self):
  rec=Mock();rec.command.return_value=('cd'*16+'\n',0)
  with self.assertRaises(ValueError):flow.ssh(rec,'wifi','127.0.0.1','ab'*16)
 def test_syntax_and_no_trace(self):
  ast.parse((R/'host_flow.py').read_text());self.assertNotIn('/sys/kernel/tracing',(R/'host_flow.py').read_text())
if __name__=='__main__':unittest.main(verbosity=2)
