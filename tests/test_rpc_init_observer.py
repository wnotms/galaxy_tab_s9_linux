import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import test_registry_mutation_evidence as fixture

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'userspace/sensors'


def load(name, filename):
    spec=importlib.util.spec_from_file_location(name,BASE/filename)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m


P=load('init_profile_tests','rpc_init_trace_profile.py')
E=load('init_errors_tests','rpc_return_error_evidence.py')
M=load('init_mutation_tests','registry_init_evidence.py')
N=load('init_negative_tests','rpc_localctl_evidence.py')


class ObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temp.cleanup)
        cls.root=Path(cls.temp.name);cls.source=ROOT/'out/rpc-readdir/build/work/hexagonrpc'
        cls.report=P.prepare(cls.source,cls.root/'profile');cls.tree=cls.root/'profile'
        cls.binary=cls.root/'trace'
        cls.compile(cls.binary,cls.tree,'rpc_return_harness.c')
        cls.old=cls.root/'old';cls.compile(cls.old,cls.source,'rpc_return_harness.c')
        cls.localctl=cls.root/'localctl';cls.compile(cls.localctl,cls.source,'rpc_localctl_harness.c',sanitize=True)
        cls.limit=cls.root/'limit'
        subprocess.run(['cc','-std=gnu11','-Wall','-Wextra','-Werror','-fsanitize=undefined',
            '-fno-sanitize-recover=all','-I'+str(cls.tree/'hexagonrpcd'),
            str(ROOT/'tests/fixtures/rpc_init_trace_harness.c'),'-o',str(cls.limit)],
            check=True,capture_output=True,text=True,timeout=30)

    @classmethod
    def compile(cls,binary,tree,fixture_name,sanitize=False):
        command=['cc','-std=gnu11','-Wall','-Wextra','-Werror','-Wno-unused-function',
            '-Wno-unused-parameter','-ffunction-sections','-fdata-sections',
            '-DHEXAGONRPC_BUILD_METHOD_DEFINITIONS=1','-I'+str(tree/'include'),'-I'+str(tree/'hexagonrpcd'),
            str(ROOT/'tests/fixtures'/fixture_name),str(tree/'hexagonrpcd/iobuffer.c'),'-Wl,--gc-sections','-o',str(binary)]
        if sanitize:command[1:1]=['-fsanitize=undefined','-fno-sanitize-recover=all']
        subprocess.run(command,check=True,capture_output=True,text=True,timeout=30)

    def run_case(self,case='normal',budget=None,opt='1',binary=None):
        env=dict(os.environ);env.pop('HEXAGONRPC_RETURN_TRACE_BUDGET',None)
        env.pop('HEXAGONRPC_RETURN_TRACE',None)
        if opt is not None:env['HEXAGONRPC_RETURN_TRACE']=opt
        if budget is not None:env['HEXAGONRPC_RETURN_TRACE_BUDGET']=budget
        return subprocess.run([str(binary or self.binary),case],env=env,check=True,capture_output=True,text=True,timeout=8)

    def test_only_header_changes_full_source_and_callback_codec_library_exact(self):
        self.assertEqual(self.report['changed_files'],['hexagonrpcd/rpc-return-trace.h'])
        self.assertFalse(self.report['device_operations'])
        for n,h in self.report['profile']['base_source_files'].items():
            if n!='hexagonrpcd/rpc-return-trace.h':self.assertEqual(self.report['source_hashes'][n],h)

    def test_default_output_exactly_same_as_frozen_v2(self):
        for case in ['normal','large','budget','transport-error','frame-limit','null-frame']:
            with self.subTest(case=case):
                self.assertEqual(self.run_case(case).stderr,self.run_case(case,binary=self.old).stderr)

    def test_eight_mib_opt_in_exceeds_old_cap_but_remains_bounded(self):
        old=self.run_case('budget').stderr
        new=self.run_case('budget',budget='8388608').stderr
        self.assertGreater(len(new.encode()),1048576)
        self.assertLessEqual(len(new.encode()),8388608+100)
        # 1000 full records remain within8MiB; the fixture checks guard bytes.
        self.assertNotIn('RPCRETURN_LIMIT',new)
        self.assertIn('reason=budget',old)

    def test_invalid_unbounded_budget_rejected_once(self):
        for value in ['','0','-1','999999999','8388609','8M',' 8388608','8388608 ']:
            with self.subTest(value=value):
                s=self.run_case('budget',budget=value).stderr
                self.assertEqual(s,'RPCRETURN_LIMIT seq=0 reason=budget_config\n')

    def test_actual_eight_mib_limit_stops_once_and_keeps_input_ubsan(self):
        r=self.run_case('unused',budget='8388608',binary=self.limit)
        self.assertLessEqual(len(r.stderr.encode()),8388608+100)
        self.assertGreater(len(r.stderr.encode()),8380000)
        self.assertEqual(r.stderr.count('RPCRETURN_LIMIT'),1)
        self.assertTrue(r.stderr.splitlines()[-1].endswith('reason=budget'))
        self.assertNotIn('runtime error',r.stderr)

    def test_opt_in_disabled_ignores_budget_and_never_logs(self):
        for value in [None,'0','yes','']:
            self.assertEqual(self.run_case(budget='garbage',opt=value).stderr,'')

    def test_large_profile_keeps_frame_and_transport_error_behavior(self):
        for case in ['normal','large','transport-error','frame-limit','null-frame']:
            self.assertEqual(self.run_case(case,budget='8388608').stderr,self.run_case(case,binary=self.old).stderr)

    def test_existing_or_inside_source_output_refused(self):
        for output in [self.root/'profile',self.source/'forbidden-profile']:
            with self.assertRaises(ValueError):P.prepare(self.source,output)

    def test_actual_localctl_sns_registry_negative_shape_ubsan(self):
        r=self.run_case('sns_registry',binary=self.localctl)
        d=json.loads(r.stdout);self.assertEqual((d['status'],d['handle'],d['error']),(0xfffffffb,0,0xfffffffb))
        self.assertEqual((d['unsupported_status'],d['fatal'],d['unsupported_encoded_bytes']),(20,0,0))
        self.assertTrue(d['text_zeroed']);self.assertNotIn('runtime error',r.stderr)

    def test_actual_registered_interface_open_succeeds(self):
        d=json.loads(self.run_case('apps_std',binary=self.localctl).stdout)
        self.assertEqual((d['status'],d['handle'],d['error']),(0,1,0))

    def test_other_missing_interface_same_driver_error_is_not_qualified_by_name(self):
        d=json.loads(self.run_case('other',binary=self.localctl).stdout)
        self.assertEqual(d['status'],0xfffffffb)


def pair():
    first=dict(sequence=5,response_to=dict(N.REGISTRY_REQUEST,rctx=11),
        status=0xfffffffb,transport_return=0,
        returned_buffers_hex=[struct.pack('<II',0,0xfffffffb).hex(),(b'\0'*255).hex()])
    second=dict(sequence=6,response_to=dict(N.PROPERTY_REQUEST,rctx=12),
        status=20,transport_return=0,returned_buffers_hex=[],error_output_omitted=True)
    return first,second


class ProtocolEvidenceTests(unittest.TestCase):
    def classify(self,calls=None):
        return N.classify(dict(streams=[dict(unit=N.UNIT,pid='17',calls=list(pair()) if calls is None else calls)]))

    def test_exact_acknowledged_pair_reported_as_negative_not_interface_success(self):
        d=self.classify();self.assertTrue(d['complete']);self.assertEqual(len(d['known_negative_replies']),2)
        self.assertFalse(d['interface_implemented']);self.assertFalse(d['SSC_publication_proved'])

    def test_wrong_status_payload_capacity_name_transport_or_pair_order_rejected(self):
        for case in ['status','payload','capacity','transport','order','missing-property']:
            a,b=pair()
            if case=='status':a['status']=0
            if case=='payload':a['returned_buffers_hex'][0]='0'*16
            if case=='capacity':a['response_to']['output_capacities']=[8,256]
            if case=='transport':a['transport_return']=-1
            if case=='order':b['sequence']=7
            d=self.classify([a]if case=='missing-property'else[a,b])
            self.assertFalse(d['complete'],case)

    def test_more_than_registered_six_probes_rejected(self):
        calls=[]
        for i in range(7):
            a,b=pair();a['sequence']=i*2;b['sequence']=i*2+1;calls.extend([a,b])
        self.assertFalse(self.classify(calls)['complete'])

    def test_current401_error_frame_decoded_without_invented_property_outputs(self):
        r=ROOT/'reference/boot-tests/test-401-fedora-mtime-cache/runtime-discovery'
        d=E.inspect((r/'discovery-unit-journal.txt').read_text(),json.loads((r/'registry-before.json').read_text())['boot_id'])
        self.assertFalse(d['complete']) # Existing budget LIMIT remains fatal.
        self.assertTrue(any(f['reason']=='observer limit/error'for f in d['faults']))
        self.assertFalse(any(f['reason']=='missing buffer header'for f in d['faults']))
        found=[c for s in d['streams']for c in s['calls']if c.get('error_output_omitted')]
        self.assertTrue(found);self.assertTrue(all(c['returned_buffers_hex']==[]for c in found))
        self.assertGreater(sum(len(s['calls'])for s in d['streams']),1026)

    def test_known_zero_error_is_exactly_ro_revision_not_arbitrary_missing_output(self):
        r=ROOT/'reference/boot-tests/test-401-fedora-mtime-cache/runtime-discovery'
        raw=(r/'discovery-unit-journal.txt').read_text();boot=json.loads((r/'registry-before.json').read_text())['boot_id']
        for old,new in [('726f2e7265766973696f6e00','786f2e7265766973696f6e00'),
                        ('sc=00020100 status=20 bytes=0','sc=00020100 status=14 bytes=0')]:
            d=E.inspect(raw.replace(old,new),boot)
            self.assertTrue(any(f['reason']=='missing buffer header'for f in d['faults']))

    def test_frozen400_frames_still_decode_identically(self):
        r=ROOT/'reference/boot-tests/test-400-fedora-adsp-comparison/runtime-discovery'
        raw=(r/'discovery-unit-journal.txt').read_text();boot=json.loads((r/'summary.json').read_text())['boot_id']
        old=fixture.E.RETURN.inspect(raw,boot);new=E.inspect(raw,boot)
        self.assertTrue(new['complete'],new['faults'])
        for s in new['streams']:
            for c in s['calls']:c.pop('error_output_omitted')
            if s['pending_final_call']:s['pending_final_call'].pop('error_output_omitted')
        self.assertEqual(old,new)

    def test_exact_snapshot_temporary_then_rename_allowed_in_disposable_copy(self):
        before={'registry/group':b'old','sns_reg.conf':b'version=6\n'}
        after={'registry/group':b'new','sns_reg.conf':b'version=6\n'}
        path=fixture.V+'../temp.json'
        calls=[fixture.opened(path,'w'),fixture.write(b'new'),fixture.close(),fixture.rename(path,fixture.V+'group')]
        d=M.replay(fixture.frames(calls),fixture.BOOT,fixture.snapshot(before),fixture.snapshot(after,'after'),fixture.manifest(before))
        self.assertTrue(d['complete'],d['faults'])
        self.assertFalse(d['physical_persist_accessed'])

    def test_other_root_temp_config_identity_or_library_writes_still_forbidden(self):
        for name in ['other.json','config/file.json','../socinfo/platform_version','dsp/lib.so']:
            path='/mnt/vendor/persist/sensors/registry/../'+name
            before={'registry/group':b'old'}
            d=M.replay(fixture.frames([fixture.opened(path,'w')]),fixture.BOOT,fixture.snapshot(before),fixture.snapshot(before,'after'),fixture.manifest(before))
            self.assertFalse(d['complete'],name)

    def test_isolated_replay_changes_only_parser_and_one_known_temp_leaf(self):
        old=(BASE/'registry_mutation_evidence.py').read_text()
        expected=old.replace('rpc_return_evidence.py','rpc_return_error_evidence.py').replace(
            "return name == 'sns_reg_version'", "return name in ('sns_reg_version', 'temp.json')")
        self.assertEqual((BASE/'registry_init_evidence.py').read_text(),expected)


class InitMutationRegressionTests(fixture.RegistryMutationTests):
    """Run the unchanged existing safety cases against the independent profile."""
    def setUp(self):
        p=patch.object(fixture,'E',M);p.start();self.addCleanup(p.stop)


if __name__=='__main__':unittest.main()
