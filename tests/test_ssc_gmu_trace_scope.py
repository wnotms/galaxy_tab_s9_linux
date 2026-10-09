"""Test372 ownership, no module/boot writes, gated single-start and fault cleanup."""
import importlib.util
import json
import inspect
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-372-ssc-gmu-trace'
def load(name,path):
 s=importlib.util.spec_from_file_location(name,path);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
H=load('ssc372_flow',R/'host_flow.py')
M=load('ssc372_runtime',R/'runtime.py')
D=load('ssc372_overlay',R/'desktop.py')
O=load('ssc372_fixture',ROOT/'tests/test_ssc_runtime_transaction.py')

class RuntimeTests(unittest.TestCase):
 def setUp(self):
  patcher=patch.multiple(O,M=M,PLAN=H.PLAN|{'boot_id':'11111111-1111-1111-1111-111111111111'})
  patcher.start();self.addCleanup(patcher.stop)
  O.RuntimeTransactionTests.setUp(self)
  self.status={row['package']:'1\tinstalled' for row in self.packages}
  for name,data in self.overrides.items():
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(data)
  self.runner.plan=dict(self.runner.plan)
  for name,key in [('usr/local/lib/gts9-test372/hexagonrpcd','trace_sha256'),('usr/lib/aarch64-linux-gnu/libhexagonrpc.so.0.4','trace_library_sha256')]:
   p=self.root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(name.encode());self.runner.plan[key]=M.sha(p)
  p=self.root/'usr/bin/stdbuf';p.parent.mkdir(parents=True,exist_ok=True);p.touch()
 def invoke(self,argv,**kw):
  if argv[:2]==['systemctl','show']:return '/usr/bin/stdbuf -oL -eL /usr/local/lib/gts9-test372/hexagonrpcd'
  return O.RuntimeTransactionTests.invoke(self,argv,**kw)
 prepare=O.RuntimeTransactionTests.prepare
 state=O.RuntimeTransactionTests.state
 def test_reuses_installed_payload_without_dpkg_or_start(self):
  self.prepare();self.assertFalse(any(c[0]=='dpkg' or c[:2]==['systemctl','start'] for c in self.calls))
  self.assertFalse(self.runner.path(M.GATE).exists())
 def test_missing_or_different_package_never_installed(self):
  for status in ('old\tinstalled','not-installed',''):
   self.status['libssc2']=status
   with self.assertRaises(ValueError):self.prepare()
   self.assertFalse(any(c[0]=='dpkg' for c in self.calls))
   self.runner.path(M.STATE).unlink(missing_ok=True)
 def test_closed_gate_required_not_replaced(self):
  p=self.root/next(iter(self.overrides));p.unlink()
  with self.assertRaises(ValueError):self.prepare()
  self.assertFalse(p.exists());self.assertFalse(self.runner.path(M.GATE).exists())
 def test_trace_integrity_blocks_start(self):
  self.prepare();self.runner.path('/usr/local/lib/gts9-test372/hexagonrpcd').write_bytes(b'bad')
  with self.assertRaises(ValueError):self.runner.start()
  self.assertFalse(self.runner.path(M.GATE).exists());self.assertFalse(self.state()['started'])
 test_bad_archive_has_no_ledger_or_package_write=O.RuntimeTransactionTests.test_bad_archive_has_no_ledger_or_package_write
 test_second_provisioning_refused=O.RuntimeTransactionTests.test_second_provisioning_refused
 test_duplicate_userspace_mapper_not_allowed=O.RuntimeTransactionTests.test_duplicate_userspace_mapper_not_allowed
 test_root_fastrpc_account_refused=O.RuntimeTransactionTests.test_root_fastrpc_account_refused
 test_start_is_single_and_persisted_before_launch=O.RuntimeTransactionTests.test_start_is_single_and_persisted_before_launch
 test_boot_change_blocks_start=O.RuntimeTransactionTests.test_boot_change_blocks_start
 test_thermal_fault_blocks_start=O.RuntimeTransactionTests.test_thermal_fault_blocks_start
 test_proxy_start_separate_and_once=O.RuntimeTransactionTests.test_proxy_start_separate_and_once
 test_deactivate_clears_gate_before_any_stop=O.RuntimeTransactionTests.test_deactivate_clears_gate_before_any_stop
 test_unconfirmed_stop_not_claimed=O.RuntimeTransactionTests.test_unconfirmed_stop_not_claimed

class OverlayTests(unittest.TestCase):
 def setUp(self):
  t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)/'root';self.incoming=Path(t.name)/'incoming'
  (self.root/'etc').mkdir(parents=True);self.incoming.mkdir();(self.root/'etc/machine-id').write_text(D.MACHINE)
  self.manifest={}
  for i,name in enumerate(sorted(D.ALLOWED)):
   src=self.incoming/str(i);src.write_bytes(name.encode())
   self.manifest[name]=dict(incoming=src.name,sha256=D.digest(src.read_bytes()),mode=0o644,original_sha256=None)
 def test_roundtrip_only_own_files_keeps_existing_usb_and_inputs(self):
  keep=self.root/'etc/systemd/system/gts9-usb-typec-lifecycle.service';keep.parent.mkdir(parents=True,exist_ok=True);keep.write_bytes(b'keep')
  D.install(self.root,self.incoming,self.manifest);D.restore(self.root)
  self.assertEqual(keep.read_bytes(),b'keep');self.assertTrue(all(not (self.root/n).exists() for n in D.ALLOWED))
 def test_preexisting_overlay_refused_without_ledger(self):
  p=self.root/next(iter(D.ALLOWED));p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'preexisting')
  with self.assertRaises(ValueError):D.install(self.root,self.incoming,self.manifest)
  self.assertFalse((self.root/D.STATE).exists())
 def test_partial_copy_is_restorable(self):
  original=D.atomic;count=0
  def fail(*a,**kw):
   nonlocal count
   count+=1
   if count==4:raise OSError('disk fault')
   return original(*a,**kw)
  with patch.object(D,'atomic',side_effect=fail):
   with self.assertRaises(OSError):D.install(self.root,self.incoming,self.manifest)
  D.restore(self.root);self.assertTrue(all(not (self.root/n).exists() for n in D.ALLOWED))
 def test_unknown_owned_content_blocks_removal(self):
  D.install(self.root,self.incoming,self.manifest);p=self.root/next(iter(D.ALLOWED));p.write_bytes(b'unknown')
  with self.assertRaises(ValueError):D.restore(self.root)
  self.assertEqual(p.read_bytes(),b'unknown')

class ScopeTests(unittest.TestCase):
 def test_vendor_only_allowlist_no_boot_or_module_operations(self):
  self.assertEqual(H.PACKAGE['write_partitions'],['vendor_boot'])
  self.assertEqual(H.PACKAGE['baseline_partitions']['boot'],H.PACKAGE['candidate_partitions']['boot'])
  src=inspect.getsource(H.install)+inspect.getsource(H.restore)
  self.assertNotIn('module-swap',src);self.assertNotIn('restore-modules',src)
  with self.assertRaises(ValueError):H.write_partition(Mock(),'boot','boot.img','0'*64,'1'*64)
 def test_exact_registered_vendor_source_required_before_write(self):
  rec=Mock()
  with self.assertRaises(ValueError):H.write_partition(rec,'vendor_boot','unregistered.img','0'*64,'1'*64)
  rec.adb.assert_not_called()
 def test_only_five_owned_overlay_files(self):
  self.assertEqual(set(H.read(R/'desktop-manifest.json')),D.ALLOWED)
  self.assertEqual(len(D.ALLOWED),5)
  self.assertFalse(any('palm' in n or 'wacom' in n or 'usb-typec' in n for n in D.ALLOWED))
 def test_no_fixed_diagnostic_or_charge_escalation(self):
  self.assertFalse(H.PLAN['PPS']);self.assertFalse(H.PLAN['pump_ON'])
  self.assertEqual(H.PLAN['baseline_config_sha256'],H.PLAN['candidate_config_sha256'])
  self.assertEqual(H.PLAN['baseline_notes_sha256'],H.PLAN['candidate_notes_sha256'])
 def test_corrected_native_observers_staged(self):
  s=inspect.getsource(H.stage);self.assertIn('qrtr-native-snapshot.py',s);self.assertIn('native-mapper-snapshot.py',s)
  self.assertNotIn("'qrtr-snapshot.py'",s)
 def test_accelerometer_must_be_actual_finite_plausible(self):
  self.assertEqual(H.sample('Accelerometer sensor measurement: X=0 Y=9.8 Z=0 m/s²')['y'],9.8)
  self.assertIsNone(H.sample('found SSC service'))
  for v in ('nan','inf','0','1000'):
   with self.assertRaises(ValueError):H.sample(f'Accelerometer sensor measurement: X={v} Y=0 Z=0 m/s²')
 def test_boundary_fault_stops_and_restores_without_launch_retry(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(H,'R',Path(tmp)):
   (Path(tmp)/'mutation-state.json').write_text(json.dumps(dict(phase='accepted-candidate-kept-text',boot_id=H.PLAN['before_boot_id'])))
   with patch.object(H,'snapshot',side_effect=ValueError('boundary')),patch.object(H,'collect_runtime'),patch.object(H,'qrtr'),patch.object(H,'runtime') as rt,patch.object(H,'restore') as restore:
    with self.assertRaisesRegex(ValueError,'boundary'):H.discover()
    self.assertEqual([c.args[1] for c in rt.call_args_list],['deactivate']);restore.assert_called_once()
    with self.assertRaises(ValueError):H.discover()
 def test_trace_runtime_backstop_no_restart(self):
  for n in ('hexagonrpcd-adsp-rootpd-trace.conf','hexagonrpcd-adsp-sensorspd-trace.conf'):
   s=(R/n).read_text();self.assertIn('RuntimeMaxSec=120s',s);self.assertIn('Restart=no',s)


G=load('ssc372_asset_fixture',ROOT/'tests/test_early_adsp_controlled_boot.py')
A=load('ssc372_assets',R/'assets.py')
class AssetTests(G.AssetTransactionTests):
 def setUp(self):
  patcher=patch.object(G,'A',A);patcher.start();self.addCleanup(patcher.stop)
  super().setUp()

class RegressionTests(unittest.TestCase):
 def test_same_kernel_requires_explicit_baseline_wifi_phase(self):
  source=inspect.getsource(H.wifi)
  self.assertNotIn("d['config_sha256']==",source)
  self.assertIn("phase='baseline'",inspect.getsource(H.preflight))
  self.assertIn('phase=phase',inspect.getsource(H.accept))
 def test_gmu_hfi_cannot_inherit_historical_waiver(self):
  rec=Mock();rec.adb.return_value=('Message HFI_H2F_MSG_GX_BW_PERF_VOTE id 42 timed out',0)
  with self.assertRaisesRegex(ValueError,'GMU HFI regression'):H.scan(rec,H.PLAN['before_boot_id'],150)
 def test_baseline_enrollment_has_no_future_error_waiver(self):
  baseline=H.PLAN['baseline_observation'];p=ROOT/baseline['path']
  self.assertEqual(H.sha(p),baseline['sha256'])
  rows=[json.loads(x) for x in p.read_text().splitlines()]
  self.assertIn(baseline['prior_nonfatal_keyboard_row'],rows)
  self.assertIn('future_error_waiver=False',inspect.getsource(H.preflight_scan))
  guard=H.load('ssc372_delta_fixture',ROOT/'reference/boot-tests/test-371-usb-lifecycle-gmu/host_flow.py')
  old=[dict(__CURSOR='old',PRIORITY='6',MESSAGE='normal')]
  new=old+[dict(__CURSOR='new',PRIORITY='3',MESSAGE=baseline['prior_nonfatal_keyboard_row']['MESSAGE'])]
  with self.assertRaises(ValueError):guard.health(new,old,{})
 def test_unknown_partition_refused_before_recovery_write(self):
  raw=''.join(v+'  /dev/block/by-name/'+n+'\n' for n,v in H.PACKAGE['baseline_partitions'].items())
  self.assertEqual(H.restore_layout(raw),H.PACKAGE['baseline_partitions'])
  with self.assertRaises(ValueError):H.restore_layout(raw.replace(H.PACKAGE['baseline_partitions']['boot'],'0'*64))

if __name__=='__main__':unittest.main()
