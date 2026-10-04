"""Execute native pack acquisition/lifetime C with real locks and sensor faults."""
import ctypes
import errno
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class PackSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / 'kernel/drivers/sm5714-battery.c').read_text()
        cls.source = source
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        path = Path(cls.tmp.name)
        (path / 'linux').mkdir()
        (path / 'linux/types.h').write_text('/* types supplied by fixture */\n')
        definitions = '\n'.join(line for line in source.splitlines()
                                if re.match(r'#define\s+SM5714_(CHG_|FG_|PACK_)', line))
        functions = [
            'static void sm5714_pack_changed_locked(',
            'static void sm5714_revoke_switching_locked(',
            'static int sm5714_chg_update_bits(',
            'static int sm5714_disable_charging(',
            'static int sm5714_fg_read_sram(',
            'static int sm5714_get_capacity(',
            'static int sm5714_get_voltage(',
            'static int sm5714_get_ocv(',
            'static int sm5714_get_current(',
            'static int sm5714_get_temp(struct sm5714_battery *sm, int *val)\n{',
            'static int sm5714_charge_fault(',
            'static int sm5714_get_status(struct sm5714_battery *sm)\n{',
            'static int sm5714_get_present(',
            'static int sm5714_pack_token_locked(',
            'static int sm5714_pack_get(',
            'static void sm5714_pack_put(',
            'int sm5714_battery_read_pack(',
            'static int sm5714_bat_get_property(',
            'static int sm5714_suspend(',
            'static int sm5714_resume(',
            'static void sm5714_unpublish_companion(',
            'static int sm5714_publish_companion(',
        ]
        code = r'''
#include <assert.h>
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;
#define U64_MAX UINT64_MAX
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h)))&((~0U)<<(l)))
#define clamp(v,l,h) ((v)<(l)?(l):((v)>(h)?(h):(v)))
#define DIV_ROUND_CLOSEST(n,d) (((n)+((n)>=0?(d)/2:-(d)/2))/(d))
#define READ_ONCE(v) (v)
#define WRITE_ONCE(v,x) ((v)=(x))
#define dev_dbg(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define dev_err_ratelimited(...) ((void)0)
struct mutex {pthread_mutex_t native;};
#define DEFINE_MUTEX(m) struct mutex m={PTHREAD_MUTEX_INITIALIZER}
typedef atomic_int atomic_t;
#define atomic_set(p,v) atomic_store(p,v)
#define atomic_read(p) atomic_load(p)
#define atomic_inc(p) atomic_fetch_add(p,1)
#define atomic_dec_and_test(p) (atomic_fetch_sub(p,1)==1)
typedef struct {pthread_mutex_t lock;pthread_cond_t event;} wait_queue_head_t;
static atomic_int draining,unpublished;
#define wait_event(w,cond) do {atomic_store(&draining,1);pthread_mutex_lock(&(w).lock);\
 while(!(cond))pthread_cond_wait(&(w).event,&(w).lock);pthread_mutex_unlock(&(w).lock);} while(0)
static void wake_up_all(wait_queue_head_t *w){pthread_mutex_lock(&w->lock);pthread_cond_broadcast(&w->event);pthread_mutex_unlock(&w->lock);}
struct device {void *data;};struct i2c_client {int kind;};struct iio_channel {int unused;};
struct power_supply {void *data;};struct delayed_work {int unused;};
struct power_supply_battery_info {int charge_full_design_uah,voltage_max_design_uv,voltage_min_design_uv;};
#define dev_get_drvdata(d) ((d)->data)
#define cancel_delayed_work_sync(w) ((void)(w))
#define schedule_delayed_work(w,t) ((void)(w),(void)(t))
#define power_supply_get_drvdata(p) ((p)->data)
enum { POWER_SUPPLY_STATUS_DISCHARGING,POWER_SUPPLY_STATUS_FULL,
 POWER_SUPPLY_STATUS_CHARGING,POWER_SUPPLY_STATUS_NOT_CHARGING };
enum {POWER_SUPPLY_HEALTH_UNKNOWN,POWER_SUPPLY_HEALTH_GOOD,
 POWER_SUPPLY_HEALTH_COLD,POWER_SUPPLY_HEALTH_OVERHEAT,
 POWER_SUPPLY_HEALTH_OVERVOLTAGE,POWER_SUPPLY_HEALTH_WATCHDOG_TIMER_EXPIRE};
enum power_supply_property {POWER_SUPPLY_PROP_STATUS,POWER_SUPPLY_PROP_PRESENT,
 POWER_SUPPLY_PROP_TECHNOLOGY,POWER_SUPPLY_PROP_CAPACITY,POWER_SUPPLY_PROP_VOLTAGE_NOW,
 POWER_SUPPLY_PROP_VOLTAGE_AVG,POWER_SUPPLY_PROP_VOLTAGE_OCV,POWER_SUPPLY_PROP_CURRENT_NOW,
 POWER_SUPPLY_PROP_CURRENT_AVG,POWER_SUPPLY_PROP_TEMP,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_CHARGE_FULL_DESIGN,POWER_SUPPLY_PROP_VOLTAGE_MAX_DESIGN,
 POWER_SUPPLY_PROP_VOLTAGE_MIN_DESIGN};
#define POWER_SUPPLY_TECHNOLOGY_LION 1
union power_supply_propval {int intval;};
static _Atomic u64 clock_ms;
static u64 ktime_get_boottime(void){return atomic_load(&clock_ms)*1000000;}
#define ktime_to_ms(v) ((v)/1000000)
''' + definitions + '\n'
        code += function(source, 'enum sm5714_charge_thermal_state {') + ';\n'
        code += function(source, 'struct sm5714_battery {') + ';\n'
        code += '#include "' + str(ROOT / 'kernel/drivers/sm5714-stage2.h') + '"\n'
        code += r'''
static DEFINE_MUTEX(sm5714_companion_lock);
static struct sm5714_battery *sm5714_companion;
static u64 sm5714_pack_issuer;
static bool sm5714_switching_blocked;
static struct sm5714_battery *active;
static _Thread_local int held;
static int busy,scenario,fail_at,temp_mc,raw[256],selector;
static u8 registers[256];
static atomic_int io,errors,charger_writes,selector_writes;
static void mutex_lock(struct mutex *m){
 int bit=m==&sm5714_companion_lock?1:m==&active->chg_lock?2:4;
 if(bit==1)assert(held==0);if(bit==2)assert(held==0||held==1);if(bit==4)assert(held==0);
 pthread_mutex_lock(&m->native);held|=bit;
}
static void mutex_unlock(struct mutex *m){
 int bit=m==&sm5714_companion_lock?1:m==&active->chg_lock?2:4;
 assert(held&bit);held&=~bit;pthread_mutex_unlock(&m->native);
}
static bool mutex_trylock(struct mutex *m){
 int bit=m==&sm5714_companion_lock?1:2;
 if(bit==1)assert(held==0);else assert(held==0||held==1);
 if(busy==bit||pthread_mutex_trylock(&m->native))return false;
 held|=bit;return true;
}
#define lockdep_assert_held(m) assert(held&2)
static int step(void){atomic_fetch_add(&clock_ms,1);return atomic_fetch_add(&io,1)+1==fail_at?-EIO:0;}
static int i2c_smbus_read_byte_data(struct i2c_client *c,u8 reg){
 assert(c==active->chg);assert(held==0||held==2||held==3);
 int ret=step();return ret?ret:registers[reg];
}
static int i2c_smbus_write_byte_data(struct i2c_client *c,u8 reg,u8 value){
 assert(c==active->chg);assert(held==2||held==3);
 atomic_fetch_add(&charger_writes,1);int ret=step();if(!ret)registers[reg]=value;return ret;
}
static int i2c_smbus_write_word_data(struct i2c_client *c,u8 reg,u8 value){
 assert(c==active->fg&&held==4&&reg==SM5714_FG_REG_SRAM_RADDR);
 atomic_fetch_add(&selector_writes,1);int ret=step();if(!ret)selector=value;return ret;
}
static int i2c_smbus_read_word_data(struct i2c_client *c,u8 reg){
 assert(c==active->fg&&held==4&&reg==SM5714_FG_REG_SRAM_RDATA);
 int ret=step();return ret?ret:raw[selector];
}
static pthread_mutex_t barrier=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t event=PTHREAD_COND_INITIALIZER;
static bool entered,released;
static void sm5714_pack_changed_locked(struct sm5714_battery *sm);
static void sm5714_revoke_switching_locked(struct sm5714_battery *sm);
static int sm5714_suspend(struct device *dev);
static int sm5714_resume(struct device *dev);
static int iio_read_channel_processed(struct iio_channel *c,int *value){
 assert(c==active->battery_temp&&held==0);int ret=step();if(ret)return ret;
 if(scenario==20){mutex_lock(&active->chg_lock);active->typec_ma=1450;
  sm5714_pack_changed_locked(active);active->typec_ma=1500;sm5714_pack_changed_locked(active);mutex_unlock(&active->chg_lock);}
 if(scenario==21){mutex_lock(&active->chg_lock);sm5714_revoke_switching_locked(active);
  active->switching_lease=7;mutex_unlock(&active->chg_lock);}
 if(scenario==22){struct device dev={active};assert(sm5714_suspend(&dev)==0);assert(sm5714_resume(&dev)==0);}
 if(scenario==23){mutex_lock(&active->chg_lock);active->typec_fault=true;mutex_unlock(&active->chg_lock);}
 if(scenario==24)busy=2;
 if(scenario==25)registers[SM5714_CHG_REG_STATUS2]|=SM5714_CHG_STATUS2_NOBAT;
 if(scenario==26)registers[SM5714_CHG_REG_STATUS1]=0;
 if(scenario==27)registers[SM5714_CHG_REG_STATUS1]|=SM5714_CHG_STATUS1_VBUS_OVP;
 if(scenario==28)registers[SM5714_CHG_REG_STATUS2]|=SM5714_CHG_STATUS2_WDT_EXPIRED;
 if(scenario==29){mutex_lock(&active->chg_lock);active->thermal_state=SM5714_THERMAL_REDUCED;mutex_unlock(&active->chg_lock);}
 if(scenario==30)atomic_fetch_add(&clock_ms,501);
 if(scenario==31)atomic_store(&clock_ms,900);
 if(scenario==38){pthread_mutex_lock(&barrier);entered=true;pthread_cond_broadcast(&event);
  while(!released)pthread_cond_wait(&event,&barrier);pthread_mutex_unlock(&barrier);}
 *value=temp_mc;return 0;
}
'''
        code += '\n'.join(function(source, name) for name in functions)
        code += r'''
static struct sm5714_pack_snapshot result;
static int reader_ret;
static void *reader(void *unused){(void)unused;reader_ret=sm5714_battery_read_pack(0,&result);return NULL;}
static void *unpublisher(void *sm){sm5714_unpublish_companion(sm);atomic_store(&unpublished,1);return NULL;}
int exercise(int mode,int fault,long long *out){
 struct sm5714_battery sm={0};struct i2c_client chg={0},fg={1};struct iio_channel temp={0};
 sm.chg=&chg;sm.fg=&fg;sm.battery_temp=&temp;active=&sm;
 pthread_mutex_init(&sm.chg_lock.native,NULL);pthread_mutex_init(&sm.sram_lock.native,NULL);
 pthread_mutex_init(&sm.pack_wait.lock,NULL);pthread_cond_init(&sm.pack_wait.event,NULL);
 sm.typec_owned=true;sm.typec_charge=true;sm.typec_mv=9000;sm.typec_ma=1500;
 sm.thermal_state=SM5714_THERMAL_NORMAL;atomic_init(&sm.pack_users,0);
 sm5714_companion=NULL;sm5714_pack_issuer=0;sm5714_switching_blocked=false;
 scenario=mode;busy=fail_at=0;temp_mc=25000;held=0;selector=-1;entered=released=false;
 atomic_store(&clock_ms,1000);atomic_store(&io,0);atomic_store(&errors,0);
 atomic_store(&charger_writes,0);atomic_store(&selector_writes,0);
 atomic_store(&draining,0);atomic_store(&unpublished,0);
 memset(registers,0,sizeof(registers));memset(raw,0,sizeof(raw));
 registers[SM5714_CHG_REG_STATUS1]=SM5714_CHG_STATUS1_VBUS_POK;
 raw[SM5714_FG_SRAM_SOC]=52<<8;raw[SM5714_FG_SRAM_VBAT]=13080;
 raw[SM5714_FG_SRAM_CURRENT]=0x8000|2044;
 assert(sm5714_publish_companion(&sm)==0);u64 lease=0;
 if(mode==1||mode==21||mode==40||mode==41){sm.switching_inhibited=true;sm.switching_lease=7;lease=7;}
 if(mode==1)sm.typec_pps=true;
 if(mode==2)busy=1;if(mode==3)busy=2;
 if(mode==4)sm.suspended=true;
 if(mode==22)registers[SM5714_CHG_REG_CNTL1]=SM5714_CHG_CNTL1_ENQ4FET;
 if(mode==32)raw[SM5714_FG_SRAM_VBAT]=65535;
 if(mode==33)temp_mc=90001;
 if(mode==35)sm5714_companion=NULL;
 if(mode==36)sm.charge_program_fault=true;
 if(mode==37)sm.pack_generation=U64_MAX;
 if(mode==40)lease=8;if(mode==41)lease=0;
 if(mode==43)atomic_store(&clock_ms,0);
 if(mode==44)registers[SM5714_CHG_REG_STATUS1]=0;
 if(mode==45)registers[SM5714_CHG_REG_STATUS2]=SM5714_CHG_STATUS2_NOBAT;
 if(mode==46)registers[SM5714_CHG_REG_STATUS1]|=SM5714_CHG_STATUS1_VBUS_OVP;
 if(mode==47)registers[SM5714_CHG_REG_STATUS2]=SM5714_CHG_STATUS2_WDT_EXPIRED;
 if(mode==48)temp_mc=9000;if(mode==49)temp_mc=50000;
 if(mode==50)temp_mc=-5000;
 if(mode==51)sm.typec_fault=true;
 if(mode==52)sm.pack_removing=true;
 if(mode==53)sm.pack_instance=0;
 fail_at=fault;memset(&result,0xff,sizeof(result));int ret;
 if(mode==38){
  pthread_t a,b;pthread_create(&a,NULL,reader,NULL);
  pthread_mutex_lock(&barrier);while(!entered)pthread_cond_wait(&event,&barrier);pthread_mutex_unlock(&barrier);
  pthread_create(&b,NULL,unpublisher,&sm);
  int loops=0;while(!atomic_load(&draining)&&loops++<2000)usleep(1000);
  if(!atomic_load(&draining)||atomic_load(&unpublished)||atomic_read(&sm.pack_users)!=1)atomic_fetch_add(&errors,1);
  pthread_mutex_lock(&barrier);released=true;pthread_cond_broadcast(&event);pthread_mutex_unlock(&barrier);
  pthread_join(a,NULL);pthread_join(b,NULL);ret=reader_ret;
  if(!atomic_load(&unpublished))atomic_fetch_add(&errors,1);
 }else ret=sm5714_battery_read_pack(lease,mode==54?NULL:&result);
 out[0]=atomic_load(&errors);out[1]=atomic_read(&sm.pack_users);out[2]=held;
 out[3]=atomic_load(&io);out[4]=atomic_load(&charger_writes);out[5]=atomic_load(&selector_writes);
 int nonzero=0;unsigned char *bytes=(void *)&result;for(unsigned int i=0;i<sizeof(result);i++)nonzero+=!!bytes[i];
 out[6]=nonzero;out[7]=result.instance;out[8]=result.state_generation;
 out[9]=result.switching_lease;out[10]=result.started_ms;out[11]=result.completed_ms;
 out[12]=result.capacity;out[13]=result.voltage_uv;out[14]=result.current_ua;out[15]=result.pack_decic;
 out[16]=result.battery_present;out[17]=result.attached;out[18]=result.health;
 out[19]=result.thermal_normal;out[20]=result.pps_contract;
 sm5714_companion=NULL;pthread_mutex_destroy(&sm.chg_lock.native);pthread_mutex_destroy(&sm.sram_lock.native);
 pthread_mutex_destroy(&sm.pack_wait.lock);pthread_cond_destroy(&sm.pack_wait.event);return ret;
}
int presence(int bits,int fault,int *value){
 struct sm5714_battery sm={0};struct i2c_client chg={0};struct power_supply psy={&sm};
 active=&sm;sm.chg=&chg;registers[SM5714_CHG_REG_STATUS2]=bits;held=0;
 fail_at=fault;atomic_store(&io,0);union power_supply_propval val={.intval=-999};
 int ret=sm5714_bat_get_property(&psy,POWER_SUPPLY_PROP_PRESENT,&val);*value=val.intval;return ret;
}
int publication(int fault){
 struct sm5714_battery sm={0};active=&sm;held=0;busy=0;sm5714_companion=NULL;
 pthread_mutex_init(&sm.chg_lock.native,NULL);atomic_init(&sm.pack_users,0);sm5714_pack_issuer=0;
 if(fault==1)sm5714_pack_issuer=U64_MAX;if(fault==2)atomic_store(&sm.pack_users,1);
 int ret=sm5714_publish_companion(&sm);sm5714_companion=NULL;pthread_mutex_destroy(&sm.chg_lock.native);return ret;
}
'''
        c = path / 'pack.c'
        c.write_text(code)
        library = c.with_suffix('.so')
        result = subprocess.run(['cc', '-shared', '-fPIC', '-pthread', '-Wall', '-Wextra',
                                 '-Werror', '-Wno-misleading-indentation', str(c),
                                 '-I', str(path), '-o', str(library)], capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(library))
        cls.lib.exercise.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_longlong)]
        cls.lib.presence.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.POINTER(ctypes.c_int)]

    def case(self, mode=0, fault=0):
        out = (ctypes.c_longlong * 21)()
        ret = self.lib.exercise(mode, fault, out)
        self.assertEqual(list(out[:3]), [0, 0, 0], 'lock/lifetime leak')
        if ret and mode != 54:
            self.assertEqual(out[6], 0, 'error must zero complete output')
        return ret, list(out)

    def test_native_sram_iio_window_and_signed_discharge_current(self):
        ret, out = self.case()
        self.assertEqual(ret, 0)
        self.assertEqual(out[3:6], [11, 0, 3])
        self.assertEqual(out[7:16], [1, 1, 0, 1000, 1011, 52, 3900000, -1000000, 250])
        self.assertEqual(out[16:], [1, 1, 1, 1, 0])

    def test_exact_owned_lease_accepts_pps_without_request_or_control_write(self):
        ret, out = self.case(1)
        self.assertEqual(ret, 0)
        self.assertEqual(out[9], 7)
        self.assertEqual(out[4], 0)
        self.assertEqual(out[20], 1)

    def test_every_native_io_and_thermistor_error_zeroes_output(self):
        for index in range(1, 12):
            with self.subTest(index=index):
                ret, out = self.case(fault=index)
                self.assertEqual(ret, -errno.EIO)
                self.assertEqual(out[3], index)
                self.assertEqual(out[4], 0)

    def test_busy_and_missing_provider_do_no_hardware_io(self):
        for mode, expected in [(2, errno.EBUSY), (3, errno.EBUSY), (35, errno.ENODEV)]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -expected)
            self.assertEqual(out[3], 0)

    def test_admission_pm_fault_removal_and_exhausted_epoch(self):
        for mode, expected in [(4, errno.EAGAIN), (36, errno.EIO), (37, errno.EOVERFLOW),
                               (51, errno.EIO), (52, errno.ESHUTDOWN), (53, errno.EOVERFLOW)]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -expected)
            self.assertEqual(out[3], 0)

    def test_wrong_or_unowned_lease_never_reads_sensor(self):
        for mode in (40, 41):
            ret, out = self.case(mode)
            self.assertEqual(ret, -errno.ESTALE)
            self.assertEqual(out[3], 0)

    def test_budget_and_lease_aba_refused(self):
        for mode in (20, 21):
            self.assertEqual(self.case(mode)[0], -errno.ESTALE)

    def test_actual_suspend_resume_invalidates_pre_pm_acquisition(self):
        ret, out = self.case(22)
        self.assertEqual(ret, -errno.ESTALE)
        self.assertGreater(out[4], 0, 'injected real PM disables Q4')

    def test_fault_and_post_acquisition_busy_refused(self):
        self.assertEqual(self.case(23)[0], -errno.EIO)
        self.assertEqual(self.case(24)[0], -errno.EBUSY)

    def test_live_presence_attach_ovp_and_watchdog_change_refused(self):
        for mode in (25, 26, 27, 28):
            self.assertEqual(self.case(mode)[0], -errno.EAGAIN)

    def test_thermal_state_change_invalidates_bundle(self):
        self.assertEqual(self.case(29)[0], -errno.ESTALE)

    def test_oldest_time_deadline_and_clock_rollback_zero_not_restamped(self):
        for mode in (30, 31, 43):
            self.assertEqual(self.case(mode)[0], -errno.ESTALE)

    def test_invalid_voltage_or_pack_thermistor_refused(self):
        self.assertEqual(self.case(32)[0], -errno.ERANGE)
        self.assertEqual(self.case(33)[0], -errno.ERANGE)

    def test_offline_absent_fault_or_cold_pack_is_not_healthy_charging(self):
        _, offline = self.case(44)
        self.assertEqual(offline[17], 0)
        _, absent = self.case(45)
        self.assertEqual(absent[16:19:2], [0, 0])
        for mode, health in ((46, 4), (47, 5), (48, 2), (49, 3)):
            ret, out = self.case(mode)
            self.assertEqual(ret, 0)
            self.assertEqual(out[18], health)
        _, negative = self.case(50)
        self.assertEqual(negative[15], -50)
        self.assertEqual(negative[18], 2)

    def test_unpublish_drains_real_pinned_iio_before_free(self):
        self.assertEqual(self.case(38)[0], -errno.ESHUTDOWN)

    def test_null_output_does_not_pin_or_read(self):
        ret, out = self.case(54)
        self.assertEqual(ret, -errno.EINVAL)
        self.assertEqual(out[3], 0)

    def test_present_property_uses_vendor_status_and_propagates_io_error(self):
        for status, expected in ((0, 1), (4, 0), (8, 1), (12, 0), (128, 1)):
            value = ctypes.c_int()
            self.assertEqual(self.lib.presence(status, 0, ctypes.byref(value)), 0)
            self.assertEqual(value.value, expected)
        value = ctypes.c_int()
        self.assertEqual(self.lib.presence(0, 1, ctypes.byref(value)), -errno.EIO)
        self.assertEqual(value.value, -999)

    def test_publish_refuses_wrapped_identity_or_undrained_readers(self):
        self.assertEqual(self.lib.publication(1), -errno.EOVERFLOW)
        self.assertEqual(self.lib.publication(2), -errno.EBUSY)

    def test_lifetime_and_core_lock_boundaries_are_actual_source(self):
        unpublish = function(self.source, 'static void sm5714_unpublish_companion(')
        self.assertLess(unpublish.index('sm5714_companion = NULL'), unpublish.index('wait_event'))
        self.assertLess(unpublish.index('mutex_unlock(&sm5714_companion_lock)'), unpublish.index('wait_event'))
        self.assertGreater(unpublish.rindex('mutex_lock(&sm5714_companion_lock)'), unpublish.index('wait_event'))
        put = function(self.source, 'static void sm5714_pack_put(')
        self.assertLess(put.index('mutex_lock'), put.index('atomic_dec_and_test'))
        self.assertLess(put.index('wake_up_all'), put.index('mutex_unlock'))
        observe = function(self.source, 'int sm5714_battery_read_pack(')
        for forbidden in ('sm5714_disable_charging', 'sm5714_configure_charging',
                          'sm5714_set_float_voltage', 'i2c_smbus_write_byte_data', 'set_pd_contract'):
            self.assertNotIn(forbidden, observe)
        probe = function(self.source, 'static int sm5714_probe(')
        self.assertLess(probe.index('init_waitqueue_head'), probe.index('sm5714_unpublish_companion, sm'))
        prop = function(self.source, 'static int sm5714_bat_get_property(')
        self.assertIn('ret = sm5714_get_present(sm);', prop)


if __name__ == '__main__':
    unittest.main()
