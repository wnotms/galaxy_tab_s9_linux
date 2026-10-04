"""Execute isolated continuous ADC C with native clock/read-clear/error mocks."""
import ctypes
import errno
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class TimingHardwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        p = Path(cls.tmp.name)
        (p / 'linux').mkdir()
        headers = {
            'types.h': '#ifndef TYPES_H\n#define TYPES_H\n#include <stdint.h>\n#include <stdbool.h>\n'
                       'typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n#endif\n',
            'bitops.h': '#define BIT(n) (1U << (n))\n#define GENMASK(h,l) (((~0U) >> (31-(h))) & ((~0U) << (l)))\n',
            'errno.h': ''.join('#define ' + name + ' ' + str(code) + '\n' for code, name in errno.errorcode.items()),
            'ktime.h': 'extern unsigned long long fake_clock;\n#define ktime_get_boottime() fake_clock\n#define ktime_to_ms(v) (v)\n',
            'regmap.h': 'struct regmap;\nint regmap_read(struct regmap*,unsigned int,unsigned int*);\n'
                        'int regmap_write(struct regmap*,unsigned int,unsigned int);\n'
                        'int regmap_update_bits(struct regmap*,unsigned int,unsigned int,unsigned int);\n'
                        'int regmap_bulk_read(struct regmap*,unsigned int,void*,unsigned int);\n',
        }
        for name, content in headers.items():
            (p / 'linux' / name).write_text(content)
        (p / 'mock.c').write_text(r"""
#include <string.h>
#include "sm5440-timing.h"
#include "sm5440-hw.h"
unsigned long long fake_clock;
static int held;
struct regmap {
 u8 reg[64];int calls,fail,uncertain,drop,unsafe,writes,enables,scenario,ready_count;
 int cycle,off_writes,dropped_effective;
 u64 enabled_ms,next_ready_ms,disabled_ms;
};
static int transfer(struct regmap *m) {if(m->cycle&&held!=1)m->unsafe++;fake_clock++;return ++m->calls==m->fail;}
static void update_ready(struct regmap *m) {
 if((m->reg[0x1c]&1)&&m->next_ready_ms&&fake_clock>=m->next_ready_ms&&m->scenario!=1) {
  m->reg[3]|=1;m->ready_count++;m->next_ready_ms=fake_clock+(m->scenario==12?600:125);
  if(m->scenario==2)m->reg[0x0a]|=2;
  if(m->scenario==3)m->reg[0x10]=4;
  if(m->scenario==4)m->reg[0x1c]^=0x40;
  if(m->scenario==5)m->reg[0x1d]^=0x80;
  if(m->scenario==6)m->reg[3]|=4;
  if(m->scenario==7)m->reg[0x0a]=0;
 }
}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v) {
 if(transfer(m))return -5;update_ready(m);*v=m->reg[r];return 0;
}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n) {
 if(transfer(m))return -5;update_ready(m);memcpy(v,m->reg+r,n);
 if(r==0)memset(m->reg,0,n);return 0;
}
static void write(struct regmap *m,unsigned int r,unsigned int v) {
 m->writes++;if(r==0x10&&m->cycle&&!(v&12))m->off_writes++;
 else if(r!=0x1c&&r!=0x1d)m->unsafe++;
 if(r==0x1c&&(v&1)&&!(m->reg[r]&1)) {
  m->enables++;m->enabled_ms=fake_clock;
  if(fake_clock<m->disabled_ms+50||(v&11)!=11||m->reg[0x1d]!=0xdf)m->unsafe++;
  m->next_ready_ms=fake_clock+125;
 }
 if(r==0x1c&&!(v&1)&&(!m->disabled_ms||(m->reg[r]&1)))m->disabled_ms=fake_clock;
 if(m->calls!=m->drop)m->reg[r]=v;else if(m->reg[r]!=v)m->dropped_effective++;
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int v) {
 int bad=transfer(m);if(!bad||m->uncertain)write(m,r,v);return bad?-5:0;
}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int v) {
 int bad=transfer(m);unsigned int next=(m->reg[r]&~mask)|(v&mask);
 if(r==0x1c&&(mask&~11U))m->unsafe++;
 if(!bad||m->uncertain)write(m,r,next);return bad?-5:0;
}
static void raw13(u8 *p,unsigned int n){p[0]=n>>5;p[1]=(n&31)<<3;}
void exercise(int scenario,int fail,int uncertain,int drop,int *out) {
 struct regmap m={0};struct sm5440_timing t={0};int ret;
 fake_clock=1000;m.scenario=scenario;m.fail=fail;m.uncertain=uncertain;m.drop=drop;
 m.reg[0x2b]=0x11;m.reg[0x1c]=0x88;m.reg[0x1d]=0x41;m.reg[0x0a]=32;
 m.reg[3]=1; /* deliberately stale READY before enable */
 raw13(m.reg+0x1e,904);raw13(m.reg+0x27,3504);
 if(scenario==8)m.reg[0x10]=4;
 if(scenario==9)m.reg[0x1c]|=1;
 if(scenario==10)m.reg[0x2b]=2;
 if(scenario==20)raw13(m.reg+0x1e,5500);
 if(scenario==21)raw13(m.reg+0x27,4800);
 if(scenario==22)raw13(m.reg+0x22,1);
 if(scenario==23)m.reg[0x26]=40;
 if(scenario==24)m.reg[0x0a]=64;
 int idle_calls=m.calls;
 if(sm5440_timing_finish(&m,&t,0)!=-22||idle_calls!=m.calls||t.finished)m.unsafe++;
 ret=sm5440_timing_begin(&m,&t);
 int before=m.calls;int repeated=sm5440_timing_begin(&m,&t);
 if(repeated!=-114||before!=m.calls)m.unsafe++;
 for(int n=0;!ret&&n<600;n++) {
  fake_clock+=5;
  if(scenario==11&&n==25){ret=-108;break;}
  if(scenario==13&&n==25)fake_clock=1;
  if(scenario==14&&n==25)fake_clock+=3000;
  if(scenario==15&&n==25)fake_clock=t.last_ms;
  ret=sm5440_timing_step(&m,&t);
 }
 if(ret==1)ret=0;
 ret=sm5440_timing_finish(&m,&t,ret);
 before=m.calls;int again=sm5440_timing_finish(&m,&t,0);
 if(again!=-114||before!=m.calls)m.unsafe++;
 out[0]=ret;out[1]=t.error;out[2]=t.cleanup_error;out[3]=t.count;
 out[4]=t.restored;out[5]=m.unsafe;out[6]=m.enables;out[7]=m.calls;
 out[8]=m.reg[0x1c];out[9]=m.reg[0x1d];out[10]=m.writes;
 out[11]=t.enabled_ms? t.enabled_ms-t.disabled_ms:0;
 out[12]=t.count?t.sample[0].ready_end_ms-t.enabled_ms:0;
 out[13]=t.count? t.sample[t.count-1].ready_end_ms-t.sample[0].ready_end_ms:0;
 out[14]=t.completed_ms-t.started_ms;out[15]=t.initial_interrupt[3];
 out[16]=m.ready_count;out[17]=t.polls;
 out[18]=t.count?t.sample[0].adc_end_ms-t.sample[0].ready_begin_ms:0;
 out[19]=m.dropped_effective;
}
""".replace(r'\"', '"'))

        src=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        cycle_code=r"""
#include <linux/errno.h>
#include "sm5714-stage2.h"
#define lockdep_assert_held(p) ((void)(p))
#define READ_ONCE(x) (x)
#define POWER_SUPPLY_HEALTH_GOOD 1
#define dev_err(...) ((void)0)
"""+function(src,'struct sm5440_timing_context {')+r""";
struct sm5440_direct {struct regmap *regmap;int io_lock;void *dev;bool stopped,fault;
 struct sm5440_timing_context timing;};
static struct sm5440_direct *cycle_sm;
static int held,facts_calls;
static void mutex_lock(int *p){(void)p;held++;}
static void mutex_unlock(int *p){(void)p;held--;}
static void msleep(unsigned int ms){
 if(held)cycle_sm->regmap->unsafe++;fake_clock+=ms;
 if(cycle_sm->regmap->scenario==11&&cycle_sm->regmap->enabled_ms&&
    fake_clock>cycle_sm->regmap->enabled_ms+100)cycle_sm->stopped=true;
}
static int sm5440_timing_facts(struct sm5714_pd_snapshot *source,
 struct sm5714_pack_snapshot *pack){
 facts_calls++;if(held)cycle_sm->regmap->unsafe++;int scenario=cycle_sm->regmap->scenario;
 if(scenario==40&&facts_calls<3)return -EAGAIN;
 if(scenario==41&&facts_calls<3)return -EBUSY;
 if(scenario==42)return -EIO;
 if(scenario==43)return -EAGAIN;
 memset(source,0,sizeof(*source));memset(pack,0,sizeof(*pack));
 source->instance=1;source->source_generation=2;source->budget_generation=3;
 source->budget_mv=5000;source->budget_ma=1800;
 pack->instance=4;pack->state_generation=5;
 if(facts_calls>1&&scenario==44)source->source_generation++;
 if(facts_calls>1&&scenario==45)pack->state_generation++;
 return 0;
}
"""+function(src,'static bool sm5440_timing_same_source(')+function(src,'static int sm5440_off(')+function(src,'static int sm5440_adc_rearm(')+function(src,'static void sm5440_timing_cycle(')+r"""
void exercise_cycle(int scenario,int *out){
 struct regmap m={0};struct sm5440_direct sm={0};sm.regmap=&m;cycle_sm=&sm;
 fake_clock=1000;held=facts_calls=0;m.scenario=scenario;m.cycle=1;
 m.reg[0x2b]=0x11;m.reg[0x1c]=0x88;m.reg[0x1d]=0x41;m.reg[0x0a]=32;
 raw13(m.reg+0x1e,904);raw13(m.reg+0x27,3504);
 if(scenario==46)sm.stopped=true;
 sm5440_timing_cycle(&sm);
 out[0]=sm.timing.acquisition.error;out[1]=sm.timing.acquisition.cleanup_error;
 out[2]=sm.timing.acquisition.count;out[3]=sm.timing.acquisition.restored;
 out[4]=m.unsafe;out[5]=held;out[6]=m.enables;out[7]=m.off_writes;
 out[8]=sm.timing.off_error;out[9]=sm.timing.off_attempted;
 out[10]=sm.fault;out[11]=sm.timing.first_readiness_error;
 out[12]=sm.timing.readiness_checks;out[13]=facts_calls;out[14]=m.writes;
 out[15]=m.reg[0x10]&12;out[16]=m.reg[0x1c];out[17]=m.reg[0x1d];
 out[18]=sm.timing.exit_error;out[19]=sm.timing.admission_error;
}
"""
        mock=p/'mock.c';mock.write_text(mock.read_text()+cycle_code)
        lib = p / 'timing.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-misleading-indentation', '-D__KERNEL__', '-I'+str(p),
                        '-I'+str(ROOT/'kernel/drivers'), str(p/'mock.c'),
                        str(ROOT/'kernel/drivers/sm5440-timing.c'), '-o', str(lib)], check=True)
        cls.lib=ctypes.CDLL(str(lib))
        cls.lib.exercise.argtypes=[ctypes.c_int]*4+[ctypes.POINTER(ctypes.c_int)]

    def case(self, scenario=0, fail=0, uncertain=0, drop=0):
        out=(ctypes.c_int*20)();self.lib.exercise(scenario,fail,uncertain,drop,out)
        r=list(out);self.assertEqual(r[5],0,'non-ADC write or early enable');return r

    def cycle(self, scenario=0):
        out=(ctypes.c_int*20)();self.lib.exercise_cycle(scenario,out)
        r=list(out);self.assertEqual(r[4:6],[0,0],'unsafe write or held wait lock');return r

    def test_real_cycle_success_readiness_and_single_converter(self):
        for scenario in [0,40,41]:
            r=self.cycle(scenario);self.assertEqual(r[:7],[0,0,8,1,0,0,1])
            self.assertEqual(r[7:11],[0,0,0,0]);self.assertEqual(r[16:18],[0x88,0x41])
            self.assertEqual(r[12],1 if scenario==0 else 3)
            self.assertEqual(r[11],0 if scenario==0 else -errno.EAGAIN if scenario==40 else -errno.EBUSY)

    def test_real_cycle_fault_and_cancel_verify_off_before_restore(self):
        for scenario in [2,3,6,7,11]:
            r=self.cycle(scenario);self.assertLess(r[0],0)
            self.assertEqual(r[7:11],[1,0,1,1]);self.assertEqual(r[15],0)
            self.assertEqual(r[16:18],[0x88,0x41]);self.assertEqual(r[3],1)

    def test_real_cycle_admission_failure_has_no_hardware_writes(self):
        for scenario in [42,43,46]:
            r=self.cycle(scenario);self.assertLess(r[0],0)
            self.assertEqual(r[6:10],[0,0,0,0]);self.assertEqual(r[14],0)
            if scenario==43:self.assertEqual(r[12],20)

    def test_real_cycle_changed_source_or_pack_refuses_after_cleanup(self):
        for scenario in [44,45]:
            r=self.cycle(scenario);self.assertEqual(r[0],-errno.ESTALE)
            self.assertEqual(r[2:4],[8,1]);self.assertEqual(r[18],-errno.ESTALE)
            self.assertEqual(r[10],1);self.assertEqual(r[16:18],[0x88,0x41])

    def test_eight_new_ready_events_and_exact_restore(self):
        r=self.case();self.assertEqual(r[:7],[0,0,0,8,1,0,1])
        self.assertEqual(r[8:10],[0x88,0x41]);self.assertGreaterEqual(r[11],50)
        self.assertGreaterEqual(r[12],125);self.assertEqual(r[15],1)
        self.assertEqual(r[16],8);self.assertGreater(r[13],7*120)
        self.assertLess(r[14],2000);self.assertGreater(r[18],0)

    def test_stale_ready_does_not_count_without_new_event(self):
        r=self.case(1);self.assertEqual(r[0],-errno.ETIMEDOUT)
        self.assertEqual(r[3],0);self.assertEqual(r[4],1);self.assertEqual(r[15],1)

    def test_fault_mode_source_control_and_channel_change_stop(self):
        for scenario in [2,3,4,5,6,7,24]:
            with self.subTest(scenario=scenario):
                r=self.case(scenario);self.assertLess(r[0],0);self.assertEqual(r[3],0)
                if scenario!=3:self.assertEqual(r[8]&1,0)

    def test_active_adc_wrong_chip_or_pump_admission_has_no_writes(self):
        for scenario in [8,9,10]:
            r=self.case(scenario);self.assertLess(r[0],0);self.assertEqual(r[10],0)

    def test_cancel_clock_rollback_and_total_deadline(self):
        for scenario, expected in [(11,errno.ESHUTDOWN),(13,errno.ESTALE),(14,errno.ETIMEDOUT)]:
            r=self.case(scenario);self.assertEqual(r[0],-expected);self.assertEqual(r[8]&1,0)
            self.assertEqual(r[4],1)

    def test_next_ready_missing_is_bounded(self):
        r=self.case(12);self.assertEqual(r[0],-errno.ETIMEDOUT)
        self.assertEqual(r[3],1);self.assertEqual(r[4],1)

    def test_physical_limits_reject_voltage_current_and_die_temperature(self):
        for scenario in [20,21,22,23]:
            r=self.case(scenario);self.assertEqual(r[0],-errno.ERANGE)
            self.assertEqual(r[3],0);self.assertEqual(r[8]&1,0);self.assertEqual(r[4],1)

    def test_every_single_transfer_error_refuses_and_no_hidden_second_finish(self):
        total=self.case()[7]
        for fail in range(1,total+1):
            with self.subTest(transfer=fail):
                r=self.case(fail=fail);self.assertLess(r[0],0)
                self.assertTrue(r[1] or r[2]);self.assertLessEqual(r[6],1)

    def test_uncertain_enable_write_is_cleaned_without_retrying_begin(self):
        for fail in range(1,30):
            r=self.case(fail=fail,uncertain=1)
            self.assertLess(r[0],0);self.assertLessEqual(r[6],1)
            if r[4]:self.assertEqual(r[8:10],[0x88,0x41])

    def test_write_readback_mismatch_is_not_success(self):
        witnessed=0
        for drop in range(1,self.case()[7]+1):
            r=self.case(drop=drop)
            if r[19]:
                witnessed+=1;self.assertLess(r[0],0,'ignored changed-register write must refuse')
            if not r[0]:self.assertEqual(r[8:10],[0x88,0x41])
        self.assertGreaterEqual(witnessed,5)


class TimingNativeFactsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        p=Path(cls.tmp.name);(p/'linux').mkdir()
        (p/'linux/types.h').write_text('#include <stdint.h>\n#include <stdbool.h>\ntypedef uint64_t u64;typedef uint32_t u32;\n')
        src=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        code=r"""
#include <string.h>
#include <errno.h>
#include "sm5714-stage2.h"
#define POWER_SUPPLY_HEALTH_GOOD 1
static int scenario,calls;
static u64 ktime_get_boottime(void){return 1100;}
#define ktime_to_ms(v) (v)
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *p){
 memset(p,0,sizeof(*p));calls++;
 if((scenario==1&&calls==1)||(scenario==3&&calls==3))return -EIO;
 p->instance=1;p->source_generation=2;p->budget_generation=3;
 p->started_ms=1000;p->completed_ms=1001;p->online=1;
 p->charge_requested=true;p->budget_mv=5000;p->budget_ma=1800;
 if(scenario==32||scenario==33){p->budget_mv=9000;p->budget_ma=scenario==32?1500:1501;}
 if(calls==3){
  if(scenario==4)p->instance++;if(scenario==5)p->source_generation++;
  if(scenario==6)p->budget_generation++;if(scenario==7)p->online=2;
  if(scenario==31)p->completed_ms=1101;
 }
 if(scenario==8)p->pps_contract=true;if(scenario==9)p->budget_mv=12000;
 if(scenario==10)p->budget_ma=0;if(scenario==11)p->budget_ma=1801;
 if(scenario==28)p->started_ms=0;if(scenario==29)p->completed_ms=1101;
 return 0;
}
int sm5714_battery_read_pack(u64 lease,struct sm5714_pack_snapshot *p){
 memset(p,0,sizeof(*p));calls++;if(lease)return -EPERM;if(scenario==2)return -EIO;
 p->instance=4;p->state_generation=5;p->started_ms=1001;p->completed_ms=1002;
 p->battery_present=p->attached=p->thermal_normal=p->typec_owned=p->typec_charge=true;
 p->capacity=9;p->voltage_uv=3700000;p->current_ua=-405000;p->pack_decic=307;
 p->health=POWER_SUPPLY_HEALTH_GOOD;p->typec_mv=5000;p->typec_ma=1800;
 if(scenario==32||scenario==33){p->typec_mv=9000;p->typec_ma=scenario==32?1500:1501;}
 if(scenario==12)p->battery_present=false;if(scenario==13)p->attached=false;
 if(scenario==14)p->typec_owned=false;if(scenario==15)p->typec_charge=false;
 if(scenario==16)p->pps_contract=true;if(scenario==17)p->health=0;
 if(scenario==18)p->capacity=4;if(scenario==19)p->capacity=80;
 if(scenario==20)p->voltage_uv=3499999;if(scenario==21)p->voltage_uv=4300000;
 if(scenario==22)p->pack_decic=199;if(scenario==23)p->pack_decic=380;
 if(scenario==24)p->switching_lease=1;if(scenario==25)p->instance=0;
 if(scenario==26)p->state_generation=0;if(scenario==27)p->typec_ma=500;
 if(scenario==30)p->started_ms=500;
 return 0;
}
"""+function(src,'static bool sm5440_timing_same_source(')+function(src,'static int sm5440_timing_facts(')+r"""
int exercise(int n,int *out){struct sm5714_pd_snapshot s;struct sm5714_pack_snapshot p;
 scenario=n;calls=0;int ret=sm5440_timing_facts(&s,&p);out[0]=calls;
 out[1]=p.current_ua;return ret;}
"""
        c=p/'facts.c';c.write_text(code);lib=p/'facts.so'
        subprocess.run(['cc','-shared','-fPIC','-Wall','-Wextra','-Werror','-Wno-misleading-indentation',
                        '-I'+str(p),'-I'+str(ROOT/'kernel/drivers'),str(c),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.exercise.argtypes=[ctypes.c_int,ctypes.POINTER(ctypes.c_int)]

    def test_native_fixed5_and_fixed9_and_signed_pack_current(self):
        for n in [0,32]:
            out=(ctypes.c_int*2)();self.assertEqual(self.lib.exercise(n,out),0)
            self.assertEqual(list(out),[3,-405000])

    def test_every_native_read_error_and_epoch_health_limit_time_refusal(self):
        for n in list(range(1,32))+[33]:
            with self.subTest(scenario=n):
                out=(ctypes.c_int*2)();self.assertLess(self.lib.exercise(n,out),0)
                self.assertLessEqual(out[0],3)


class TimingIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        spec=importlib.util.spec_from_file_location('timing_gate',ROOT/'scripts/verify-x710-charging-profile.py')
        cls.gate=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.gate)

    def test_profile_is_exclusive_and_not_default_enabled(self):
        cfg=self.gate.BASE.read_text()+'\nCONFIG_CHARGER_SM5440_DIRECT=y\nCONFIG_SM5440_ADC_TIMING_TEST=y\n'
        self.assertTrue(self.gate.verify(cfg,profile='sm5440-adc-timing')['valid'])
        for profile in ['sm5440-passive','sm5440-policy-offline','sm5440-adc-condition']:
            self.assertFalse(self.gate.verify(cfg,profile=profile)['valid'])
        for extra in ['CONFIG_SM5440_ADC_CONDITION_TEST=y','CONFIG_X710_CHARGING_POLICY=y']:
            self.assertFalse(self.gate.verify(cfg+'\n'+extra+'\n',profile='sm5440-adc-timing')['valid'])
        self.assertFalse(self.gate.STAGE2.verify(cfg)['valid'])
        for name in ['gts9wifi-mainline.fragment','gts9wifi-sm5440-passive.fragment','gts9wifi-sm5440-policy-offline.fragment']:
            self.assertNotIn('CONFIG_SM5440_ADC_TIMING_TEST=y',(ROOT/'kernel/config'/name).read_text())

    def test_no_source_mutator_or_pump_activation_in_timing_cycle(self):
        body=function(self.source,'static void sm5440_timing_cycle(')
        for forbidden in ['sm5714_pd_request_pps','sm5714_pd_restore_fixed','switching_acquire',
                          'switching_release','set_pd_contract','ENHIZ','regmap_write','regmap_update_bits']:
            self.assertNotIn(forbidden,body)
        self.assertIn('sm5440_timing_finish(',body)
        self.assertLess(body.index('c.off_error = sm5440_off(sm);'),body.index('sm5440_timing_finish('))
        self.assertIn('msleep(5);\n\t\tmutex_lock(',body)

    def test_frozen_converter_and_active_budget_unchanged(self):
        old=subprocess.check_output(['git','show','809617ff:kernel/drivers/sm5440-direct.c'],cwd=ROOT,text=True)
        for name in ['static int sm5440_sample_once(', 'static int sm5440_quiesce(',
                     'int sm5440_passive_request_fresh(', 'int sm5440_passive_observe(']:
            self.assertEqual(function(old,name),function(self.source,name))
        header=(ROOT/'kernel/drivers/sm5440-hw.h').read_text()
        self.assertIn('#define SM5440_FRESH_REQUEST_MS 100U',header)
        poll=function(self.source,'static void sm5440_poll(')
        self.assertLess(poll.index('!sm->startup_confirmations'),poll.index('sm5440_timing_cycle(sm);'))
        self.assertIn('return; /* One experiment per bind;',poll)

    def test_no_companion_publication_or_resume_rearm(self):
        body=function(self.source,'static int sm5440_publish(')
        part=body.split('#ifdef CONFIG_SM5440_ADC_TIMING_TEST')[1].split('#else')[0]
        self.assertIn('return 0;',part);self.assertNotIn('sm5440_companion =',part)
        resume=function(self.source,'static int sm5440_resume(')
        self.assertIn('if (sm->timing.attempted)\n\t\treturn -EOPNOTSUPP;',resume)

    def test_cached_snapshot_read_performs_no_IO(self):
        body=function(self.source,'static void sm5440_timing_show(')
        self.assertNotIn('regmap_',body);self.assertNotIn('sm5714_',body)
        self.assertIn('i <= t->count',body)  # retain partial failure slot


if __name__=='__main__':
    unittest.main()
