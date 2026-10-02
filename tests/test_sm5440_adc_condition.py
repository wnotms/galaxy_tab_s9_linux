"""Actual C OFF-only ENHIZ transaction, restore/PM/fault and profile isolation."""
import ctypes
import errno
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class ConditionTransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        cls.source = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#define CONFIG_SM5440_ADC_CONDITION_TEST 1
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define READ_ONCE(x) (x)
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
typedef int atomic_t; typedef int wait_queue_head_t;
struct device {int unused;};struct regmap {int unused;};struct mutex {int unused;};
struct delayed_work {int unused;};struct power_supply {int unused;};struct dentry {int unused;};
static int depth,errors,calls,fail,fail2,waits,started,never_ready,stop_wait,wrong_read;
static unsigned int write_regs[128],write_masks[128],write_values[128];
static int writes;static u8 regs[64];static u64 clock_ms;
static void mutex_lock(struct mutex *p){(void)p;depth++;}
static void mutex_unlock(struct mutex *p){(void)p;depth--;}
#define lockdep_assert_held(x) ((void)(x))
#define ktime_to_ms(x) ((x)/1000000ULL)
static u64 ktime_get_boottime(void){return clock_ms*1000000ULL;}
''' + '#include "' + str(ROOT / 'kernel/drivers/sm5440-hw.h') + '"\n'
        code += function(cls.source, 'struct sm5440_sample {') + ';\n'
        code += function(cls.source, 'struct sm5440_direct {') + ';\n'
        code += r'''
static struct sm5440_direct *current;
static int step(void){if(depth!=1)errors++;calls++;return calls==fail||calls==fail2?-EIO:0;}
static int regmap_read(struct regmap *m,unsigned int r,unsigned int *v){
 (void)m;int ret=step();if(ret)return ret;*v=regs[r];
 if(r==SM5440_INT4)regs[r]=0;
 if(calls==wrong_read)*v^=1;return 0;}
static int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n){
 (void)m;int ret=step();if(ret)return ret;memcpy(v,regs+r,n);
 if(r==SM5440_INT1)memset(regs+r,0,n);return 0;}
static int regmap_write(struct regmap *m,unsigned int r,unsigned int v){
 (void)m;int ret=step();if(ret)return ret;
 write_regs[writes]=r;write_masks[writes]=255;write_values[writes++]=v;regs[r]=v;return 0;}
static int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int v){
 (void)m;int ret=step();
 /* Model uncertain delivery: an errored CNTL6 write CAN reach hardware. */
 if(ret&&r!=SM5440_CNTL6)return ret;
 write_regs[writes]=r;write_masks[writes]=mask;write_values[writes++]=v;
 regs[r]=(regs[r]&~mask)|(v&mask);
 if(r==SM5440_ADCCNTL1&&(v&SM5440_ADC_ENABLE)){started=1;waits=0;}
 return ret;}
static void msleep(unsigned int ms){
 if(depth)errors++;clock_ms+=ms;
 if(started&&++waits>=3&&!never_ready)regs[SM5440_INT4]|=SM5440_ADC_READY;
 if(stop_wait==1||(stop_wait==2&&started&&waits==2))current->stopped=true;}
'''
        for name in ['static int sm5440_off(', 'static int sm5440_sample_once(',
                     'static int sm5440_adc_rearm(', 'static int sm5440_condition_begin(',
                     'static int sm5440_condition_restore(', 'static int sm5440_condition_cycle(']:
            code += function(cls.source, name) + '\n'
        code += r'''
int exercise(int failure,int second,int initial,int scenario,int mismatch,long long *out){
 struct sm5440_direct sm={0};struct sm5440_sample s={0};current=&sm;
 depth=errors=calls=waits=started=writes=never_ready=stop_wait=0;clock_ms=1000;
 fail=failure;fail2=second;wrong_read=mismatch;memset(regs,0,sizeof(regs));
 regs[SM5440_CNTL5]=1;regs[SM5440_CNTL6]=initial;regs[SM5440_ADCCNTL1]=12;
 /* VBAT4V, VBUS5V, IBUS0; original decode unchanged. */
 unsigned int vbat=(4000000-2048000)/500,vbus=(5000000-4096000)/1000;
 regs[SM5440_ADC_VBUS]=vbus>>5;regs[SM5440_ADC_VBUS+1]=(vbus&31)<<3;
 regs[SM5440_ADC_VBUS+8]=7;regs[SM5440_ADC_VBUS+9]=vbat>>5;
 regs[SM5440_ADC_VBUS+10]=(vbat&31)<<3;regs[SM5440_STATUS1+2]=32;
 regs[SM5440_CNTL2]=0xf2;regs[SM5440_VBUSCNTL]=0xe7;
 regs[SM5440_VBATCNTL]=0x37;regs[SM5440_PRTNCNTL]=0xfe;
 if(scenario==1)sm.stopped=true;if(scenario==2)sm.dying=true;
 if(scenario==3)regs[SM5440_CNTL5]=5;if(scenario==4)never_ready=1;
 if(scenario==5)stop_wait=1;if(scenario==6)sm.fault=true;
 if(scenario==7)sm.condition_attempted=true;if(scenario==8)stop_wait=2;
 int ret=sm5440_condition_cycle(&sm,&s);
 out[0]=calls;out[1]=errors;out[2]=depth;out[3]=regs[SM5440_CNTL6];
 out[4]=regs[SM5440_CNTL5]&SM5440_MODE_MASK;out[5]=regs[SM5440_ADCCNTL1]&1;
 out[6]=sm.enhiz_restore_pending;out[7]=sm.fault;out[8]=s.condition_error;
 out[9]=s.restore_error;out[10]=s.cntl6_before_valid;out[11]=s.cntl6_before;
 out[12]=s.cntl6_during_valid;out[13]=s.cntl6_during;
 out[14]=s.cntl6_restored_valid;out[15]=s.cntl6_restored;
 out[16]=s.vbat_uv;out[17]=s.vbus_uv;out[18]=s.ibus_ua;
 out[19]=s.acquired_ms;out[20]=s.completed_ms;out[21]=writes;
 out[22]=waits;out[23]=sm.condition_attempted;
 for(int i=0;i<writes;i++){
  unsigned int r=write_regs[i],mask=write_masks[i],v=write_values[i];
  if(r==SM5440_CNTL6){if(mask!=SM5440_ENHIZ||(v&~SM5440_ENHIZ))out[1]++;}
  else if(r==SM5440_CNTL5){if(v&SM5440_MODE_MASK)out[1]++;}
  else if(r==SM5440_ADCCNTL1){if(mask&~(SM5440_ADC_ENABLE|SM5440_ADC_RATE|SM5440_ADC_AVG32))out[1]++;}
  else if(r!=SM5440_ADCCNTL2||v!=SM5440_ADC_CHANNELS)out[1]++;
 }
 return ret;}
'''
        c = Path(cls.tmp.name) / 'condition.c'
        c.write_text(code)
        lib = c.with_suffix('.so')
        subprocess.run(['cc', '-shared', '-fPIC', '-Wall', '-Werror',
                        '-Wno-misleading-indentation', str(c), '-o', str(lib)], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.exercise.argtypes = [ctypes.c_int] * 5 + [ctypes.POINTER(ctypes.c_longlong)]

    def run_case(self, fail=0, second=0, initial=0x89, scenario=0, mismatch=0):
        out = (ctypes.c_longlong * 24)()
        ret = self.lib.exercise(fail, second, initial, scenario, mismatch, out)
        self.assertEqual(list(out[1:3]), [0, 0], 'lock/write discipline')
        return ret, list(out)

    def test_one_actual_converter_restores_bit_and_preserves_decode(self):
        ret, r = self.run_case()
        self.assertEqual(ret, 0)
        self.assertEqual(r[3:10], [0x89, 0, 0, 0, 0, 0, 0])
        self.assertEqual(r[10:16], [1, 0x89, 1, 9, 1, 0x89])
        self.assertEqual(r[16:19], [4000000, 5000000, 0])
        self.assertGreater(r[19], 0)
        self.assertGreater(r[22], 0)
        self.assertEqual(r[23], 1)

    def test_initial_clear_bit_and_other_bits_preserved(self):
        for initial in [0x09, 0x89, 0x19, 0x99, 0x7f, 0xff]:
            ret, r = self.run_case(initial=initial)
            self.assertEqual(ret, 0)
            self.assertEqual(r[3], initial)
            self.assertEqual(r[13], initial & ~128)

    def test_stopped_dying_fault_second_attempt_do_not_touch_bus(self):
        for scenario, error in [(1, errno.ESHUTDOWN), (2, errno.ESHUTDOWN),
                                (6, errno.EIO), (7, errno.EALREADY)]:
            ret, r = self.run_case(scenario=scenario)
            self.assertEqual(ret, -error)
            self.assertEqual(r[0], 0)
            self.assertEqual(r[21], 0)

    def test_active_mode_refused_before_condition_write(self):
        ret, r = self.run_case(scenario=3)
        self.assertEqual(ret, -errno.EBUSY)
        self.assertEqual(r[0], 1)
        self.assertEqual(r[21], 0)
        self.assertEqual(r[3], 0x89)

    def test_every_actual_bus_failure_has_no_grant_and_restore_accounting(self):
        _, clean = self.run_case()
        for step in range(1, clean[0] + 1):
            ret, r = self.run_case(fail=step)
            self.assertLess(ret, 0, step)
            if r[9] == 0:
                self.assertEqual(r[3], 0x89, step)
                self.assertEqual(r[6], 0, step)
            else:
                self.assertEqual(r[6:8], [1, 1], step)
            self.assertTrue(r[8] or r[9], step)

    def test_uncertain_enhiz_write_is_restored(self):
        ret, r = self.run_case(fail=5)
        self.assertEqual(ret, -errno.EIO)
        self.assertEqual(r[3], 0x89)
        self.assertEqual(r[9], 0)
        self.assertEqual(r[6], 0)

    def test_readback_mismatch_refuses_and_restores(self):
        ret, r = self.run_case(mismatch=6)
        self.assertEqual(ret, -errno.EIO)
        self.assertEqual(r[3], 0x89)
        self.assertEqual(r[6], 0)
        self.assertEqual(r[8], -errno.EIO)

    def test_timeout_restores_without_masking_first_error(self):
        ret, r = self.run_case(scenario=4)
        self.assertEqual(ret, -errno.ETIMEDOUT)
        self.assertEqual(r[3:10], [0x89, 0, 0, 0, 0, -errno.ETIMEDOUT, 0])

    def test_cancel_during_unlocked_rearm_restores(self):
        ret, r = self.run_case(scenario=5)
        self.assertEqual(ret, -errno.ESHUTDOWN)
        self.assertEqual(r[3:7], [0x89, 0, 0, 0])

    def test_cancel_during_converter_wait_restores(self):
        ret, r = self.run_case(scenario=8)
        self.assertEqual(ret, -errno.ESHUTDOWN)
        self.assertEqual(r[3:7], [0x89, 0, 0, 0])
        self.assertEqual(r[8:10], [-errno.ESHUTDOWN, 0])

    def test_adc_disable_readback_refused_before_enhiz_mutation(self):
        ret, r = self.run_case(mismatch=4)
        self.assertEqual(ret, -errno.EIO)
        self.assertEqual(r[3], 0x89)
        self.assertEqual(r[6], 0)
        self.assertEqual(r[12], 0)

    def test_restoration_readback_mismatch_keeps_pending_fault(self):
        _, clean = self.run_case()
        ret, r = self.run_case(mismatch=clean[0]-1)
        self.assertEqual(ret, -errno.EIO)
        self.assertEqual(r[8:10], [0, -errno.EIO])
        self.assertEqual(r[6:8], [1, 1])
        self.assertEqual(r[14], 1)

    def test_native_error_and_cleanup_error_both_preserved(self):
        ret, r = self.run_case(fail=5, second=11)
        self.assertEqual(ret, -errno.EIO)
        self.assertEqual(r[8:10], [-errno.EIO, -errno.EIO])
        self.assertEqual(r[6:8], [1, 1])

    def test_snapshot_fields_validity_not_zero_fabrication(self):
        show = function(self.source, 'static void sm5440_snapshot_sample_show(')
        for field in ['cntl6_before_valid', 'cntl6_during_valid',
                      'cntl6_restored_valid', 'condition_error', 'restore_error']:
            self.assertIn(field, show)

    def test_original_converter_rearm_quiesce_and_thresholds_unchanged(self):
        old = subprocess.check_output(['git', 'show', '949d6b73:kernel/drivers/sm5440-direct.c'],
                                      cwd=ROOT, text=True)
        for name in ['static int sm5440_sample_once(', 'static int sm5440_adc_rearm(',
                     'static int sm5440_quiesce(', 'static bool sm5440_passive_pc_sample(',
                     'static bool sm5440_startup_matches(', 'int sm5440_passive_request_fresh(',
                     'int sm5440_passive_observe(']:
            self.assertEqual(function(self.source, name), function(old, name))

    def test_normal_preprocessed_driver_paths_are_identical(self):
        old = subprocess.check_output(['git', 'show', '949d6b73:kernel/drivers/sm5440-direct.c'],
                                      cwd=ROOT, text=True)
        names = ['struct sm5440_sample {', 'struct sm5440_direct {',
                 'struct sm5440_snapshot {', 'static int sm5440_publish(',
                 'static int sm5440_off(', 'static int sm5440_sample_once(',
                 'static int sm5440_adc_rearm(', 'static void sm5440_poll(',
                 'static int sm5440_quiesce(', 'static void sm5440_stop(',
                 'static int sm5440_suspend(', 'static int sm5440_resume(',
                 'static int sm5440_probe(', 'static void sm5440_snapshot_capture(',
                 'static void sm5440_snapshot_sample_show(', 'static int sm5440_snapshot_show(']
        for name in names:
            before = subprocess.check_output(['cc', '-E', '-P', '-x', 'c', '-'],
                                             input=function(old, name), text=True)
            after = subprocess.check_output(['cc', '-E', '-P', '-x', 'c', '-'],
                                            input=function(self.source, name), text=True)
            self.assertEqual(''.join(before.split()), ''.join(after.split()), name)

    def test_diagnostic_has_no_publish_reschedule_or_resume_rearm(self):
        probe = function(self.source, 'static int sm5440_probe(')
        self.assertIn('#ifndef CONFIG_SM5440_ADC_CONDITION_TEST\n\tret = sm5440_publish(sm);', probe)
        poll = function(self.source, 'static void sm5440_poll(')
        self.assertIn('#ifndef CONFIG_SM5440_ADC_CONDITION_TEST\n\tif (!READ_ONCE(sm->stopped)', poll)
        resume = function(self.source, 'static int sm5440_resume(')
        self.assertIn('if (sm->condition_attempted)\n\t\treturn -EOPNOTSUPP;', resume)
        for name in ['static int sm5440_suspend(', 'static void sm5440_stop(']:
            body = function(self.source, name)
            self.assertLess(body.index('sm5440_quiesce('), body.index('sm5440_condition_restore('))


class ConditionProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location('gate', ROOT / 'scripts/verify-x710-charging-profile.py')
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def test_exact_separate_profile_and_refused_ordinary_enable(self):
        cfg = self.gate.BASE.read_text() + '\nCONFIG_CHARGER_SM5440_DIRECT=y\nCONFIG_SM5440_ADC_CONDITION_TEST=y\n'
        self.assertTrue(self.gate.verify(cfg, profile='sm5440-adc-condition')['valid'])
        for profile in ['sm5440-passive', 'sm5440-policy-offline']:
            self.assertFalse(self.gate.verify(cfg, profile=profile)['valid'])
        self.assertFalse(self.gate.STAGE2.verify(cfg)['valid'])

    def test_policy_and_diagnostic_cannot_be_combined(self):
        cfg = self.gate.BASE.read_text() + '\nCONFIG_CHARGER_SM5440_DIRECT=y\nCONFIG_SM5440_ADC_CONDITION_TEST=y\nCONFIG_X710_CHARGING_POLICY=y\n'
        for profile in ['sm5440-adc-condition', 'sm5440-policy-offline']:
            self.assertFalse(self.gate.verify(cfg, profile=profile)['valid'])

    def test_existing_profiles_accept_new_inactive_declaration(self):
        cfg = self.gate.BASE.read_text() + '\nCONFIG_CHARGER_SM5440_DIRECT=y\n# CONFIG_SM5440_ADC_CONDITION_TEST is not set\n'
        self.assertTrue(self.gate.verify(cfg)['valid'])
        self.assertTrue(self.gate.verify(cfg+'CONFIG_X710_CHARGING_POLICY=y\n', profile='sm5440-policy-offline')['valid'])

    def test_kconfig_built_in_dependency_and_no_default_enable(self):
        patch = (ROOT / 'kernel/patches/0015-power-supply-hook-sm5440-adc-condition.patch').read_text()
        self.assertIn('depends on CHARGER_SM5440_DIRECT=y && !X710_CHARGING_POLICY', patch)
        self.assertNotIn('default y', patch)
        for f in ['gts9wifi-mainline.fragment', 'gts9wifi-sm5440-passive.fragment',
                  'gts9wifi-sm5440-policy-offline.fragment']:
            self.assertNotIn('CONFIG_SM5440_ADC_CONDITION_TEST=y', (ROOT/'kernel/config'/f).read_text())
