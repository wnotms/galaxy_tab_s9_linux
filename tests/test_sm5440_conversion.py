"""Actual bounded converter C with read-to-clear bus, time and fault injection."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = Path(cls.tmp.name)
        (p / 'linux').mkdir()
        headers = {
            'types.h': '#ifndef MOCK_TYPES\n#define MOCK_TYPES\n#include <stdint.h>\n#include <stdbool.h>\n'
                       'typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n#endif\n',
            'bitops.h': '#define BIT(n) (1U << (n))\n'
                        '#define GENMASK(h,l) (((~0U) >> (31-(h))) & ((~0U) << (l)))\n',
            'compiler.h': '#define READ_ONCE(x) (x)\n',
            'errno.h': ''.join('#define ' + name + ' ' + str(code) + '\n'
                              for code, name in errno.errorcode.items()),
            'ktime.h': '#include <stdint.h>\nextern uint64_t fake_clock;\n'
                       'static inline uint64_t ktime_get_boottime(void){return fake_clock;}\n'
                       '#define ktime_to_ms(v) (v)\n',
            'regmap.h': 'struct regmap;\n'
                        'int regmap_read(struct regmap *,unsigned int,unsigned int *);\n'
                        'int regmap_write(struct regmap *,unsigned int,unsigned int);\n'
                        'int regmap_bulk_read(struct regmap *,unsigned int,void *,unsigned int);\n'
                        'int regmap_update_bits(struct regmap *,unsigned int,unsigned int,unsigned int);\n',
        }
        for name, content in headers.items():
            (p / 'linux' / name).write_text(content)
        (p / 'mock.c').write_text(r'''
#include <string.h>
#include "sm5440-conversion.h"
#include "sm5440-hw.h"
uint64_t fake_clock;
static u64 generation;
struct regmap {
 u8 reg[256], original[256];
 int calls,writes,enables,unsafe,fail,persistent,uncertain,drop,scenario,step,ready_sent;
 u64 enabled_ms,disabled_ms;
};
static int bad(struct regmap *m) {
 m->calls++;fake_clock+=m->step;
 return m->fail && (m->calls==m->fail || (m->persistent && m->calls>=m->fail));
}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v) {
 if(bad(m))return -5;*v=m->reg[r];if(r<=3)m->reg[r]=0;return 0;
}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n) {
 if(bad(m))return -5;
 if(r==0 && m->enabled_ms && !m->ready_sent && fake_clock>=m->enabled_ms+30 && m->scenario!=7) {
  m->reg[3]|=1;m->ready_sent=1;
 }
 if(r==0x1e && m->scenario==13)generation++;
 if(r==0x1e && m->scenario==18)m->reg[0x10]=1;
 if(r==0x1e && m->scenario==19)m->reg[0x0a]=0;
 memcpy(v,m->reg+r,n);if(r==0)memset(m->reg,0,n);return 0;
}
static void written(struct regmap *m,unsigned int r,unsigned int v) {
 m->writes++;
 if(r!=0x1c && r!=0x1d)m->unsafe++;
 if(r==0x1c && (v&1)) {
  m->enables++;m->enabled_ms=fake_clock;
  if(fake_clock<m->disabled_ms+20 || (v&10)!=8)m->unsafe++;
  if(m->scenario==8)m->reg[0x0a]|=2;
  if(m->scenario==9)generation++;
  if(m->scenario>=100 && m->scenario<=110) {
   static const u8 regs[11]={8,8,8,10,10,10,10,10,10,11,11};
   static const u8 bits[11]={16,8,1,128,64,8,4,2,1,4,2};
   int index=m->scenario-100;m->reg[regs[index]]|=bits[index];
  }
  if(m->scenario>=200 && m->scenario<=210) {
   static const u8 regs[11]={0,0,0,2,2,2,2,2,2,3,3};
   static const u8 bits[11]={16,8,1,128,64,8,4,2,1,4,2};
   int index=m->scenario-200;m->reg[regs[index]]|=bits[index];
  }
 }
 if(r==0x1c && !(v&1) && m->enabled_ms) {
  if(m->scenario==17)v^=0x40;
  if(m->scenario==23)m->reg[0x0a]|=2;
 }
 if(m->calls!=m->drop)m->reg[r]=v;
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int v) {
 int b=bad(m);if(!b||m->uncertain)written(m,r,v);return b?-5:0;
}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int v) {
 int b=bad(m);unsigned int next=(m->reg[r]&~mask)|(v&mask);
 if((!b||m->uncertain)&&next!=m->reg[r])written(m,r,next);return b?-5:0;
}
static void raw13(u8 *p,unsigned int raw) {p[0]=raw>>5;p[1]=(raw&31)<<3;}
void exercise(int scenario,int running,int fail,int persistent,int uncertain,int drop,int step,int *o) {
 struct regmap m={0};struct sm5440_conversion a={0};int ret,early_calls;
 fake_clock=1000;generation=1;
 m.reg[0x2b]=0x21;m.reg[0x10]=running?5:1;m.reg[0x0a]=32;
 m.reg[0x1c]=0x82;m.reg[0x1d]=0x55;m.disabled_ms=1000;
 raw13(m.reg+0x1e,4904);raw13(m.reg+0x22,running?2401:0);
 m.reg[0x26]=15;raw13(m.reg+0x27,3504);
 a.enabled=true;a.generation=&generation;a.epoch=1;a.running=running;
 if(scenario==1)a.enabled=false;
 if(scenario==2)generation++;
 if(scenario==3)m.reg[0x2b]=0x22;
 if(scenario==4)m.reg[0x1c]|=1;
 if(scenario==5)m.reg[0x10]=running?1:5;
 if(scenario==6)m.reg[1]=2; /* latched startup/thermal fault before start */
 if(scenario==7)m.reg[3]=1; /* old READY only, no new completion */
 if(scenario==12)raw13(m.reg+0x27,0);
 if(scenario==22)m.reg[0x0a]=64;
 if(scenario==29)raw13(m.reg+0x27,3505); /* 3800.5mV raw precision */
 memcpy(m.original,m.reg,256);
 m.fail=fail;m.persistent=persistent;m.uncertain=uncertain;m.drop=drop;m.step=step;m.scenario=scenario;
 ret=sm5440_conversion_begin(&m,&a);o[0]=ret;
 if(ret==-115) {
  m.disabled_ms=a.disabled_ms;
  fake_clock=a.disabled_ms+19;early_calls=m.calls;
  o[1]=sm5440_conversion_advance(&m,&a);o[2]=m.calls-early_calls;
  fake_clock=a.disabled_ms+20;
  if(scenario==14)fake_clock=1;
  if(scenario==25)fake_clock=a.requested_ms+101;
  ret=sm5440_conversion_advance(&m,&a);o[3]=ret;
  if(scenario==28)ret=sm5440_conversion_cancel(&m,&a);
  for(int i=0;ret==-115 && i<100;i++) {
   if(scenario!=26)fake_clock+=5;
   if(scenario==10)m.reg[0x1c]^=2;
   if(scenario==11)m.reg[0x1d]^=1;
   if(scenario==27)ret=sm5440_conversion_cancel(&m,&a);
   else ret=sm5440_conversion_advance(&m,&a);
  }
 }
 o[4]=ret;o[5]=a.state;o[6]=m.calls;o[7]=m.writes;o[8]=m.enables;o[9]=m.unsafe;
 o[10]=a.sample.valid;o[11]=a.sample.observed_ms;o[12]=a.sample.vbus_mv;
 o[13]=a.sample.vbat_mv;o[14]=a.sample.ibus_ua;o[15]=a.die_decic;
 o[16]=a.operation_error;o[17]=a.cleanup_error;o[18]=a.owned;o[19]=a.adc_off_verified;
 o[20]=m.reg[0x1c];o[21]=m.reg[0x1d];o[22]=a.requested_ms;o[23]=a.acquired_ms;
 o[24]=a.completed_ms;o[25]=a.events[3];o[26]=a.faults;o[27]=m.reg[0x10];
 o[28]=sm5440_conversion_begin(&m,&a);o[29]=sm5440_conversion_advance(&m,&a);
 o[30]=sm5440_conversion_cancel(&m,&a);o[31]=m.calls;
 o[32]=a.vbus_uv;o[33]=a.vbat_uv;o[34]=a.sample.pump_on;
}
''')
        cmd = ['cc', '-shared', '-fPIC', '-std=c11', '-D__KERNEL__', '-Wall', '-Wextra',
               '-Werror', '-Wno-misleading-indentation', '-I' + str(p),
               '-I' + str(ROOT / 'kernel/drivers'),
               str(ROOT / 'kernel/drivers/sm5440-conversion.c'), str(p / 'mock.c'),
               '-o', str(p / 'conversion.so')]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(p / 'conversion.so'))
        cls.lib.exercise.argtypes = [ctypes.c_int] * 7 + [ctypes.POINTER(ctypes.c_int)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def case(self, scenario=0, running=0, fail=0, persistent=0, uncertain=0, drop=0, step=0):
        out = (ctypes.c_int * 35)()
        self.lib.exercise(scenario, running, fail, persistent, uncertain, drop, step, out)
        self.assertEqual(out[9], 0, 'unsourced write or early converter enable')
        if scenario != 1:
            self.assertEqual(out[28:31], [-114, -114, -114], 'terminal object cannot restart')
            self.assertEqual(out[6], out[31], 'terminal reuse does not perform I/O')
        return list(out)

    def test_off_conversion_preserves_original_fields_and_oldest_time(self):
        o = self.case()
        self.assertEqual(o[:4], [-115, -115, 0, -115])
        self.assertEqual(o[4:6], [0, 3])
        self.assertEqual(o[10:16], [1, 1020, 9000, 3800, 0, 300])
        self.assertEqual(o[16:22], [0, 0, 0, 1, 0x82, 0x55])
        self.assertGreater(o[24], o[23])
        self.assertLessEqual(o[24] - o[22], 100)
        self.assertEqual(o[27], 1)

    def test_running_conversion_preserves_625ua_and_never_changes_pump_mode(self):
        o = self.case(running=1)
        self.assertEqual(o[4], 0)
        self.assertEqual(o[14], 1500625)
        self.assertEqual(o[27], 5)
        self.assertEqual(o[8], 1)
        self.assertEqual(o[34], 1)

    def test_microvolt_voltage_is_preserved_alongside_core_millivolts(self):
        o = self.case(29)
        self.assertEqual(o[4], 0)
        self.assertEqual(o[33], 3800500)
        self.assertEqual(o[13], 3800)

    def test_default_disabled_has_no_bus_access_or_enabled_converter(self):
        o = self.case(1)
        self.assertEqual(o[0], -1)
        self.assertEqual(o[6:11], [0, 0, 0, 0, 0])

    def test_identity_epoch_foreign_conversion_and_prefault_refuse_start(self):
        for scenario in (2, 3, 4, 5, 6, 22):
            with self.subTest(scenario=scenario):
                o = self.case(scenario)
                self.assertLess(o[4], 0)
                self.assertEqual(o[8], 0)
                self.assertEqual(o[10], 0)

    def test_old_ready_cannot_finish_new_conversion_and_raw_latch_is_retained(self):
        o = self.case(7)
        self.assertEqual(o[4], -110)
        self.assertEqual(o[25] & 1, 1)
        self.assertEqual(o[10], 0)
        self.assertEqual(o[20] & 1, 0)

    def test_fault_generation_and_control_drift_refuse_measurement(self):
        for scenario in (8, 9, 10, 11, 12, 13, 17, 18, 19, 23):
            with self.subTest(scenario=scenario):
                o = self.case(scenario, running=1)
                self.assertLess(o[4], 0)
                self.assertEqual(o[10], 0)
                self.assertEqual(o[20] & 1, 0)

    def test_each_live_and_latched_hardware_fault_is_retained_and_rejected(self):
        for base in (100, 200):
            for index in range(11):
                with self.subTest(base=base, index=index):
                    o = self.case(base + index, running=1)
                    self.assertEqual(o[4], -5)
                    self.assertEqual(o[10], 0)
                    self.assertTrue(o[26] & (1 << index))
                    self.assertEqual(o[27], 5, 'caller must perform checked pump OFF')

    def test_native_clock_regression_and_request_timeout(self):
        self.assertEqual(self.case(14)[4], -62)
        self.assertEqual(self.case(25)[4], -110)

    def test_same_millisecond_polling_cannot_run_forever(self):
        o = self.case(26)
        self.assertEqual(o[4], -110)
        self.assertLess(o[6], 500)
        self.assertEqual(o[10], 0)

    def test_cancel_during_rearm_or_conversion_disables_and_preserves_error(self):
        for scenario in (27, 28):
            o = self.case(scenario)
            self.assertEqual(o[4], -125)
            self.assertEqual(o[16], -125)
            self.assertEqual(o[20:22], [0x82, 0x55])
            self.assertEqual(o[10], 0)

    def test_every_single_bus_error_invalidates_with_no_converter_retry(self):
        calls = self.case()[6]
        for fail in range(1, calls + 1):
            for uncertain in (0, 1):
                with self.subTest(fail=fail, uncertain=uncertain):
                    o = self.case(fail=fail, uncertain=uncertain)
                    self.assertLess(o[4], 0)
                    self.assertEqual(o[10], 0)
                    self.assertLessEqual(o[8], 1)
                    if o[20] & 1:
                        self.assertEqual(o[19], 0, 'failed cleanup must not claim ADC OFF')
                        self.assertEqual(o[18], 1, 'unknown controls remain owned')
                        self.assertLess(o[17], 0)

    def test_persistent_bus_loss_preserves_unknown_cleanup_and_first_error(self):
        for fail in range(1, self.case()[6] + 1):
            with self.subTest(fail=fail):
                o = self.case(fail=fail, persistent=1, uncertain=1)
                self.assertEqual(o[4], -5)
                self.assertEqual(o[16], -5)
                self.assertEqual(o[10], 0)
                if o[18]:
                    self.assertEqual(o[17], -5)

    def test_dropped_writes_require_real_readback_not_successful_bus_status(self):
        for call in range(1, self.case()[6] + 1):
            with self.subTest(call=call):
                o = self.case(drop=call)
                if o[4] == 0:
                    self.assertEqual(o[20:22], [0x82, 0x55])
                    self.assertEqual(o[18], 0)
                else:
                    self.assertEqual(o[10], 0)
                self.assertLessEqual(o[8], 1)

    def test_active_mode_all_bus_errors_remain_invalid_without_touching_pump(self):
        for call in range(1, self.case(running=1)[6] + 1):
            with self.subTest(call=call):
                o = self.case(running=1, fail=call, uncertain=1)
                self.assertLess(o[4], 0)
                self.assertEqual(o[10], 0)
                self.assertEqual(o[27], 5)

    def test_delayed_bus_crossing_deadline_cannot_publish_fresh(self):
        o = self.case(step=6)
        self.assertEqual(o[4], -110)
        self.assertEqual(o[10], 0)


if __name__ == '__main__':
    unittest.main()
