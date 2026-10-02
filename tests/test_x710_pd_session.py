"""Execute the actual kernel consumer with threaded PM and faulted providers.

Native backend, battery I2C and ADC acquisition are tested by their own suites.
These mocked physical facts are not hardware acceptance or protection proof.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class PdSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        directory = Path(cls.tmp.name)
        (directory/'linux').mkdir()
        (directory/'linux/types.h').write_text('/* host types precede real headers */\n')
        source = (ROOT/'kernel/drivers/x710-pd-session.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define min(a,b) ((a)<(b)?(a):(b))
#define ARRAY_SIZE(a) (sizeof(a)/sizeof((a)[0]))
#define PD_MAX_PAYLOAD 7
#define PDO_TYPE_FIXED 0
static unsigned int rdo_index(u32 p){return (p>>28)&7;}
#define RDO_CAP_MISMATCH BIT(26)
#define RDO_USB_COMM BIT(25)
#define RDO_NO_SUSPEND BIT(24)
#define RDO_PROG(i,v,c,f) (((u32)(i)<<28)|(((v)/20)<<9)|((c)/50)|(f))
static unsigned int pdo_type(u32 p){return p>>30;}
static unsigned int pdo_fixed_voltage(u32 p){return ((p>>10)&1023)*50;}
static unsigned int pdo_max_current(u32 p){return (p&1023)*10;}
static unsigned int rdo_op_current(u32 p){return ((p>>10)&1023)*10;}
static unsigned int rdo_max_current(u32 p){return (p&1023)*10;}
typedef atomic_int atomic_t;
#define ATOMIC_INIT(v) (v)
#define atomic_read(p) atomic_load(p)
#define atomic_set(p,v) atomic_store(p,v)
struct mutex{pthread_mutex_t value;};
#define DEFINE_MUTEX(n) struct mutex n={PTHREAD_MUTEX_INITIALIZER}
static _Thread_local int held;
static void mutex_lock(struct mutex *m){pthread_mutex_lock(&m->value);held++;}
static void mutex_unlock(struct mutex *m){held--;pthread_mutex_unlock(&m->value);}
static bool mutex_trylock(struct mutex *m){if(pthread_mutex_trylock(&m->value))return false;held++;return true;}
#define __init
#define PM_SUSPEND_PREPARE 1
#define PM_HIBERNATION_PREPARE 2
#define PM_RESTORE_PREPARE 3
#define PM_POST_SUSPEND 4
#define PM_POST_HIBERNATION 5
#define PM_POST_RESTORE 6
#define NOTIFY_OK 1
#define NOTIFY_BAD 2
#define NOTIFY_DONE 0
struct notifier_block{int (*notifier_call)(struct notifier_block *,unsigned long,void *);};
static int init_error;
static int register_pm_notifier(struct notifier_block *n){(void)n;return init_error;}
static u64 clock_ms;
static u64 ktime_get_boottime(void){return clock_ms*1000000;}
#define ktime_to_ms(n) ((n)/1000000)
enum power_supply_property {POWER_SUPPLY_PROP_PRESENT,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_CAPACITY,POWER_SUPPLY_PROP_VOLTAGE_NOW,POWER_SUPPLY_PROP_TEMP};
union power_supply_propval{int intval;};
struct power_supply{int unused;};
#define POWER_SUPPLY_HEALTH_GOOD 1
''' + '#include "'+str(ROOT/'kernel/drivers/sm5714-pd-policy.h')+'"\n'
        for file, marker in [('sm5440-hw.h', 'struct sm5440_passive_measurement {'),
                             ('x710-pd-session.h', 'struct x710_pd_session_result {')]:
            code += function((ROOT/'kernel/drivers'/file).read_text(), marker)+';\n'
        code += r'''
#define SM5440_FRESH_REQUEST_MS 100U
static DEFINE_MUTEX(x710_session_lock);
static atomic_t x710_session_quiescing;
static bool x710_session_unresolved;
static struct power_supply battery;
static int pack[5],gets,puts,reads,measures,acquires,pps_calls,fixed_calls,releases;
static int event_count,fail_event,cancel_event,change_event,scenario,errors;
static u64 source_epoch,source_instance;
static unsigned int actual_mv;
static bool lease_live,logical_pps;
static char trace[200];static int trace_count;
static pthread_mutex_t barrier=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t condition=PTHREAD_COND_INITIALIZER;
static bool entered,released;static int reader_ret,pm_ret;
static int step(char kind){
 if(held!=1)errors++;trace[trace_count++]=kind;event_count++;clock_ms+=2;
 if(event_count==cancel_event)atomic_set(&x710_session_quiescing,1);
 if(event_count==change_event){source_epoch++;lease_live=false;}
 return event_count==fail_event?-EIO:0;
}
static struct power_supply *power_supply_get_by_name(const char *name){
 gets++;if(strcmp(name,"sm5714-battery"))errors++;return scenario==1?NULL:&battery;
}
static int power_supply_get_property(struct power_supply *p,enum power_supply_property n,union power_supply_propval *v){
 if(p!=&battery||n<0||n>4)errors++;int ret=step('b');if(ret)return ret;
 if(scenario==21)clock_ms+=110;v->intval=pack[n];return 0;
}
static void power_supply_put(struct power_supply *p){if(p!=&battery)errors++;puts++;}
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *out){
 reads++;int ret=step('r');if(ret)return ret;if(logical_pps)return -EOPNOTSUPP;
 memset(out,0,sizeof(*out));out->instance=source_instance;out->source_generation=source_epoch;
 out->budget_generation=3;out->budget_mv=scenario==2?5000:9000;out->budget_ma=1500;
 out->nr_source_pdos=scenario==3?0:3;out->source_pdos[0]=(100U<<10)|300;
 out->source_pdos[1]=(180U<<10)|300;out->source_pdos[2]=(3U<<30)|(110U<<17)|(50U<<8)|60;
 if(scenario==4)out->source_pdos[2]=(3U<<30)|(90U<<17)|(90U<<8)|20;
 if(scenario==5)out->nr_source_pdos=8;
 return 0;
}
int sm5440_passive_request_fresh(struct sm5440_passive_measurement *out){
 measures++;int ret=step('m');if(ret)return ret;memset(out,0,sizeof(*out));
 if(scenario==22)return -ETIMEDOUT;if(scenario==23)return -EIO;
 out->observed_ms=clock_ms-10;out->vbus_uv=actual_mv*1000;out->vbat_uv=3900000;
 out->die_decic=300;out->online=true;
 if(scenario==6)out->observed_ms=clock_ms-101;
 if(scenario==7)out->observed_ms=clock_ms+1;
 if(scenario==8)out->observed_ms=0;
 if(scenario==9)out->online=false;
 if(scenario==10)out->ibus_ua=625;
 if(scenario==11)out->vbat_uv=3499999;
 if(scenario==12)out->vbat_uv=4300000;
 if(scenario==13)out->die_decic=550;
 if(scenario==14)out->vbus_uv=10600000;
 if(scenario==15&&logical_pps)out->vbus_uv+=100001;
 if(scenario==16&&measures==5)out->vbus_uv+=100001;
 return 0;
}
int sm5714_battery_switching_acquire(u64 *lease){
 acquires++;int ret=step('a');*lease=7;lease_live=!ret;return ret;
}
int sm5714_pd_request_pps(u64 instance,u64 epoch,u64 lease,unsigned int mv,unsigned int ma,struct sm5714_pd_snapshot *out){
 pps_calls++;int ret=step('p');(void)ma;if(ret)return ret;
 if(instance!=source_instance||epoch!=source_epoch||lease!=7||!lease_live)return -ESTALE;
 if(scenario==24){
  pthread_mutex_lock(&barrier);entered=true;pthread_cond_broadcast(&condition);
  while(!released)pthread_cond_wait(&condition,&barrier);pthread_mutex_unlock(&barrier);
 }
 logical_pps=true;actual_mv=mv;memset(out,0,sizeof(*out));out->pps_contract=true;
 out->instance=instance;out->source_generation=epoch;out->online=2;
 out->budget_mv=mv;out->budget_ma=ma;
 if(scenario==25)return -ETIMEDOUT;
 if(scenario==26){logical_pps=false;actual_mv=9000;return -ETIMEDOUT;}
 if(scenario==27)out->source_generation++;
 return 0;
}
int sm5714_pd_restore_fixed(u64 instance,u64 epoch,u64 lease,struct sm5714_pd_snapshot *out){
 fixed_calls++;int ret=step('f');if(ret)return ret;
 if(instance!=source_instance||epoch!=source_epoch||lease!=7||!lease_live)return -ESTALE;
 logical_pps=false;actual_mv=9000;memset(out,0,sizeof(*out));out->budget_mv=9000;
 if(scenario==17)out->budget_mv=5000;return 0;
}
int sm5714_pd_release_fixed(u64 instance,u64 epoch,u64 lease,const struct sm5714_fixed_proof *proof){
 releases++;int ret=step('l');if(ret)return ret;
 if(instance!=source_instance||epoch!=source_epoch||lease!=7||!lease_live||logical_pps)return -ESTALE;
 if(!proof->pump_off||proof->ibus_ua||clock_ms<proof->observed_ms||clock_ms-proof->observed_ms>100)return -ESTALE;
 lease_live=false;return 0;
}
'''
        markers = ['static u64 x710_session_now(', 'static int x710_session_pack(',
                   'static int x710_session_measure(', 'static bool x710_session_target(',
                   'static int x710_session_same_fixed(', 'static int x710_session_cleanup(',
                   'int x710_pd_off_roundtrip(', 'static int x710_session_pm(']
        for marker in markers:
            code += function(source, marker)+'\n'
        code += 'static struct notifier_block x710_session_notifier={.notifier_call=x710_session_pm};\n'
        code += function(source, 'static int __init x710_session_init(')+'\n'
        code += r'''
static struct x710_pd_session_result result;
static void *reader(void *unused){(void)unused;reader_ret=x710_pd_off_roundtrip(8800,1800,&result);return NULL;}
static void *pm_prepare(void *unused){(void)unused;pm_ret=x710_session_pm(NULL,PM_SUSPEND_PREPARE,NULL);return NULL;}
int exercise(int mode,int failure,int cancel,int change,long long *out){
 scenario=mode;fail_event=failure;cancel_event=cancel;change_event=change;
 gets=puts=reads=measures=acquires=pps_calls=fixed_calls=releases=event_count=errors=trace_count=0;
 memset(trace,0,sizeof(trace));clock_ms=1000;source_epoch=2;source_instance=1;actual_mv=9000;
 logical_pps=lease_live=x710_session_unresolved=false;atomic_set(&x710_session_quiescing,0);
 pack[0]=1;pack[1]=1;pack[2]=50;pack[3]=3900000;pack[4]=300;
 if(mode>=30&&mode<40){int slot=(mode-30)/2;pack[slot]=(mode%2)?10000000:-1;}
 if(mode==18)atomic_set(&x710_session_quiescing,1);
 if(mode==19)x710_session_unresolved=true;
 unsigned int mv=8800,ma=1800;
 if(mode==40)mv=11000;if(mode==41)mv=8801;if(mode==42)ma=1850;if(mode==43)ma=1799;
 int ret;
 if(mode==24){
  pthread_t a,b;entered=released=false;pthread_create(&a,NULL,reader,NULL);
  pthread_mutex_lock(&barrier);while(!entered)pthread_cond_wait(&condition,&barrier);pthread_mutex_unlock(&barrier);
  struct x710_pd_session_result other;int second=x710_pd_off_roundtrip(8800,1800,&other);if(second!=-EBUSY)errors++;
  pthread_create(&b,NULL,pm_prepare,NULL);int loops=0;
  while(!atomic_read(&x710_session_quiescing)&&loops++<2000)usleep(1000);
  if(!atomic_read(&x710_session_quiescing))errors++;
  pthread_mutex_lock(&barrier);released=true;pthread_cond_broadcast(&condition);pthread_mutex_unlock(&barrier);
  pthread_join(a,NULL);pthread_join(b,NULL);if(pm_ret!=NOTIFY_OK)errors++;ret=reader_ret;
 }else{
  memset(&result,0,sizeof(result));ret=x710_pd_off_roundtrip(mv,ma,mode==44?NULL:&result);
 }
 out[0]=errors;out[1]=gets;out[2]=puts;out[3]=reads;out[4]=measures;out[5]=acquires;
 out[6]=pps_calls;out[7]=fixed_calls;out[8]=releases;out[9]=result.error;
 out[10]=result.cleanup_error;out[11]=result.switching_released;out[12]=x710_session_unresolved;
 out[13]=event_count;out[14]=logical_pps;out[15]=held;
 return ret;
}
int pm_case(int action,int unresolved,int initfail,long long *out){
 init_error=initfail;x710_session_unresolved=unresolved;atomic_set(&x710_session_quiescing,1);
 int ret=x710_session_init();out[0]=atomic_read(&x710_session_quiescing);if(ret)return ret;
 ret=x710_session_pm(NULL,action,NULL);out[1]=atomic_read(&x710_session_quiescing);out[2]=x710_session_unresolved;return ret;
}
'''
        c = directory/'session.c'
        c.write_text(code)
        lib = c.with_suffix('.so')
        subprocess.run(['cc', '-shared', '-fPIC', '-pthread', '-Wall', '-Werror',
                        '-Wno-misleading-indentation', '-I'+str(directory),
                        str(c), '-o', str(lib)], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.exercise.argtypes = [ctypes.c_int]*4+[ctypes.POINTER(ctypes.c_longlong)]
        cls.lib.pm_case.argtypes = [ctypes.c_int]*3+[ctypes.POINTER(ctypes.c_longlong)]

    def case(self, mode=0, failure=0, cancel=0, change=0):
        out = (ctypes.c_longlong*16)()
        ret = self.lib.exercise(mode, failure, cancel, change, out)
        self.assertEqual(out[0], 0)
        self.assertEqual(out[15], 0)
        if out[1] and mode != 1:
            self.assertEqual(out[1], out[2])
        self.assertLessEqual(out[6:9][1], 1)  # one consumer cleanup, never retry
        return ret, list(out)

    def test_real_consumer_roundtrip_and_checked_release(self):
        ret, out = self.case()
        self.assertEqual(ret, 0)
        self.assertEqual(out[5:9], [1, 1, 1, 1])
        self.assertEqual(out[9:13], [0, 0, 1, 0])
        self.assertEqual(out[14], 0)

    def test_each_provider_failure_preserves_error_and_stops(self):
        _, clean = self.case()
        for index in range(1, clean[13]+1):
            with self.subTest(event=index):
                ret, out = self.case(failure=index)
                self.assertEqual(ret, -errno.EIO)
                self.assertLessEqual(out[6], 1)
                if out[12]:
                    self.assertFalse(out[11])

    def test_preflight_unsupported_source_never_acquires(self):
        for mode in [1, 2, 3, 4, 5]:
            with self.subTest(mode=mode):
                ret, out = self.case(mode)
                self.assertNotEqual(ret, 0)
                self.assertEqual(out[5:9], [0]*4)

    def test_stale_future_zero_adc_refused_before_ownership(self):
        for mode in [6, 7, 8]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -errno.ESTALE)
            self.assertEqual(out[5:9], [0]*4)

    def test_physical_off_voltage_current_die_pack_refusals(self):
        for mode in [9, 10, 11, 12, 13, 14]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -errno.ERANGE)
            self.assertEqual(out[5:9], [0]*4)

    def test_pps_physical_mismatch_is_not_logical_success(self):
        ret, out = self.case(15)
        self.assertEqual(ret, -errno.ERANGE)
        self.assertEqual(out[6], 1)
        self.assertTrue(out[11])

    def test_fixed_physical_mismatch_does_not_release(self):
        ret, out = self.case(16)
        self.assertEqual(ret, -errno.ERANGE)
        self.assertEqual(out[8], 0)
        self.assertEqual(out[12], 1)

    def test_unexpected_fixed_fallback_voltage_keeps_inhibited(self):
        ret, out = self.case(17)
        self.assertEqual(ret, -errno.ERANGE)
        self.assertEqual(out[8], 0)

    def test_quiescing_and_unresolved_state_do_not_start(self):
        for mode in [18, 19]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -errno.ESHUTDOWN)
            self.assertEqual(out[5:9], [0]*4)

    def test_slow_pack_acquisition_refuses_oldest_time(self):
        ret, out = self.case(21)
        self.assertEqual(ret, -errno.ESTALE)
        self.assertEqual(out[5], 0)

    def test_existing_adc_timeout_and_fault_are_not_waived(self):
        for mode, expected in [(22, errno.ETIMEDOUT), (23, errno.EIO)]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -expected)
            self.assertEqual(out[5], 0)

    def test_real_mutex_serialization_and_pm_drain_during_pps(self):
        ret, out = self.case(24)
        self.assertEqual(ret, -errno.ECANCELED)
        self.assertEqual(out[6:9], [1, 1, 1])
        self.assertEqual(out[11:13], [1, 0])

    def test_failed_native_cleanup_is_not_retried_by_consumer(self):
        ret, out = self.case(25)
        self.assertEqual(ret, -errno.ETIMEDOUT)
        self.assertEqual(out[7:9], [0, 0])
        self.assertEqual(out[10], -errno.EOPNOTSUPP)
        self.assertEqual(out[12], 1)

    def test_successful_native_cleanup_can_release_without_hiding_first_error(self):
        ret, out = self.case(26)
        self.assertEqual(ret, -errno.ETIMEDOUT)
        self.assertEqual(out[11:13], [1, 0])

    def test_pps_result_identity_is_checked_before_physical_acceptance(self):
        ret, out = self.case(27)
        self.assertEqual(ret, -errno.ESTALE)
        self.assertEqual(out[11:13], [1, 0])

    def test_pack_property_ranges_fail_closed(self):
        for mode in range(30, 40):
            ret, out = self.case(mode)
            self.assertEqual(ret, -errno.EPERM)
            self.assertEqual(out[5], 0)

    def test_bad_parameters_do_not_touch_providers(self):
        for mode in range(40, 45):
            ret, out = self.case(mode)
            self.assertNotEqual(ret, 0)
            self.assertEqual(out[13], 0)

    def test_cancellation_at_each_operation_never_arms_again(self):
        _, clean = self.case()
        for index in range(1, clean[13]+1):
            ret, out = self.case(cancel=index)
            self.assertLessEqual(out[6], 1)
            if index <= 16:
                self.assertEqual(out[6], 0)

    def test_source_changes_at_each_operation_cannot_release_old_owner(self):
        _, clean = self.case()
        for index in range(2, clean[13]+1):
            ret, out = self.case(change=index)
            self.assertNotEqual(ret, 0)
            self.assertFalse(out[11])

    def test_pm_actions_and_failed_init_do_not_autostart(self):
        for action in [1, 2, 3]:
            for unresolved in [0, 1]:
                out = (ctypes.c_longlong*3)()
                ret = self.lib.pm_case(action, unresolved, 0, out)
                self.assertEqual(ret, 2 if unresolved else 1)
                self.assertEqual(out[1], 1)
        for action in [4, 5, 6]:
            out = (ctypes.c_longlong*3)()
            self.assertEqual(self.lib.pm_case(action, 1, 0, out), 1)
            self.assertEqual(list(out), [0, 0, 1])
        out = (ctypes.c_longlong*3)()
        self.assertEqual(self.lib.pm_case(1, 0, -errno.EIO, out), -errno.EIO)
        self.assertEqual(out[0], 1)

    def test_compiled_only_by_explicit_policy_profile(self):
        patch = (ROOT/'kernel/patches/0014-power-supply-hook-x710-policy-offline.patch').read_text()
        self.assertIn('obj-$(CONFIG_X710_CHARGING_POLICY) += x710-pd-session.o', patch)
        prep = (ROOT/'scripts/prepare-kernel.sh').read_text()
        self.assertIn('x710-pd-session.c) dest="$tree/drivers/power/supply"', prep)
        fragment = (ROOT/'kernel/config/gts9wifi-mainline.fragment').read_text()
        self.assertNotIn('CONFIG_X710_CHARGING_POLICY=y', fragment)
        for forbidden in ['pump_on(', '500U', 'schedule_delayed_work', 'debugfs_create_file', 'module_param']:
            self.assertNotIn(forbidden, (ROOT/'kernel/drivers/x710-pd-session.c').read_text())


if __name__ == '__main__':
    unittest.main()
