"""Run actual new driver cycle plus unchanged native converter on mocked bus."""
import ctypes,importlib.util,subprocess,unittest
from pathlib import Path
import test_sm5440_conversion as fixture_module
ROOT=Path(__file__).resolve().parents[1]

class OneShotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture_module.ConversionTests.setUpClass();cls.p=Path(fixture_module.ConversionTests.tmp.name)
        text=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        start=text.index('static void sm5440_oneshot_cycle(');end=text.index('\n#endif',start)
        body=text[start:end]
        mock=(cls.p/'mock.c').read_text().replace('m->enables++;m->enabled_ms=fake_clock;', 'm->enables++;m->enabled_ms=fake_clock;m->ready_sent=0;')
        mock += r'''
#include <stdlib.h>
#include <linux/errno.h>
#include "sm5440-oneshot.h"
#define GFP_KERNEL 0
#define READ_ONCE(v) (v)
struct sm5440_direct {struct regmap *regmap;int io_lock,stopped,fault;void *dev;struct sm5440_oneshot_context oneshot;};
static int test_case,facts_calls,off_calls;
static struct sm5440_direct *active;
static int lock_depth;
static void mutex_lock(int *p){(void)p;if(lock_depth)abort();lock_depth++;}
static void mutex_unlock(int *p){(void)p;if(lock_depth!=1)abort();lock_depth--;}
static void *kzalloc(size_t n,int flags){(void)flags;if(lock_depth)abort();return test_case==1?NULL:calloc(1,n);}
static void kfree(void *p){free(p);}
#define dev_err(...) ((void)0)
static void msleep(int ms){if(lock_depth)abort();fake_clock+=ms;if(test_case==5 && active->regmap->enables)active->stopped=1;}
static int sm5440_off(struct sm5440_direct *sm){off_calls++;return sm->regmap->reg[0x10]==1?0:-5;}
static int sm5440_adc_rearm(struct sm5440_direct *sm){(void)sm;if(lock_depth)abort();fake_clock+=50;return test_case==8?-5:0;}
static bool sm5440_timing_same_source(const struct sm5714_pd_snapshot *a,const struct sm5714_pd_snapshot *b){return a->instance==b->instance && a->source_generation==b->source_generation && a->budget_generation==b->budget_generation && a->budget_ma==b->budget_ma && a->budget_mv==b->budget_mv;}
static int sm5440_timing_facts(struct sm5714_pd_snapshot *s,struct sm5714_pack_snapshot *p){
 if(lock_depth)abort();facts_calls++;
 if(test_case==2)return -1;
 if(test_case==3 && facts_calls<=2)return -11;
 if(test_case==4)return -16;
 *s=(struct sm5714_pd_snapshot){.instance=1,.source_generation=2,.budget_generation=3,.budget_mv=9000,.budget_ma=1500};
 *p=(struct sm5714_pack_snapshot){.instance=4,.state_generation=5,.voltage_uv=3800000,.current_ua=500000,.pack_decic=300,.started_ms=fake_clock,.completed_ms=fake_clock};
 if(test_case==6 && facts_calls==3)s->source_generation++;
 if(test_case==7 && facts_calls==3)p->state_generation++;
 return 0;
}
'''+body+r'''
void oneshot_case(int scenario,int fail,int *out){
 struct regmap m={0};struct sm5440_direct sm={.regmap=&m};
 active=&sm;test_case=scenario;facts_calls=off_calls=lock_depth=0;fake_clock=1000;generation=1;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x1c]=0x0c;m.reg[0x1d]=0xdf;
 raw13(m.reg+0x1e,4904);raw13(m.reg+0x27,3504);m.reg[0x26]=15;
 m.fail=fail;m.disabled_ms=1000;
 if(scenario==9)m.scenario=7;
 if(scenario==10)m.scenario=100;
 if(scenario==11)raw13(m.reg+0x22,1);
 if(scenario==12)m.step=3;
 sm5440_oneshot_cycle(&sm);
 out[0]=sm.oneshot.error;out[1]=sm.oneshot.count;out[2]=sm.oneshot.finished;out[3]=sm.oneshot.attempted;
 out[4]=sm.oneshot.cleanup_error;out[5]=sm.oneshot.off_error;out[6]=sm.fault;out[7]=m.enables;
 out[8]=m.unsafe;out[9]=m.reg[0x10];out[10]=m.reg[0x1c];out[11]=m.reg[0x1d];
 out[12]=off_calls;out[13]=facts_calls;out[14]=lock_depth;
 out[15]=0;
 for(int i=0;i<4;i++){if(sm.oneshot.sample[i].adc.generation)out[15]++;
 out[16+i]=sm.oneshot.sample[i].adc.sample.valid;
 out[20+i]=sm.oneshot.sample[i].adc.completed_ms-sm.oneshot.sample[i].adc.requested_ms;}
 out[24]=sm.oneshot.readiness_checks;
}
'''
        (cls.p/'oneshot.c').write_text(mock)
        cmd=['cc','-shared','-fPIC','-std=c11','-D__KERNEL__','-Wall','-Wextra','-Werror','-Wno-misleading-indentation','-I'+str(cls.p),'-I'+str(ROOT/'kernel/drivers'),str(ROOT/'kernel/drivers/sm5440-conversion.c'),str(cls.p/'oneshot.c'),'-o',str(cls.p/'oneshot.so')]
        run=subprocess.run(cmd,capture_output=True,text=True)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        cls.lib=ctypes.CDLL(str(cls.p/'oneshot.so'));cls.lib.oneshot_case.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
    @classmethod
    def tearDownClass(cls):fixture_module.ConversionTests.tearDownClass()
    def case(self,scenario=0,fail=0):
        out=(ctypes.c_int*25)();self.lib.oneshot_case(scenario,fail,out)
        self.assertEqual(list(out)[8:10],[0,1])
        self.assertEqual(out[11],223)
        if out[4]:
            self.assertLess(out[0],0)
            self.assertEqual(out[6:8],[1,1])
            self.assertEqual(out[12],1)
            self.assertEqual(out[16],0)
        else:
            self.assertEqual(out[10],12)
        self.assertEqual(out[14:16],[0,0]);return list(out)
    def test_four_actual_native_conversions(self):
        o=self.case();self.assertEqual(o[:8],[0,4,1,1,0,0,0,4]);self.assertEqual(o[16:20],[1]*4);self.assertTrue(all(0<t<=100 for t in o[20:24]))
    def test_heap_failure_no_io(self):
        o=self.case(1);self.assertEqual(o[:4],[-12,0,1,1]);self.assertEqual(o[7],0)
    def test_not_ready_bounded_then_success(self):
        o=self.case(3);self.assertEqual(o[0],0);self.assertEqual(o[24],3)
    def test_not_ready_refuses_after_bound(self):
        o=self.case(4);self.assertEqual(o[0],-16);self.assertEqual(o[24],20);self.assertEqual(o[7],0)
    def test_invalid_pack_no_enable(self):self.assertEqual(self.case(2)[7],0)
    def test_suspend_during_wait(self):
        o=self.case(5);self.assertEqual(o[0],-125);self.assertEqual(o[1],0);self.assertEqual(o[12],1)
    def test_changed_source_pack_no_second_request(self):
        for scenario in [6,7]:
            with self.subTest(scenario=scenario):o=self.case(scenario);self.assertEqual(o[0],-116);self.assertEqual(o[1],0);self.assertEqual(o[7],1)
    def test_no_ready_no_retry(self):
        o=self.case(9);self.assertEqual(o[0],-110);self.assertEqual(o[7],1)
    def test_fault_no_retry(self):
        o=self.case(10);self.assertEqual(o[0],-5);self.assertEqual(o[7],1)
    def test_nonzero_off_current_refused(self):
        o=self.case(11);self.assertEqual(o[0],-34);self.assertEqual(o[1],0)
    def test_bus_time_does_not_relax100ms(self):self.assertLess(self.case(12)[0],0)
    def test_failed_rearm_no_conversion(self):self.assertEqual(self.case(8)[7],0)
    def test_i2c_failure_cleanup(self):
        for fail in range(1,60):
            with self.subTest(fail=fail):o=self.case(fail=fail);self.assertLess(o[0],0);self.assertEqual(o[1],0)
    def test_profile_only_enabled_in_diagnostic(self):
        spec=importlib.util.spec_from_file_location('oneshot_config_gate',ROOT/'scripts/verify-x710-charging-profile.py');g=importlib.util.module_from_spec(spec);spec.loader.exec_module(g)
        base=(ROOT/'out/kernel-x710-pc-ordinary/config').read_text()
        config=base+'\nCONFIG_SM5440_ADC_ONESHOT_TEST=y\n'
        self.assertTrue(g.verify(config,profile='sm5440-adc-oneshot')['valid'])
        self.assertFalse(g.verify(config,profile='sm5440-passive')['valid'])
        self.assertFalse(g.verify(config+'\nCONFIG_X710_NATIVE_CONTROL=y\n',profile='sm5440-adc-oneshot')['valid'])
    def test_production_and_converter_unchanged(self):
        import hashlib,json
        freeze=json.loads((ROOT/'reference/charging/sm5440-native-oneshot/inputs-before.json').read_text())
        for name in ['kernel/drivers/sm5440-conversion.c','kernel/drivers/sm5714-battery.c','kernel/drivers/sm5714_usbpd.c']:
            self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),freeze['protected_sources'][name])

if __name__=='__main__':unittest.main()
