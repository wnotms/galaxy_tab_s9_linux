import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

ROOT=Path(__file__).resolve().parents[1]
R=ROOT/'reference/boot-tests/test-386-diag-minimal-overlay'
spec=importlib.util.spec_from_file_location('ssc386_flow',R/'host_flow.py')
H=importlib.util.module_from_spec(spec);spec.loader.exec_module(H)


class ParentScopeTests(unittest.TestCase):
    def setUp(self):
        self.inventory=json.loads((ROOT/'reference/boot-tests/test-383-ssc-bounded-boot-history/runtime-discovery/glink-complete.json').read_text())
        self.boot=self.inventory['boot_id']

    def test_exact_native_unbound_adsp_parent_accepted(self):
        parent=H.control_parent(self.inventory,self.boot)
        self.assertTrue(parent.startswith('/sys/devices/platform/soc@0/6800000.remoteproc/'))
        self.assertTrue(parent.endswith('rpmsg_ctrl.0.0'))

    def test_duplicate_or_missing_parent_stops(self):
        parent=next(x for x in self.inventory['rpmsg'] if x['name']=='rpmsg_ctrl')
        for rows in ([x for x in self.inventory['rpmsg'] if x['name']!='rpmsg_ctrl'],self.inventory['rpmsg']+[parent]):
            with self.assertRaises(ValueError):H.control_parent(self.inventory|{'rpmsg':rows},self.boot)

    def test_bound_parent_is_not_adopted(self):
        parent=next(x for x in self.inventory['rpmsg'] if x['name']=='rpmsg_ctrl')
        parent['driver']='foreign-or-existing-driver'
        with self.assertRaises(ValueError):H.control_parent(self.inventory,self.boot)

    def test_foreign_processor_parent_is_rejected(self):
        parent=next(x for x in self.inventory['rpmsg'] if x['name']=='rpmsg_ctrl')
        parent['resolved']=parent['resolved'].replace('6800000.remoteproc','3000000.remoteproc')
        with self.assertRaises(ValueError):H.control_parent(self.inventory,self.boot)

    def test_stale_boot_inventory_is_rejected(self):
        with self.assertRaises(ValueError):H.control_parent(self.inventory,'11111111-1111-1111-1111-111111111111')

    def test_no_rpc_or_protocol_mask_scope(self):
        self.assertFalse(H.PLAN['runtime_daemons_planned']);self.assertEqual(H.PLAN['rpc_launch_order'],[])
        self.assertFalse(H.PLAN['payload_writes']);self.assertFalse(H.PLAN['masks_sent'])
        self.assertFalse(H.PLAN['live_control_unload_allowed'])
        self.assertEqual(H.PLAN['recovery_stable_snapshots'],3)
        self.assertEqual(H.PLAN['recovery_stable_window_seconds'],8)
        self.assertFalse(H.PLAN['recovery_failed_command_retry'])
        self.assertEqual(H.PLAN['ledger_directory'],'/run/gts9-test386')
        self.assertEqual(H.PLAN['helper_device_deadline_seconds'],15)
        self.assertEqual(H.PLAN['helper_host_deadline_seconds'],19)
        self.assertEqual(H.PLAN['helper_packet_max_bytes'],65536)
        self.assertFalse(hasattr(H.C,'discover'));self.assertFalse(hasattr(H.C,'runtime'))
        self.assertEqual(len(H.C.read(R/'desktop-manifest.json')),5)

    def test_original_kernel_vendor_config_and_181_manifest_reused(self):
        old=H.C.read(ROOT/'reference/boot-tests/test-383-ssc-bounded-boot-history/PACKAGE.json')
        for key in ('baseline_partitions','candidate_partitions'):
            self.assertEqual(H.C.PACKAGE[key],old[key])
        self.assertEqual(H.PLAN['baseline_config_sha256'],H.PLAN['candidate_config_sha256'])
        self.assertEqual(H.PLAN['trace_instance'],'gts9_test382')
        self.assertEqual(len((R/'candidate-modules.sha256').read_text().splitlines()),181)
        self.assertFalse(H.PLAN['PPS']);self.assertFalse(H.PLAN['pump_ON'])


class FirstFailureRecoveryTests(unittest.TestCase):
    def setUp(self):
        t=tempfile.TemporaryDirectory();self.addCleanup(t.cleanup);self.root=Path(t.name)
        self.rec=Mock(folder=self.root/'diagnostic')
        def recorder(path):
            path.mkdir(exist_ok=False);return self.rec
        self.boot='11111111-1111-1111-1111-111111111111'
        self.state=dict(phase='accepted-candidate-kept-text',boot_id=self.boot,rollback_required=True)
        patches=[patch.object(H,'R',self.root),patch.object(H.C,'verify_inputs'),
            patch.object(H.C,'read',return_value=self.state),patch.object(H.C.p,'Recorder',side_effect=recorder),
            patch.object(H,'diagnostic',return_value=dict(boot_id=self.boot,complete=True)),
            patch.object(H.C,'trace_collect'),patch.object(H.C,'trace_inventory'),
            patch.object(H.C,'snapshot',return_value=dict(uptime=80)),patch.object(H.C,'native_gate'),
            patch.object(H.C,'transport_admit'),patch.object(H.C,'scan',return_value=dict(fault_counts={})),
            patch.object(H.C,'restore',return_value=dict(verdict='EXACT370_DEBIAN_RESTORED'))]
        for p in patches:p.start();self.addCleanup(p.stop)

    def test_success_restores_once_and_never_claims_ssc(self):
        result=H.probe();H.C.restore.assert_called_once()
        self.assertFalse(result['SSC_tested']);self.assertFalse(result['live_control_unloaded'])
        self.assertTrue((self.root/'rollback-complete.json').exists())

    def test_helper_failure_preserved_then_restore_once_without_retry(self):
        H.diagnostic.side_effect=ValueError('DIAG open failed')
        with self.assertRaisesRegex(ValueError,'DIAG open failed'):H.probe()
        H.diagnostic.assert_called_once();H.C.restore.assert_called_once()
        self.assertTrue(json.loads((self.root/'first-diagnostic-failure.json').read_text())['no_retry'])

    def test_new_kernel_fault_stops_and_restores(self):
        H.C.scan.side_effect=ValueError('new kernel fault')
        with self.assertRaisesRegex(ValueError,'new kernel fault'):H.probe()
        H.C.restore.assert_called_once()
        self.assertFalse((self.root/'diagnostic/summary.json').exists())

    def test_trace_collection_failure_never_becomes_success(self):
        H.C.trace_collect.side_effect=ValueError('trace loss')
        with self.assertRaisesRegex(ValueError,'trace loss'):H.probe()
        H.C.restore.assert_called_once()
        self.assertTrue((self.root/'diagnostic/glink-collection-error.json').exists())

    def test_failed_restoration_has_explicit_recovery_requirement(self):
        H.C.restore.side_effect=TimeoutError('ADB unavailable')
        with self.assertRaises(TimeoutError):H.probe()
        self.assertTrue(json.loads((self.root/'recovery-required.json').read_text())['manual_TWRP_required'])
        self.assertFalse((self.root/'rollback-complete.json').exists())

    def test_failed_input_admission_cannot_touch_diagnostic_or_reboot(self):
        H.C.verify_inputs.side_effect=ValueError('source drift')
        with self.assertRaises(ValueError):H.probe()
        H.diagnostic.assert_not_called();H.C.restore.assert_not_called()

    def test_second_probe_is_rejected_without_second_restore(self):
        self.rec.folder.mkdir()
        with self.assertRaises(ValueError):H.probe()
        H.diagnostic.assert_not_called();H.C.restore.assert_not_called()

    def test_wrong_candidate_phase_is_rejected(self):
        self.state['phase']='already-restored'
        with self.assertRaises(ValueError):H.probe()
        H.diagnostic.assert_not_called();H.C.restore.assert_not_called()


class RecoveryBeforeMutationTests(unittest.TestCase):
    def run_install(self, admission_error=None):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder)
            pre=dict(verdict='READY_FOR_ONE_CONTROLLED_BOOT',epoch=H.C.time.time(),boot_id='11111111-1111-1111-1111-111111111111')
            order=[]
            def enter(rec):
                order.append('enter');H.C.p.SERIAL='R52X10045LT'
            def admit(rec):
                order.append('admit')
                if admission_error:raise admission_error
            def transfer(rec):
                order.append('transfer');raise ValueError('sentinel-before-installation')
            with patch.object(H.C,'R',root), patch.object(H.C,'verify_inputs'), patch.object(H.C,'verify_stage'), patch.object(H.C,'read',return_value=pre), patch.object(H.C,'snapshot'), patch.object(H.C.p,'Recorder'), patch.object(H.C.h,'enter_recovery',side_effect=enter), patch.object(H.C.recovery_admission,'admit',side_effect=admit), patch.object(H.C,'transfer',side_effect=transfer) as tx, patch.object(H.C,'write_partition') as write, patch.object(H.C,'assets') as assets, patch.object(H.C,'desktop_overlay') as desktop, patch.object(H.C,'restore') as restore:
                with self.assertRaises(ValueError):H.C.install()
                write.assert_not_called();assets.assert_not_called();desktop.assert_not_called()
                restore.assert_called_once_with(from_recovery=True)
                failure=json.loads((root/'first-failure.json').read_text())
                self.assertTrue(failure['no_retry'])
                return order,tx.call_count,failure['error']
    def test_failed_recovery_admission_cannot_transfer_remount_or_install(self):
        order,count,error=self.run_install(ValueError('closed-gate'))
        self.assertEqual(order,['enter','admit']);self.assertEqual(count,0)
        self.assertEqual(error,'closed-gate')
    def test_passing_gate_precedes_transfer(self):
        order,count,error=self.run_install()
        self.assertEqual(order,['enter','admit','transfer']);self.assertEqual(count,1)
        self.assertEqual(error,'sentinel-before-installation')

if __name__=='__main__':unittest.main()
