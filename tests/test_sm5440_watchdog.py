"""Compile/execute the new register helper; no live caller, pump or deployment."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class WatchdogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name);(p/'linux').mkdir()
        headers={
            'types.h':'#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n',
            'bitops.h':'#define BIT(n) (1U << (n))\n#define GENMASK(h,l) (((~0U) >> (31-(h))) & ((~0U) << (l)))\n',
            'errno.h':'#define EIO 5\n#define EPERM 1\n#define EBUSY 16\n#define ENODEV 19\n#define EINVAL 22\n#define ENOLINK 67\n#define ETIMEDOUT 110\n#define EALREADY 114\n#define ECANCELED 125\n',
            'regmap.h':'struct regmap;\nint regmap_read(struct regmap *,unsigned int,unsigned int *);\nint regmap_write(struct regmap *,unsigned int,unsigned int);\nint regmap_bulk_read(struct regmap *,unsigned int,void *,unsigned int);\n'}
        for name,data in headers.items():(p/'linux'/name).write_text(data)
        harness=r'''
#include <string.h>
#include "sm5440-watchdog.h"
#include "sm5440-hw.h"
struct regmap {u8 reg[256];int calls,writes,fail,persistent,uncertain,drop,unsafe,phase;};
static int bad(struct regmap *m) {m->calls++;return m->fail && (m->calls==m->fail || (m->persistent && m->calls>=m->fail));}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v) {
 if(bad(m))return -5;*v=m->reg[r];return 0;
}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *p,unsigned int n) {
 if(r!=8 || n!=4)m->unsafe++;if(bad(m))return -5;memcpy(p,m->reg+r,n);return 0;
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int v) {
 int b=bad(m);m->writes++;
 if(r!=0x0c || v&1 || ((v^m->reg[r])&15))m->unsafe++;
 if((!b || m->uncertain) && m->calls!=m->drop)m->reg[r]=v;
 if(m->phase==10)m->reg[0x10]=1;
 return b?-5:0;
}
void exercise(int scenario,int fail,int persistent,int uncertain,int drop,int *o) {
 struct regmap m={0};struct sm5440_watchdog w={0};
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x22;
 if(scenario==1)m.reg[0x2b]=0x22;
 if(scenario==2)m.reg[0x10]=5;
 if(scenario==3)m.reg[0x0a]|=2;
 if(scenario==4)m.reg[0x0a]=0;
 if(scenario==5)m.reg[0x0c]|=128;
 if(scenario==6)m.reg[0x0c]|=1;
 m.fail=fail;m.persistent=persistent;m.uncertain=uncertain;m.drop=drop;
 o[0]=sm5440_watchdog_arm_off(&m,&w,1,100);
 o[1]=m.reg[0x0c];o[2]=w.state;o[3]=w.owned;o[4]=w.operation_error;o[5]=w.restore_error;
 o[6]=m.calls;o[7]=m.writes;
 o[8]=sm5440_watchdog_arm_off(&m,&w,1,100);o[9]=m.calls;
 if(o[0])goto end;
 m.reg[0x10]=5; /* Test bus emulates an external pump mode, helper never writes it. */
 if(scenario==7)m.reg[0x0a]|=2;
 if(scenario==8)m.reg[0x0c]^=2;
 if(scenario==9)m.reg[0x0c]&=~128;
 if(scenario==10)m.phase=10;
 o[10]=sm5440_watchdog_service(&m,&w,scenario==11?2:1,scenario==12?1101:scenario==13?99:200);
 o[11]=m.calls;o[12]=m.writes;o[13]=w.operation_error;o[14]=w.state;
 if(scenario==14)m.reg[0x0a]|=64;
 o[15]=sm5440_watchdog_restore_off(&m,&w); /* ON mode must block cleanup writes. */
 o[16]=m.writes;o[17]=w.owned;
 m.phase=0;m.reg[0x10]=1;
 if(scenario==15)m.reg[0x0c]|=1;
 o[18]=sm5440_watchdog_restore_off(&m,&w);
 o[19]=m.reg[0x0c];o[20]=w.owned;o[21]=w.restore_error;o[22]=w.state;o[23]=w.operation_error;
 o[24]=m.calls;o[25]=m.writes;
 o[26]=sm5440_watchdog_service(&m,&w,1,300);o[27]=m.calls;
end:
 o[28]=m.unsafe;
}
int null_args(int n) {struct regmap m={0};struct sm5440_watchdog w={0};
 if(n==0)return sm5440_watchdog_arm_off(0,&w,1,1);
 if(n==1)return sm5440_watchdog_arm_off(&m,0,1,1);
 if(n==2)return sm5440_watchdog_arm_off(&m,&w,0,1);
 if(n==3)return sm5440_watchdog_arm_off(&m,&w,1,0);
 if(n==4)return sm5440_watchdog_service(0,&w,1,1);
 if(n==5)return sm5440_watchdog_service(&m,0,1,1);
 if(n==6)return sm5440_watchdog_restore_off(0,&w);
 return sm5440_watchdog_restore_off(&m,0);
}
'''
        (p/'mock.c').write_text(harness)
        cls.command=['cc','-shared','-fPIC','-std=c11','-D__KERNEL__','-Wall','-Wextra','-Werror',
            '-Wno-misleading-indentation','-I'+str(p),'-I'+str(ROOT/'kernel/drivers'),
            str(ROOT/'kernel/drivers/sm5440-watchdog.c'),str(p/'mock.c'),'-o',str(p/'watchdog.so')]
        c=subprocess.run(cls.command,capture_output=True,text=True)
        if c.returncode:raise AssertionError(c.stdout+c.stderr)
        cls.lib=ctypes.CDLL(str(p/'watchdog.so'))
        cls.lib.exercise.argtypes=[ctypes.c_int]*5+[ctypes.POINTER(ctypes.c_int)]

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def case(self,scenario=0,fail=0,persistent=0,uncertain=0,drop=0):
        out=(ctypes.c_int*29)();self.lib.exercise(scenario,fail,persistent,uncertain,drop,out)
        self.assertEqual(out[28],0,'write outside CNTL1 fields or reset/INT/pump attempt')
        return list(out)

    def test_real_equal_value_refresh_occurs_and_exact_original_restores(self):
        o=self.case();self.assertEqual(o[:6],[0,0xc2,1,1,0,0])
        self.assertEqual(o[10],0);self.assertEqual(o[12],o[7]+1)
        self.assertEqual(o[18:24],[0,0x22,0,0,2,0]);self.assertEqual(o[26],-1)
        self.assertEqual(o[24],o[27])

    def test_second_arm_does_not_touch_bus(self):
        o=self.case();self.assertEqual(o[8],-114);self.assertEqual(o[6],o[9])

    def test_invalid_id_live_fault_running_reset_or_inherited_wdt_refused(self):
        for scenario,ret in [(1,-19),(2,-16),(3,-5),(4,-67),(5,-16),(6,-16)]:
            with self.subTest(scenario=scenario):
                o=self.case(scenario);self.assertEqual(o[0],ret);self.assertEqual(o[7],0)

    def test_live_fault_drift_or_lost_wdt_blocks_service(self):
        for scenario in (7,8,9):
            o=self.case(scenario);self.assertEqual(o[10],-5);self.assertEqual(o[12],o[7]);self.assertEqual(o[14],3)
            self.assertEqual(o[23],-5,'cleanup must retain original service error')

    def test_epoch_deadline_or_clock_regression_has_no_service_io(self):
        for scenario,ret in [(11,-125),(12,-110),(13,-110)]:
            o=self.case(scenario);self.assertEqual(o[10],ret);self.assertEqual(o[11],o[9])
            self.assertEqual(o[12],o[7]);self.assertEqual(o[23],ret)

    def test_running_cleanup_does_not_disable_watchdog(self):
        o=self.case();self.assertEqual(o[15],-16);self.assertEqual(o[16],o[12]);self.assertEqual(o[17],1)

    def test_mode_loss_after_service_is_detected(self):
        o=self.case(10);self.assertEqual(o[10],-16);self.assertEqual(o[14],3)

    def test_cleanup_can_work_with_fault_or_detached_status_when_off(self):
        o=self.case(14);self.assertEqual(o[18],0);self.assertEqual(o[19],0x22)

    def test_unowned_drift_is_preserved_and_uncertainty_retained(self):
        o=self.case(8);self.assertEqual(o[18],-5);self.assertEqual(o[19],0x20)
        self.assertEqual(o[20],1);self.assertEqual(o[21],-5)

    def test_reset_bit_in_cleanup_is_not_rewritten(self):
        o=self.case(15);self.assertEqual(o[18],-16);self.assertEqual(o[25],o[16]);self.assertEqual(o[20],1)

    def test_every_arm_bus_failure_preserves_error_and_no_auto_rearm(self):
        for fail in range(1,self.case()[6]+1):
            for uncertain in (0,1):
                with self.subTest(fail=fail,uncertain=uncertain):
                    o=self.case(fail=fail,uncertain=uncertain)
                    self.assertEqual(o[0],-5);self.assertEqual(o[4],-5);self.assertEqual(o[8],-114)
                    if not o[3]:self.assertEqual(o[1],0x22)

    def test_persistent_bus_failure_cannot_claim_cleanup(self):
        o=self.case(fail=5,persistent=1,uncertain=1)
        self.assertEqual(o[0],-5);self.assertEqual(o[3],1);self.assertEqual(o[5],-5)

    def test_every_service_io_failure_latches_error_and_blocks_further_feed(self):
        clean=self.case()
        for fail in range(clean[9]+1,clean[11]+1):
            for uncertain in (0,1):
                with self.subTest(fail=fail,uncertain=uncertain):
                    o=self.case(fail=fail,uncertain=uncertain)
                    self.assertEqual(o[0],0);self.assertEqual(o[10],-5);self.assertEqual(o[13],-5)
                    self.assertEqual(o[23],-5);self.assertEqual(o[26],-1)

    def test_each_off_cleanup_io_failure_retains_ownership_and_error(self):
        clean=self.case()
        # Initial running cleanup performs one OFF-mode read. Then four OFF
        # cleanup operations: mode, CNTL1, real restoration write, readback.
        for fail in range(clean[11]+2,clean[24]+1):
            with self.subTest(fail=fail):
                o=self.case(fail=fail)
                self.assertEqual(o[0],0);self.assertEqual(o[10],0)
                self.assertEqual(o[18],-5);self.assertEqual(o[20],1);self.assertEqual(o[21],-5)

    def test_ignored_enable_write_caught(self):
        o=self.case(drop=5);self.assertEqual(o[0],-5);self.assertEqual(o[1],0x22)

    def test_null_or_invalid_identity_has_no_authority(self):
        for n in range(8):self.assertEqual(self.lib.null_args(n),-22)

if __name__=='__main__':unittest.main()
