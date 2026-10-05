"""Actual host address enrollment refuses redirection before authentication."""
import importlib.util,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
FLOW=ROOT/'reference/boot-tests/test-324-native-oneshot-off/host_flow.py'

class AddressTests(unittest.TestCase):
 def setUp(self):
  spec=importlib.util.spec_from_file_location('oneshot_address_test',FLOW);self.f=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.f)
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.f.R=Path(self.tmp.name);self.f.PLAN={'candidate_config_sha256':'a'*64,'candidate_notes_sha256':'b'*64}
  (self.f.R/'preflight').mkdir();self.path=self.f.R/'preflight/summary.json';self.before=b'{"wifi":"10.139.153.116","boot_id":"old","battery":{"soc":59}}\n';self.path.write_bytes(self.before)
  (self.f.R/'mutation-state.json').write_text(json.dumps({'phase':'candidate-installed-awaiting-owner-fixed9-boot'}))
  self.response='3c2a1b8f2d624db4b5ffdc836050fcf6\n'+'a'*64+'  -\n'+'b'*64+'  /sys/kernel/notes\n'
 def probe(self,response=None,error=None):
  def call(*args,**kwargs):
   self.assertEqual(self.path.read_bytes(),self.before)
   self.assertEqual(kwargs['address'],'10.139.153.123')
   if error:raise error
   return response,0
  return patch.object(self.f,'ssh_command',side_effect=call)
 def test_refused_transport_never_changes_existing_address(self):
  with self.probe(error=ConnectionError('refused')):
   self.assertRaises(ConnectionError,self.f.wifi_address,'10.139.153.123')
  self.assertEqual(self.path.read_bytes(),self.before)
 def test_wrong_empty_or_partial_identity_never_changes_address(self):
  for response in ['', 'wrong\n', self.response.replace('a'*64,'c'*64), self.response+'extra\n']:
   with self.subTest(response=response),self.probe(response=response):
    self.assertRaises(ValueError,self.f.wifi_address,'10.139.153.123')
   self.assertEqual(self.path.read_bytes(),self.before)
 def test_authenticated_candidate_only_updates_address(self):
  with self.probe(response=self.response):result=self.f.wifi_address('10.139.153.123')
  expected=json.loads(self.before);expected['wifi']='10.139.153.123'
  self.assertEqual(json.loads(self.path.read_bytes()),expected);self.assertEqual(result['authenticated_address'],expected['wifi'])
  self.assertEqual(list(self.path.parent.iterdir()),[self.path])
 def test_atomic_publication_failure_preserves_old_packet(self):
  with self.probe(response=self.response),patch('os.replace',side_effect=OSError('mock publication failure')):
   self.assertRaises(OSError,self.f.wifi_address,'10.139.153.123')
  self.assertEqual(self.path.read_bytes(),self.before);self.assertEqual(list(self.path.parent.iterdir()),[self.path])
 def test_stopped_series_cannot_update_or_probe(self):
  (self.f.R/'mutation-state.json').write_text(json.dumps({'phase':'first-failure-awaiting-PC-unconditional-restore'}))
  with patch.object(self.f,'ssh_command') as probe:self.assertRaises(ValueError,self.f.wifi_address,'10.139.153.123');probe.assert_not_called()
  self.assertEqual(self.path.read_bytes(),self.before)
 def test_invalid_address_no_probe(self):
  with patch.object(self.f,'ssh_command') as probe:self.assertRaises(ValueError,self.f.wifi_address,'host; reboot');probe.assert_not_called()
  self.assertEqual(self.path.read_bytes(),self.before)

if __name__=='__main__':unittest.main()
