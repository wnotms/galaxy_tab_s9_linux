"""Exercise provisioning failure and one-start semantics on a temporary root."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1];R=ROOT/'reference/boot-tests/test-365-ssc-discovery'
sp=importlib.util.spec_from_file_location('ssc365_runtime_tests',R/'runtime.py');M=importlib.util.module_from_spec(sp);sp.loader.exec_module(M)
PLAN=json.loads((R/'registration.json').read_text())|{'boot_id':'11111111-1111-1111-1111-111111111111'}


class RuntimeTransactionTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name);self.incoming=self.root/'incoming';self.incoming.mkdir()
        (self.root/str(M.PREFIX).lstrip('/')/'sensors').mkdir(parents=True)
        (self.root/'dev').mkdir();(self.root/'dev/fastrpc-adsp').write_bytes(b'fixture')
        self.d=dict(boot_id=PLAN['boot_id'],machine_id=PLAN['machine_id'],config_sha256=PLAN['candidate_config_sha256'],notes_sha256=PLAN['candidate_notes_sha256'],cmdline=PLAN['runtime_cmdline'],dcc_absent=True,direct_default='N',
            battery=dict(POWER_SUPPLY_HEALTH='Good',POWER_SUPPLY_CAPACITY='60',POWER_SUPPLY_TEMP='300',POWER_SUPPLY_VOLTAGE_NOW='4100000'),failed_units='',services=dict(gdm='inactive'),
            adsp=[dict(state='running',firmware='qcom/sm8550/adsp.mdt')],fastrpc=['/dev/fastrpc-adsp'],native_socinfo=dict(boot_id=PLAN['boot_id']))
        self.mapping={n:n+'\n' for n in ('soc_id','hw_platform','platform_subtype','platform_subtype_id','platform_version')}
        self.packages=[];self.status={};self.calls=[];self.fail=None
        for n in ('libprotobuf-c1','libssc2','gts9-hexagonrpc','iio-sensor-proxy'):
            p=self.incoming/(n+'.deb');p.write_bytes(n.encode())
            self.packages.append(dict(package=n,version='1',filename=p.name,bytes=p.stat().st_size,sha256=M.sha(p),payload_files={},payload_links={}))
        self.overrides={f'etc/systemd/system/{u}.d/90-gts9-controlled-test.conf':'[Unit]\nConditionPathExists=/run/gts9-ssc-test/ready\n' for u in M.UNITS+('hexagonrpcd-sdsp.service',)}
        self.runner=M.Runtime(PLAN,lambda:self.d,lambda _:self.mapping,self.root,self.invoke)
        self.account=SimpleNamespace(pw_uid=123,pw_gid=123,pw_shell='/usr/sbin/nologin')
        for obj in (patch.object(M.pwd,'getpwnam',return_value=self.account),patch.object(M.os,'chown'),patch.object(M.stat,'S_ISCHR',return_value=True)):
            obj.start();self.addCleanup(obj.stop)
    def invoke(self,argv,**kwargs):
        self.calls.append(argv)
        if argv[0]=='dpkg-query':return self.status.get(argv[-1],'')
        if argv[0]=='dpkg':
            for n in self.overrides:self.assertTrue((self.root/n).exists())
            self.assertFalse(self.runner.path(M.GATE).exists())
            if self.fail:raise ValueError(self.fail)
            if argv[1]=='--configure':
                self.status.update({n:'1\tinstalled' for n in argv[2:]})
        if argv[:2]==['systemctl','is-active']:return 'inactive'
        return ''
    def prepare(self):return self.runner.prepare(self.incoming,self.packages,self.overrides)
    def state(self):return json.loads(self.runner.path(M.STATE).read_text())

    def test_prepare_keeps_services_inactive_and_writes_real_mapping(self):
        d=self.prepare();self.assertEqual(d['phase'],'prepared-inactive')
        self.assertFalse(d['started']);self.assertFalse(self.runner.path(M.GATE).exists())
        self.assertFalse(any(c[:2]==['systemctl','start'] for c in self.calls))
        for n,text in self.mapping.items():self.assertEqual(self.runner.path(M.PREFIX/'socinfo'/n).read_text(),text)
    def test_bad_archive_has_no_ledger_or_package_write(self):
        self.packages[0]['sha256']='0'*64
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.runner.path(M.STATE).exists());self.assertFalse(any(c[0]=='dpkg' for c in self.calls))
    def test_different_preexisting_package_not_replaced(self):
        self.status['libprotobuf-c1']='old\tinstalled'
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(any(c[0]=='dpkg' for c in self.calls))
    def test_not_installed_status_from_dpkg_is_accepted(self):
        self.status['iio-sensor-proxy']='not-installed';self.prepare()
    def test_dpkg_failure_quarantines_inactive_state(self):
        self.fail='mock configure error'
        with self.assertRaises(ValueError):self.prepare()
        self.assertEqual(self.state()['phase'],'provisioning-stopped');self.assertFalse(self.runner.path(M.GATE).exists())
        self.assertFalse(any(c[:2]==['systemctl','start'] for c in self.calls))
    def test_second_provisioning_refused(self):
        self.prepare();before=len(self.calls)
        with self.assertRaises(ValueError):self.prepare()
        self.assertEqual(len(self.calls),before)
    def test_missing_board_mapping_refused(self):
        del self.mapping['platform_version']
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.runner.path(M.STATE).exists())
    def test_root_fastrpc_account_refused(self):
        self.account.pw_uid=0
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.runner.path(M.GATE).exists())
    def test_duplicate_userspace_mapper_not_allowed(self):
        self.packages[-1]['package']='pd-mapper'
        with self.assertRaises(ValueError):self.prepare()
        self.assertFalse(self.runner.path(M.STATE).exists())
    def test_existing_soinfo_not_overwritten(self):
        self.runner.path(M.PREFIX/'socinfo').mkdir()
        with self.assertRaises(ValueError):self.prepare()
    def test_start_is_single_and_persisted_before_launch(self):
        self.prepare();original=self.invoke
        def check(argv,**kw):
            if argv[:2]==['systemctl','start']:
                self.assertTrue(self.state()['started']);self.assertEqual(self.runner.path(M.GATE).read_text(),PLAN['boot_id']+'\n')
                self.assertEqual(tuple(argv[3:]),M.UNITS[:-1])
            return original(argv,**kw)
        self.runner.invoke=check;self.runner.start()
        with self.assertRaises(ValueError):self.runner.start()
        self.assertEqual(sum(c[:2]==['systemctl','start'] for c in self.calls),1)
    def test_lost_launch_reply_cannot_replay_start(self):
        self.prepare()
        def lost(argv,**kw):raise OSError('lost launch reply')
        self.runner.invoke=lost
        with self.assertRaises(OSError):self.runner.start()
        self.assertTrue(self.state()['started'])
        with self.assertRaises(ValueError):self.runner.start()
    def test_detach_or_adsp_offline_blocks_start(self):
        self.prepare();self.d['adsp'][0]['state']='offline'
        with self.assertRaises(ValueError):self.runner.start()
        self.assertFalse(self.runner.path(M.GATE).exists())
    def test_boot_change_blocks_start(self):
        self.prepare();self.d['boot_id']='22222222-2222-2222-2222-222222222222'
        with self.assertRaises(ValueError):self.runner.start()
    def test_thermal_fault_blocks_start(self):
        self.prepare();self.d['battery']['POWER_SUPPLY_TEMP']='420'
        with self.assertRaises(ValueError):self.runner.start()
    def test_proxy_start_separate_and_once(self):
        self.prepare()
        with self.assertRaises(ValueError):self.runner.start_proxy()
        self.runner.start();self.runner.start_proxy()
        with self.assertRaises(ValueError):self.runner.start_proxy()
        self.assertTrue(self.state()['proxy_started'])

    def test_deactivate_clears_gate_before_any_stop(self):
        self.prepare();self.runner.start();original=self.invoke
        def check(argv,**kw):
            if argv[:2]==['systemctl','stop']:self.assertFalse(self.runner.path(M.GATE).exists())
            return original(argv,**kw)
        self.runner.invoke=check;d=self.runner.deactivate()
        self.assertEqual(d['phase'],'inactive-gated');self.assertTrue(d['qualified_passive_packages_retained'])
    def test_unconfirmed_stop_not_claimed(self):
        self.prepare();self.runner.start();original=self.invoke
        self.runner.invoke=lambda argv,**kw:'active' if argv[:2]==['systemctl','is-active'] else original(argv,**kw)
        with self.assertRaises(ValueError):self.runner.deactivate()
        self.assertFalse(self.runner.path(M.GATE).exists())


if __name__=='__main__':unittest.main()
