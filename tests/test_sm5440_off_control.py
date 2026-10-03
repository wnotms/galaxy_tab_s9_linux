"""Execute the real OFF-only register transaction against a fault-injected bus."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest
import re

ROOT = Path(__file__).resolve().parents[1]


class OffControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = Path(cls.tmp.name)
        (p / 'linux').mkdir()
        (p / 'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;\n')
        (p / 'linux/bitops.h').write_text('#define BIT(n) (1U << (n))\n#define GENMASK(h,l) (((~0U) >> (31-(h))) & ((~0U) << (l)))\n')
        (p / 'linux/errno.h').write_text('#define EIO 5\n#define EBUSY 16\n#define ENODEV 19\n#define EINVAL 22\n#define ERANGE 34\n#define ENOLINK 67\n#define EALREADY 114\n')
        (p / 'linux/kernel.h').write_text('')
        (p / 'linux/regmap.h').write_text('struct regmap;\nint regmap_read(struct regmap *, unsigned int, unsigned int *);\nint regmap_bulk_read(struct regmap *, unsigned int, void *, unsigned int);\nint regmap_update_bits(struct regmap *, unsigned int, unsigned int, unsigned int);\n')
        harness = r'''
#include <string.h>
#include <limits.h>
#include "sm5440-control.h"
#include "sm5440-hw.h"
struct regmap { unsigned char reg[256], initial[256];
 int calls,updates,fail,drop,uncertain,persistent,inject,unsafe,phase;
 int restore_calls, restore_fail, wrote_mask, injection_done;
};
static int fault(struct regmap *m) {
 m->calls++;
 if(m->phase) m->restore_calls++;
 return (m->fail && (m->calls==m->fail || (m->persistent && m->calls>=m->fail))) ||
        (m->phase && m->restore_fail && m->restore_calls==m->restore_fail);
}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *out) {
 if(fault(m)) return -5;*out=m->reg[r];return 0;
}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *out,unsigned int n) {
 if(r!=SM5440_STATUS1 || n!=4)m->unsafe++;
 if(fault(m))return -5;memcpy(out,m->reg+r,n);return 0;
}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int value) {
 int bad=fault(m);m->updates++;
 if(!((r==0x16 && mask==0x7f)||(r==0x14 && mask==0x3f)||
      (r==0x12 && mask==0x1f)||(r==SM5440_CNTL5 && mask==SM5440_MODE_MASK && !value)))m->unsafe++;
 if(r==SM5440_CNTL5 && (value & SM5440_MODE_MASK))m->unsafe++;
 if(!bad || m->uncertain) {
  if(m->calls!=m->drop)m->reg[r]=(m->reg[r]&~mask)|(value&mask);
  if(r!=SM5440_CNTL5)m->wrote_mask|=1;
  if(!m->injection_done && r!=SM5440_CNTL5 && m->inject) {
   m->injection_done=1;
   if(m->inject==1)m->reg[SM5440_CNTL5]|=4;
   if(m->inject==2)m->reg[SM5440_STATUS1+2]|=2;
   if(m->inject==3)m->reg[SM5440_CNTL2]^=1;
   if(m->inject==4)m->reg[0x16]^=128;
   if(m->inject==5)m->reg[SM5440_STATUS1+2]=0;
  }
 }
 return bad?-5:0;
}
/* out fields include actual bus state and whether any unowned byte changed. */
void exercise(unsigned int ma,int scenario,int fail,int drop,int uncertain,
              int restore_fail,int persistent,int inject,int *o) {
 struct regmap m={0};struct sm5440_control c={0};
 for(int i=0;i<256;i++)m.reg[i]=(i*7+3)&255;
 m.reg[SM5440_DEVICEID]=0x21;m.reg[SM5440_CNTL5]=1;
 memset(m.reg+SM5440_STATUS1,0,4);m.reg[SM5440_STATUS1+2]=32;
 m.reg[0x16]=0xc1;m.reg[0x14]=0x77;m.reg[0x12]=0xf0;
 if(scenario==1)m.reg[SM5440_DEVICEID]=0x22;
 if(scenario==2)m.reg[SM5440_CNTL5]=5;
 if(scenario==3)m.reg[SM5440_STATUS1+2]|=2;
 if(scenario==4)m.reg[SM5440_STATUS1+2]|=64;
 if(scenario==5)m.reg[SM5440_STATUS1+2]=0;
 memcpy(m.initial,m.reg,256);
 m.fail=fail;m.drop=drop;m.uncertain=uncertain;m.persistent=persistent;m.inject=inject;
 int r=sm5440_control_prepare(&m,ma,&c);
 o[0]=r;o[1]=c.operation_error;o[2]=c.restore_error;o[3]=c.pending;
 o[4]=c.state;o[5]=c.off_verified;o[6]=m.calls;o[7]=m.updates;
 o[8]=m.reg[0x16];o[9]=m.reg[0x14];o[10]=m.reg[0x12];o[11]=m.unsafe;
 o[12]=m.reg[SM5440_CNTL5];o[13]=c.attempted;
 o[14]=sm5440_control_prepare(&m,ma,&c); /* no repeated writes */
 o[15]=m.calls;o[16]=c.status_before[2];o[17]=c.status_after[2];
 if(scenario==6 || restore_fail) {
  m.phase=1;m.restore_fail=restore_fail;
  o[18]=sm5440_control_restore(&m,&c);o[19]=c.restore_error;
 }
 o[20]=c.pending;o[21]=c.state;o[22]=c.off_verified;o[23]=m.restore_calls;
 o[24]=m.reg[0x16];o[25]=m.reg[0x14];o[26]=m.reg[0x12];o[27]=m.reg[SM5440_CNTL5];
 o[28]=0;
 for(int i=0;i<256;i++)if(i!=0x16 && i!=0x14 && i!=0x12 && i!=SM5440_CNTL5 && m.reg[i]!=m.initial[i])o[28]++;
 o[29]=m.updates;o[30]=c.witness_valid;
 int before=m.calls;
 o[31]=sm5440_control_restore(&m,&c);o[32]=m.calls-before;
 o[33]=m.reg[SM5440_STATUS1+2];o[34]=m.reg[SM5440_CNTL2];
}
int null_args(int n) {struct sm5440_control c={0};struct regmap m={0};
 if(n==0)return sm5440_control_prepare(0,1800,&c);
 if(n==1)return sm5440_control_prepare(&m,1800,0);
 if(n==2)return sm5440_control_restore(0,&c);
 return sm5440_control_restore(&m,0);
}
'''
        (p / 'mock.c').write_text(harness)
        result = subprocess.run(['cc', '-shared', '-fPIC', '-std=c11', '-D__KERNEL__',
                                 '-Wall', '-Wextra', '-Werror', '-Wno-misleading-indentation',
                                 '-I' + str(p), '-I' + str(ROOT / 'kernel/drivers'),
                                 str(ROOT / 'kernel/drivers/sm5440-control.c'), str(p / 'mock.c'),
                                 '-o', str(p / 'control.so')], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(p / 'control.so'))
        cls.lib.exercise.argtypes = [ctypes.c_uint] + [ctypes.c_int] * 7 + [ctypes.POINTER(ctypes.c_int)]
        cls.lib.null_args.argtypes = [ctypes.c_int]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def case(self, ma=1800, scenario=0, fail=0, drop=0, uncertain=0, restore_fail=0, persistent=0, inject=0):
        out = (ctypes.c_int * 35)()
        self.lib.exercise(ma, scenario, fail, drop, uncertain, restore_fail, persistent, inject, out)
        self.assertEqual(out[11], 0, 'write outside audited fields, INT access or ON attempt')
        return list(out)

    def test_prepare_rounds_down_and_preserves_unowned_bits(self):
        o = self.case(ma=1799)
        self.assertEqual(o[:6], [0, 0, 0, 1, 1, 1])
        self.assertEqual(o[8:11], [0x80 | 35, 0x40 | 51, 0xe0 | 12])
        self.assertEqual(o[12], 1)
        self.assertEqual(o[28], 0)

    def test_vendor_frequency_boundaries(self):
        for ma,code in [(1000,4),(1100,4),(1101,8),(1700,8),(1701,12),(1800,12)]:
            with self.subTest(ma=ma):
                o=self.case(ma=ma);self.assertEqual(o[10],0xe0|code)
                self.assertLessEqual((o[8]&127)*50,ma)

    def test_invalid_current_no_bus_access(self):
        for ma in [0,999,1801,3000,2**32-1]:
            o=self.case(ma=ma);self.assertEqual(o[0],-34);self.assertEqual(o[6:8],[0,0])

    def test_identity_on_mode_live_fault_uvlo_and_unplug_refused_without_writes(self):
        for scenario,ret in [(1,-19),(2,-16),(3,-5),(4,-5),(5,-67)]:
            with self.subTest(scenario=scenario):
                o=self.case(scenario=scenario);self.assertEqual(o[0],ret);self.assertEqual(o[7],0)
                self.assertFalse(o[3]);self.assertEqual(o[14],-114)

    def test_null_args(self):
        for n in range(4):self.assertEqual(self.lib.null_args(n),-22)

    def test_every_prepare_io_failure_preserves_first_error_and_restores_attempted_settings(self):
        calls=self.case()[6]
        for uncertain in [0,1]:
            for failure in range(1,calls+1):
                with self.subTest(failure=failure,uncertain=uncertain):
                    o=self.case(fail=failure,uncertain=uncertain)
                    self.assertEqual(o[0:3],[-5,-5,0]);self.assertEqual(o[3],0)
                    self.assertEqual(o[8:11],[0xc1,0x77,0xf0]);self.assertEqual(o[28],0)
                    self.assertEqual(o[14],-114);self.assertEqual(o[6],o[15])

    def test_each_silent_settings_write_drop_is_detected_and_restored(self):
        detected=[]
        for drop in range(1,self.case()[6]+1):
            o=self.case(drop=drop)
            if o[0]:
                detected.append(drop);self.assertEqual(o[0],-5)
                self.assertEqual(o[8:11],[0xc1,0x77,0xf0]);self.assertFalse(o[3])
        self.assertEqual(len(detected),3)

    def test_explicit_restore_is_off_verified_and_idempotent(self):
        o=self.case(scenario=6)
        self.assertEqual(o[18:23],[0,0,0,2,1]);self.assertEqual(o[24:28],[0xc1,0x77,0xf0,1])
        self.assertEqual(o[31:33],[0,0])

    def test_each_cleanup_io_failure_retains_pending(self):
        count=self.case(scenario=6)[23]
        for failure in range(1,count+1):
            with self.subTest(failure=failure):
                o=self.case(restore_fail=failure,uncertain=1)
                self.assertEqual(o[18:22],[-5,-5,1,3])
                if failure==2: # no OFF readback => inherited high fields not restored
                    self.assertEqual(o[24:27],[0xa4,0x73,0xec])

    def test_persistent_bus_failure_cannot_prove_off_or_restore(self):
        # First settings write can have reached silicon. All later reads fail.
        for failure in range(16,self.case()[6]+1):
            o=self.case(fail=failure,persistent=1,uncertain=1)
            if o[13]:
                self.assertEqual(o[0],-5);self.assertEqual(o[2],-5)
                self.assertEqual(o[3],1);self.assertEqual(o[5],0)

    def test_new_mode_fault_or_detach_stops_and_restores_without_fault_clearing(self):
        for inject,ret in [(1,-16),(2,-5),(5,-67)]:
            o=self.case(inject=inject);self.assertEqual(o[0],ret)
            self.assertEqual(o[8:11],[0xc1,0x77,0xf0]);self.assertEqual(o[12],1)
            self.assertEqual(o[3],0)
            if inject==2:self.assertEqual(o[33],34)

    def test_protection_drift_is_retained_and_not_rewritten(self):
        o=self.case(inject=3)
        self.assertEqual(o[0:4],[-5,-5,-5,1]);self.assertEqual(o[4],3)
        self.assertEqual(o[28],1);self.assertEqual(o[34],(0x0d*7+3)^1)

    def test_unowned_settings_bit_drift_is_not_overwritten_or_claimed_restored(self):
        o=self.case(inject=4)
        self.assertEqual(o[0:4],[-5,-5,-5,1]);self.assertEqual(o[8],0x41)

    def test_no_runtime_hook_export_or_probe_activation(self):
        source=(ROOT/'kernel/drivers/sm5440-control.c').read_text()
        for text in ['EXPORT_SYMBOL','module_init','late_initcall','msleep','usleep','SM5440_MODE_CHG_ON']:
            self.assertNotIn(text,source)
        driver=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        # The new isolated diagnostic caller disappears from both default and
        # offline-policy preprocessing; no production activation was added.
        no_headers=re.sub(r'^\s*#include[^\n]*', '', driver, flags=re.M)
        for flags in [[], ['-DCONFIG_X710_CHARGING_POLICY=1']]:
            parsed=subprocess.check_output(['cc','-E','-P','-x','c',*flags,'-'],
                                           input=no_headers,text=True)
            self.assertNotIn('sm5440_control_prepare(',parsed)
        self.assertNotIn('sm5440_control_prepare(', (ROOT/'kernel/drivers/x710-pd-session.c').read_text())
        patch=(ROOT/'kernel/patches/0016-power-supply-hook-sm5440-off-control.patch').read_text()
        self.assertIn('obj-$(CONFIG_X710_CHARGING_POLICY) += sm5440-control.o',patch)
        prep=(ROOT/'scripts/prepare-kernel.sh').read_text()
        self.assertIn('sm5440-control.c) dest="$tree/drivers/power/supply"',prep)
        self.assertIn('"$driver_src/sm5440-control.h" "$tree/drivers/power/supply/"',prep)


if __name__ == '__main__':
    unittest.main()
