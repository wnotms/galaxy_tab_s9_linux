"""Execute one-call C observer, owned lifetime, strict cache and isolated builder."""
import ctypes
import errno
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import test_sm5440_fresh_observer as legacy
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'kernel/diagnostics/sm5440-passive-observer/sm5440-passive-observer.c'
spec = importlib.util.spec_from_file_location('passive291_gate', ROOT / 'reference/boot-tests/test-291-passive-observer-offline/observation_gate.py')
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)


class PassiveObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.tmp.cleanup)
        src = SOURCE.read_text(); header = (ROOT / 'kernel/drivers/sm5440-hw.h').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;typedef uint32_t u32;
#define SM5440_PASSIVE_OBSERVATION_MS 500U
static int kind,locked,errors,result_lock;static unsigned int calls;
static u64 clock_ms;
static u64 ktime_get_boottime(void) {return clock_ms;}
#define ktime_to_ms(x) (x)
static void mutex_lock(int *m) {(void)m;locked++;}
static void mutex_unlock(int *m) {(void)m;locked--;}
static bool kthread_should_stop(void) {return kind==19;}
'''
        for marker in ('struct sm5440_passive_measurement {', 'struct sm5440_passive_observation {'):
            code += function(header, marker)+';\n'
        code += src[src.index('enum observer_state {'):src.index('static DEFINE_MUTEX')]
        code += r'''
static struct observer_row row;static unsigned int nr_rows;
static enum observer_state state;
static int sm5440_passive_observe(struct sm5440_passive_observation *o) {
 if(locked)errors++;calls++;
 o->request_ms=1001;o->measurement.observed_ms=1005;
 o->completed_ms=1139;o->returned_ms=1140;o->oldest_age_ms=135;
 o->acquisition_seq=11;o->request_epoch=5;
 o->measurement.vbus_uv=5000000;o->measurement.vbat_uv=4000000;
 o->measurement.ibus_ua=0;o->measurement.die_decic=300;o->measurement.online=true;
 clock_ms=1141;
 if(kind>=1 && kind<=5) {
  memset(o,0,sizeof(*o));
  return kind==1?-ETIMEDOUT:kind==2?-EIO:kind==3?-ESHUTDOWN:kind==4?-ENODEV:-EBUSY;
 }
 switch(kind) {
 case 6:clock_ms=1501;break;
 case 7:o->oldest_age_ms=0;break;
 case 8:o->measurement.observed_ms=0;break;
 case 9:o->acquisition_seq=0;break;
 case 10:o->request_ms=999;break;
 case 11:o->completed_ms=1004;break;
 case 12:o->returned_ms=1138;break;
 case 13:o->returned_ms=1142;break;
 case 14:o->measurement.online=false;break;
 case 15:o->measurement.ibus_ua=625;break;
 case 16:o->measurement.vbus_uv=9500001;break;
 case 17:o->measurement.vbat_uv=4300000;break;
 case 18:o->measurement.die_decic=420;break;
 case 21:clock_ms=999;break;
 case 22:o->completed_ms=1499;o->returned_ms=1500;o->oldest_age_ms=495;clock_ms=1500;break;
 case 23:clock_ms=1502;break;
 }
 return 0;
}
'''
        code += function(src, 'static int observer_check(')+'\n'
        code += function(src, 'static int observer_thread(')+'\n'
        code += r'''
int run(int scenario,u64 *out) {
 kind=scenario;calls=nr_rows=0;locked=errors=0;clock_ms=kind==20?0:1000;
 state=OBSERVER_RUNNING;memset(&row,0,sizeof(row));observer_thread(NULL);
 out[0]=calls;out[1]=nr_rows;out[2]=state;out[3]=errors;out[4]=locked;
 out[5]=row.raw.oldest_age_ms;out[6]=row.raw.measurement.ibus_ua;
 out[7]=row.raw.acquisition_seq;out[8]=row.raw.request_epoch;
 return nr_rows?row.status:0;
}
int null_check(void) {return observer_check(1000,1141,0,NULL);}
'''
        cfile = Path(cls.tmp.name)/'observer.c'; cfile.write_text(code); so = cfile.with_suffix('.so')
        built = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                '-Wno-misleading-indentation', '-Wno-unused-parameter',
                                '-shared', '-fPIC', str(cfile), '-o', str(so)], capture_output=True)
        if built.returncode:raise AssertionError(built.stderr.decode())
        cls.lib = ctypes.CDLL(str(so)); cls.lib.run.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]

    def run_case(self, kind=0):
        values = (ctypes.c_uint64*9)(); ret = self.lib.run(kind, values)
        self.assertEqual(list(values)[3:5], [0,0], 'no lock across request; released')
        return ret, list(values)

    def test_one_slow_diagnostic_preserves_age_sequence_epoch(self):
        ret, facts = self.run_case(); self.assertEqual(ret,0)
        self.assertEqual(facts, [1,1,1,0,0,135,0,11,5])

    def test_first_provider_failure_stops_without_retry(self):
        for kind, error in [(1,errno.ETIMEDOUT),(2,errno.EIO),(3,errno.ESHUTDOWN),
                            (4,errno.ENODEV),(5,errno.EBUSY)]:
            ret, facts = self.run_case(kind); self.assertEqual(ret,-error)
            self.assertEqual(facts[:3],[1,1,2]);self.assertEqual(facts[5:],[0,0,0,0])

    def test_caller_late_zero_or_reversed_time_refused(self):
        for kind in (6,20,21,23):self.assertEqual(self.run_case(kind)[0],-errno.ETIMEDOUT)
        self.assertEqual(self.run_case(22)[0],0)

    def test_null_or_corrupt_provenance_refused(self):
        self.assertEqual(self.lib.null_check(),-errno.EINVAL)
        for kind in range(7,14):self.assertEqual(self.run_case(kind)[0],-errno.ESTALE)

    def test_online_current_voltage_temperature_bounds(self):
        for kind, error in [(14,errno.ENODATA),(15,errno.EBUSY),(16,errno.ERANGE),
                            (17,errno.ERANGE),(18,errno.ERANGE)]:
            ret,facts=self.run_case(kind);self.assertEqual(ret,-error);self.assertEqual(facts[:3],[1,1,2])
        self.assertEqual(self.run_case(15)[1][6],625, 'failed raw current retained')

    def test_unload_before_call_cancels_without_request(self):
        ret,facts=self.run_case(19);self.assertEqual(ret,0);self.assertEqual(facts[:3],[0,0,3])

    def test_no_hw_policy_loop_or_read_activation(self):
        src=SOURCE.read_text();show=function(src,'static int observer_result_show(')
        self.assertNotIn('sm5440_passive_observe',show)
        for token in ('regmap_', 'i2c_', 'power_supply_set_property', 'module_param',
                      'sm5714_battery_', 'msleep', 'for (', 'debugfs_create_file_unsafe'):
            self.assertNotIn(token,src)
        self.assertEqual(src.count('sm5440_passive_observe(&result.raw)'),1)
        self.assertIn('legacy_fresh_authorized=0',show)
        self.assertIn('debugfs_create_file("result", 0400',src)


class PassiveTaskLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        old=legacy.SOURCE
        try:
            legacy.SOURCE=SOURCE
            legacy.ObserverTaskLifetimeTests.setUpClass()
        finally:legacy.SOURCE=old
        cls.lib=legacy.ObserverTaskLifetimeTests.lib
        cls.addClassCleanup(legacy.ObserverTaskLifetimeTests.tmp.cleanup)

    def run_case(self, fail=0, immediate=0, old=0):
        out=(ctypes.c_int*8)();ret=self.lib.lifecycle(fail,immediate,old,out);return ret,list(out)

    def test_owned_fast_return_and_running_join(self):
        self.assertEqual(self.run_case(immediate=1),(0,[0,1,0,1,1,1,1,0]))
        self.assertEqual(self.run_case(),(0,[0,2,0,1,1,1,1,0]))

    def test_creation_failures_do_not_join_or_leak(self):
        for fail,error,removed in [(1,errno.ENOMEM,0),(2,errno.ENOMEM,0),(3,errno.EINVAL,1),(4,errno.ENOMEM,1)]:
            self.assertEqual(self.run_case(fail=fail),(-error,[0,0,0,0,removed,0,0,0]))

    def test_unowned_negative_control_still_detects_uaf(self):
        ret,out=self.run_case(immediate=1,old=1);self.assertEqual(ret,0);self.assertGreater(out[0],0)


class PassiveCacheGateTests(unittest.TestCase):
    def raw(self, changes=None, header=None):
        row=dict(row=1,request_ms=1000,return_ms=1141,provider_status=0,status=0,
                 diagnostic_valid=1,provider_request_ms=1001,acquisition_ms=1005,
                 completed_ms=1139,provider_return_ms=1140,oldest_age_ms=135,
                 acquisition_seq=11,request_epoch=5,raw_vbus_uv=5000000,
                 raw_vbat_uv=4000000,raw_ibus_ua=0,raw_die_decic=300,raw_online=1)
        row.update(changes or {});h=dict(gate.HEADER,state='1',count='1');h.update(header or {})
        return '\n'.join(f'{k}={v}' for k,v in h.items())+'\n'+' '.join(f'{k}={v}' for k,v in row.items())+'\n'

    def test_valid_slow_age_never_grants_fresh_or_charging(self):
        d=gate.observation(self.raw());self.assertEqual(d['outcome'],'PASSIVE_OBSERVATION_VALID')
        self.assertEqual(d['consumer_oldest_age_ms'],136);self.assertEqual(d['provider_oldest_age_ms'],135)
        self.assertIsNone(d['ADC_duration_ms']);self.assertFalse(d['charging_authorized']);self.assertFalse(d['legacy_fresh_accepted'])

    def test_refusal_retains_one_call_with_zero_provider_output(self):
        zero={k:0 for k in gate.PROVIDER_FIELDS};zero.update(provider_status=-110,status=-110,diagnostic_valid=0,return_ms=1501)
        d=gate.observation(self.raw(zero,{'state':'2'}));self.assertEqual(d['outcome'],'PASSIVE_OBSERVATION_REFUSED')
        self.assertEqual(d['count'],1);self.assertEqual(d['delivery_ms'],501)

    def test_provider_failure_cannot_hide_raw_stale_or_status(self):
        for changes in [{'provider_status':-5,'status':0},{'provider_status':-5,'status':-5,'diagnostic_valid':0}]:
            with self.assertRaises(ValueError):gate.observation(self.raw(changes,{'state':'2'}))

    def test_wrong_contract_schema_duplicates_and_extra_calls(self):
        for text in [self.raw(header={'legacy_fresh_authorized':'1'}),self.raw(header={'count':'2'}),
                     self.raw()+'count=1\n',self.raw()+'unknown=1\n',self.raw()+'row=2\n',self.raw().replace('oldest_age_ms=135','request_ms=135')]:
            with self.assertRaises(ValueError):gate.observation(text)

    def test_provenance_age_deadline_sequence_and_range_refusals(self):
        for key,value in [('provider_request_ms',999),('acquisition_ms',0),('completed_ms',1004),
                          ('provider_return_ms',1142),('oldest_age_ms',0),('acquisition_seq',0),
                          ('return_ms',1501),('raw_online',0),('raw_ibus_ua',1),('raw_vbus_uv',9500001),
                          ('raw_vbat_uv',4300000),('raw_die_decic',420),('request_epoch',2**64)]:
            with self.subTest(key=key),self.assertRaises(ValueError):gate.observation(self.raw({key:value}))

    def test_pending_and_cancelled_are_incomplete_not_success(self):
        for state in ('0','3'):
            raw='\n'.join(f'{k}={v}' for k,v in dict(gate.HEADER,state=state,count='0').items())+'\n'
            self.assertEqual(gate.observation(raw)['outcome'],'INCOMPLETE')


class PassiveObserverBuilderTests(unittest.TestCase):
    def fixture(self, failure=None):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'scripts').mkdir();script=root/'scripts/build-sm5440-passive-observer.sh'
            shutil.copyfile(ROOT/'scripts/build-sm5440-passive-observer.sh',script)
            source=root/'kernel/diagnostics/sm5440-passive-observer';source.mkdir(parents=True)
            for name in ('Makefile','sm5440-passive-observer.c'):shutil.copyfile(SOURCE.parent/name,source/name)
            driver=root/'kernel/drivers';driver.mkdir()
            tree=root/'.work/build/linux-src-x710-charging/drivers/power/supply';tree.mkdir(parents=True)
            for name,content in [('sm5440-direct.c',b'provider'),('sm5440-hw.h',b'header')]:
                (driver/name).write_bytes(b'changed' if failure=='header' and name.endswith('.h') else content)
                (tree/name).write_bytes(b'changed' if failure=='overlay' else (driver/name).read_bytes())
            out=root/'out/kernel-x710-290-passive';out.mkdir(parents=True)
            config=out/'config';config.write_bytes(b'CONFIG_MODULES=y\n');notes=out/'kernel-notes.bin';notes.write_bytes(b'notes')
            image=out/'Image.gz';image.write_bytes(b'image')
            manifest={n:{'path':str(p.relative_to(root)),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()} for n,p in [('config',config),('kernel-notes.bin',notes),('Image.gz',image)]}
            folder=root/'reference/boot-tests/test-290-passive-observation-api';folder.mkdir(parents=True);(folder/'ARTIFACTS.json').write_text(json.dumps(manifest))
            if failure=='image':image.write_bytes(b'wrong image')
            build=root/'.work/build/linux-out-x710-290-passive';build.mkdir();(build/'.config').write_bytes(b'wrong' if failure=='config' else config.read_bytes())
            (build/'Module.symvers').write_text('' if failure=='symbol' else '0x123\tsm5440_passive_observe\tvmlinux\tEXPORT_SYMBOL_GPL\n')
            bin_dir=root/'bin';bin_dir.mkdir()
            (bin_dir/'git').write_text("#!/usr/bin/env python3\nimport sys\nname=sys.argv[-1].split('/')[-1]\nsys.stdout.buffer.write({'sm5440-direct.c':b'provider','sm5440-hw.h':b'header'}[name])\n")
            notevalue="b'wrong'" if failure=='notes' else "b'notes'"
            (bin_dir/'llvm-objcopy').write_text(f"#!/usr/bin/env python3\nimport sys,pathlib\np=pathlib.Path(sys.argv[2].split('=',1)[1]);p.write_bytes({notevalue})\n")
            (bin_dir/'make').write_text('#!/bin/sh\nfor arg in "$@"; do case "$arg" in M=*) target=${arg#M=};; esac; done\nprintf "mock module" > "$target/sm5440-passive-observer.ko"\n')
            for path in bin_dir.iterdir():path.chmod(0o755)
            original=root/'out/sm5440-fresh-observer-276/sm5440-fresh-observer.ko';original.parent.mkdir();original.write_bytes(b'frozen276')
            env=dict(os.environ,PATH=str(bin_dir)+':'+os.environ['PATH']);env['OBSERVER_OUT_DIR']=str(root/'out/new291')
            result=subprocess.run(['bash',str(script)],env=env,capture_output=True,timeout=15)
            self.assertEqual(original.read_bytes(),b'frozen276')
            return result.returncode,result.stderr.decode(),(root/'out/new291/sm5440-passive-observer.ko').exists()

    def test_exact_provider_isolated_output_and_old_observer_retained(self):
        status,error,present=self.fixture();self.assertEqual(status,0,error);self.assertTrue(present)

    def test_wrong_artifact_config_ABI_overlay_notes_or_export_stops(self):
        for failure in ('image','config','header','overlay','notes','symbol'):
            with self.subTest(failure=failure):
                status,error,present=self.fixture(failure);self.assertNotEqual(status,0,error);self.assertFalse(present)


class PassiveCoordinatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import sys
        folder=ROOT/'reference/boot-tests/test-291-passive-observer-offline'
        previous=sys.modules.get('observation_gate')
        sys.modules['observation_gate']=gate
        try:
            spec=importlib.util.spec_from_file_location('passive291_coordinator',folder/'coordinator.py')
            cls.coordinator=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.coordinator)
        finally:
            if previous is None:sys.modules.pop('observation_gate',None)
            else:sys.modules['observation_gate']=previous

    def run_case(self, fault=None):
        raw=PassiveCacheGateTests().raw()
        class Ops:
            loads=unloads=reads=0
            def verified_identity(self):
                if fault=='preflight':raise ValueError('identity')
                return {'boot_id':'boot-A'}
            def boottime_ms(self):return 900 if not self.reads else 1200
            def load(self,timeout):
                self.loads+=1
                if fault=='load':raise TimeoutError('load')
            def cached_result(self):
                self.reads+=1
                if fault=='read':raise OSError('read')
                if fault=='malformed':return 'missing'
                if fault=='refused':
                    zero={k:0 for k in gate.PROVIDER_FIELDS};zero.update(provider_status=-110,status=-110,diagnostic_valid=0)
                    return PassiveCacheGateTests().raw(zero,{'state':'2'})
                if fault=='pending':
                    return '\n'.join(f'{k}={v}' for k,v in dict(gate.HEADER,state=0,count=0).items())+'\n'
                return raw
            def unload(self,timeout):
                self.unloads+=1
                if fault=='unload':raise OSError('unload')
            def boot(self):return 'boot-B' if fault=='boot' else 'boot-A'
        ops=Ops();ticks=[0.0]
        def clock():ticks[0]+=0.5;return ticks[0]
        with tempfile.TemporaryDirectory() as tmp:
            d=self.coordinator.run_once(Path(tmp)/'observation',ops,clock=clock,sleep=lambda _:None)
            self.assertTrue((Path(tmp)/'observation/summary.json').exists())
            return d,ops

    def test_one_success_no_trace_and_healthy_cleanup(self):
        d,o=self.run_case();self.assertEqual(d['verdict'],'PASSIVE_OBSERVATION_VALID')
        self.assertEqual((o.loads,o.unloads,o.reads),(1,1,1));self.assertTrue(d['same_boot_after_unload'])
        self.assertFalse(d['charging_authorized']);self.assertFalse(d['legacy_fresh_accepted'])

    def test_refusal_is_captured_without_retry(self):
        d,o=self.run_case('refused');self.assertEqual(d['verdict'],'PASSIVE_OBSERVATION_REFUSED')
        self.assertEqual((o.loads,o.unloads,o.reads),(1,1,1))

    def test_failed_preflight_never_loads_or_unloads(self):
        d,o=self.run_case('preflight');self.assertEqual(d['verdict'],'STOP_COLLECTION')
        self.assertEqual((o.loads,o.unloads),(0,0))

    def test_partial_load_timeout_gets_owned_cleanup_without_retry(self):
        d,o=self.run_case('load');self.assertEqual(d['verdict'],'STOP_COLLECTION')
        self.assertEqual((o.loads,o.unloads),(1,1))

    def test_read_parse_and_boot_fault_preserve_errors_and_cleanup(self):
        for fault in ('read','malformed','boot'):
            d,o=self.run_case(fault);self.assertEqual(d['verdict'],'STOP_COLLECTION')
            self.assertTrue(d['errors']);self.assertEqual((o.loads,o.unloads),(1,1))

    def test_unload_failure_cannot_be_reported_qualified(self):
        d,o=self.run_case('unload');self.assertEqual(d['verdict'],'STOP_COLLECTION')
        self.assertFalse(d['observer_unloaded']);self.assertEqual(o.unloads,1)

    def test_incomplete_cache_has_bounded_wait_no_reload(self):
        d,o=self.run_case('pending');self.assertEqual(d['verdict'],'STOP_COLLECTION')
        self.assertEqual((o.loads,o.unloads),(1,1));self.assertLessEqual(o.reads,12)

    def test_portable_ops_select_new_namespace_only(self):
        src=(ROOT/'reference/boot-tests/test-291-passive-observer-offline/device_ops.py').read_text()
        self.assertIn("packet['test'] != 'Test292'",src)
        self.assertIn('PROVIDER_NOTES_SHA256',src)
        self.assertIn('/sys/module/sm5440_passive_observer',src)
        self.assertNotIn('TraceFS',src)
        self.assertNotIn('kallsyms',src)


if __name__=='__main__':unittest.main()
