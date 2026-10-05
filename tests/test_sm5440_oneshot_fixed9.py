"""Compile real startup predicates in ordinary and isolated fixed9V profiles."""
import ctypes
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]

class Fixed9StartupTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = (ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        code = '''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
''' + '\n#include "'+str(ROOT/'kernel/drivers/sm5440-hw.h')+'"\n'
        code += function(source, 'struct sm5440_sample {')+';\n'
        code += function(source, 'static bool sm5440_passive_pc_sample(')+'\n'
        code += '#ifdef CONFIG_SM5440_ADC_ONESHOT_TEST\n'+function(source, 'static bool sm5440_passive_fixed9_sample(')+'\n#endif\n'
        code += function(source, 'static bool sm5440_startup_revblk(')+'\n'
        code += function(source, 'static bool sm5440_startup_matches(')+'\n'
        code += '#ifdef CONFIG_SM5440_ADC_ONESHOT_TEST\n'+function(source, 'static bool sm5440_oneshot_startup_revblk(')+'\n'+function(source, 'static bool sm5440_oneshot_startup_matches(')+'\n#endif\n'
        code += '''
static void populate(struct sm5440_sample *s, const int *v) {
 memset(s,0,sizeof(*s));
 s->vbus_uv=v[0];s->vbat_uv=v[1];s->ibus_ua=v[2];s->die_decic=v[3];
 s->mode_before=v[4];s->mode_after=v[5];s->int4_wait=v[6];s->online=v[7];
 s->faults=v[8];s->int_before[2]=v[9];s->status[2]=v[10];
 s->cntl2=v[11];s->vbuscntl=v[12];s->vbatcntl=v[13];s->prtncntl=v[14];
}
int evaluate(const int *a,const int *b) {
 struct sm5440_sample initial,sample;populate(&initial,a);populate(&sample,b);
 bool latch=sm5440_startup_revblk(&initial);
 bool clean=sm5440_startup_matches(&sample,&initial);
#ifdef CONFIG_SM5440_ADC_ONESHOT_TEST
 latch |= sm5440_oneshot_startup_revblk(&initial);
 clean = sm5440_oneshot_startup_matches(&sample,&initial);
#endif
 return latch | (clean<<1);
}
'''
        c=Path(cls.tmp.name)/'startup.c';c.write_text(code)
        cls.libs=[]
        for diagnostic in [False,True]:
            lib=c.with_name('fixed9.so' if diagnostic else 'ordinary.so')
            args=['cc','-shared','-fPIC','-Wall','-Werror']
            if diagnostic:args+=['-DCONFIG_SM5440_ADC_ONESHOT_TEST']
            subprocess.run(args+[str(c),'-o',str(lib)],check=True)
            dll=ctypes.CDLL(str(lib));dll.evaluate.argtypes=[ctypes.POINTER(ctypes.c_int)]*2
            cls.libs.append(dll)

    def initial(self, uv=9400000):
        # Actual Test324 OFF latch and unchanged control bytes, not a pump grant.
        return [uv,4009000,0,300,1,1,1,1,128,0x62,0x20,0xf2,0xe7,0x37,0xfe]
    def clean(self, uv=9400000):
        v=self.initial(uv);v[8]=0;v[9]=0x20;return v
    def evaluate(self,a,b,diagnostic=True):
        return self.libs[int(diagnostic)].evaluate((ctypes.c_int*15)(*a),(ctypes.c_int*15)(*b))
    def test_captured_fixed9_context_only_admitted_by_diagnostic(self):
        self.assertEqual(self.evaluate(self.initial(),self.clean()),3)
        self.assertEqual(self.evaluate(self.initial(),self.clean(),False),0)
    def test_pc_behavior_unchanged_in_both_profiles(self):
        for uv in [4500000,5000000,5500000]:
            for diagnostic in [False,True]:
                self.assertEqual(self.evaluate(self.initial(uv),self.clean(uv),diagnostic),3)
    def test_fixed9_boundaries_and_no_unapproved_voltage(self):
        for uv in [8500000,9000000,9500000]:
            self.assertEqual(self.evaluate(self.initial(uv),self.clean(uv)),3)
        for uv in [5500001,8499999,9500001,12000000,20000000]:
            self.assertEqual(self.evaluate(self.initial(uv),self.clean(uv)),0)
    def test_confirmations_cannot_cross_voltage_classes(self):
        self.assertEqual(self.evaluate(self.initial(),self.clean(5000000)),1)
        self.assertEqual(self.evaluate(self.initial(5000000),self.clean()),1)
    def test_off_ready_online_zero_current_temperature_pack_required(self):
        bad={1:[3499999,4300000],2:[1,-1],3:[224,420],4:[0x05,0x09],5:[0x05,0x09],6:[0],7:[0]}
        for field,values in bad.items():
            for value in values:
                with self.subTest(field=field,value=value):
                    a=self.initial();a[field]=value
                    self.assertEqual(self.evaluate(a,self.clean())&1,0)
                    b=self.clean();b[field]=value
                    self.assertEqual(self.evaluate(self.initial(),b)&2,0)
    def test_only_initial_inactive_revblk_latch_can_be_classified(self):
        for field,value in [(8,0),(8,129),(9,0x20),(9,0x63),(10,0x22),(10,0x21)]:
            a=self.initial();a[field]=value
            self.assertEqual(self.evaluate(a,self.clean())&1,0)
    def test_repeated_decoded_fault_never_confirms(self):
        for fault in [1,2,4,8,16,32,64,128,256,512]:
            b=self.clean();b[8]=fault
            self.assertEqual(self.evaluate(self.initial(),b),1)
    def test_any_control_drift_refuses_confirmation(self):
        for field in range(11,15):
            b=self.clean();b[field]^=1
            self.assertEqual(self.evaluate(self.initial(),b),1)
    def test_existing_worker_still_requires_two_new_confirmations(self):
        poll=function((ROOT/'kernel/drivers/sm5440-direct.c').read_text(),'static void sm5440_poll(')
        self.assertIn('startup_confirmations = 2',poll)
        self.assertIn('msecs_to_jiffies(5000)',poll)
        self.assertIn('sm5440_startup_matches(&sample, &sm->startup_sample)',poll)
        self.assertIn('sm->startup_confirmations--;',poll)
        self.assertIn('if (!sm->startup_confirmations)',poll)

if __name__ == '__main__':unittest.main()
