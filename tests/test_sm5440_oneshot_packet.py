"""New producer closing boundary and saved native-refusal packet replay."""
import importlib.util,json,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reference/boot-tests/test-326-fixed9-native-dispatch'
spec=importlib.util.spec_from_file_location('packet326_test',R/'host_flow.py');f=importlib.util.module_from_spec(spec);spec.loader.exec_module(f)

class PacketTests(unittest.TestCase):
 def test_actual_registered_producer_has_one_final_boundary_after_extensions(self):
  plan=json.loads((R/'registration.json').read_text());cmd=plan['candidate_command']
  self.assertEqual(cmd.count('echo @@boot;'),1)
  self.assertEqual(cmd.count('echo @@boot-end;'),1)
  self.assertLess(cmd.index('echo @@oneshot'),cmd.index('echo @@boot-end;'))
  self.assertLess(cmd.index('echo @@pack-thermal'),cmd.index('echo @@boot-end;'))
 def test_original325_duplicate_packet_remains_a_refusal(self):
  raw=(R.parent/'test-325-fixed9-native-off/candidate-admission/current-state.txt').read_text().replace('\r','')
  with self.assertRaisesRegex(ValueError,'duplicate section'):f.h.g.baseline.sections(raw)
 def test_single_boundary_packet_retains_original_native_refusal(self):
  raw=(R.parent/'test-325-fixed9-native-off/analysis/normalized-packet.txt').read_text();sec=f.h.g.baseline.sections(raw)
  self.assertEqual(sec['boot'].strip(),sec['boot-end'].strip())
  self.assertEqual(f.gate.values(sec['oneshot'])['oneshot_attempted'],'0')
  self.assertEqual(f.gate.values(sec['snapshot'])['fault'],'1')
  self.assertRaises(ValueError,f.gate.retained_observation,sec['oneshot'],sec['snapshot'],(R.parent/'test-325-fixed9-native-off/candidate-admission/kernel-json.txt').read_text(),sec['boot'].strip().replace('-',''))
 def test_original325_core_boot_end_is_not_reinterpreted_as_full_packet_close(self):
  plan=json.loads((R.parent/'test-325-fixed9-native-off/registration.json').read_text())
  self.assertEqual(plan['candidate_command'].count('echo @@boot-end;'),2)
  self.assertEqual(json.loads((R.parent/'test-325-fixed9-native-off/summary.json').read_text())['verdict'],'STOP_INITIAL_FIXED9_FAULT_RECHECK_RESTORED')
 def test_capture_still_restores_on_first_failure(self):
  import ast
  node=next(n for n in ast.parse((R/'host_flow.py').read_text()).body if isinstance(n,ast.FunctionDef) and n.name=='capture_and_restore');body=ast.unparse(node)
  self.assertIn('finally:',body);self.assertIn('restore()',body);self.assertIn("state.get('rollback_required')",body)

if __name__=='__main__':unittest.main()
