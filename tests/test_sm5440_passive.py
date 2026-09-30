"""Real passive driver arithmetic, converter lifetime and mocked I2C errors."""
import ctypes
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class PassiveHardwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        src = (ROOT / "kernel/drivers/sm5440-direct.c").read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <stddef.h>
#include <stdarg.h>
typedef uint8_t u8; typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
#define lockdep_assert_held(x) ((void)(x))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
''' + '\n#include "' + str(ROOT / 'kernel/drivers/sm5440-hw.h') + '"\n'
        code += function(src, 'struct sm5440_sample {') + ';\n'
        code += r'''
struct work_struct {int unused;};
struct delayed_work {struct work_struct work;};
struct sm5440_direct {void *regmap;int io_lock,dev;bool stopped,fault;
 bool initial_sample_done;u8 startup_confirmations;unsigned long startup_deadline;
 struct sm5440_sample startup_sample,sample;struct delayed_work work;struct power_supply *psy;};
struct power_supply {struct sm5440_direct *sm;};
struct device {struct sm5440_direct *sm;};
static struct sm5440_direct *dev_get_drvdata(struct device *d) {return d->sm;}
union power_supply_propval {int intval;};
enum power_supply_property {POWER_SUPPLY_PROP_STATUS,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_ONLINE,POWER_SUPPLY_PROP_VOLTAGE_NOW,POWER_SUPPLY_PROP_CURRENT_NOW,
 POWER_SUPPLY_PROP_TEMP};
#define POWER_SUPPLY_STATUS_NOT_CHARGING 3
#define POWER_SUPPLY_HEALTH_UNSPEC_FAILURE 6
#define POWER_SUPPLY_HEALTH_GOOD 1
#define POWER_SUPPLY_HEALTH_UNKNOWN 0
static unsigned long fake_jiffies=100;
#define jiffies fake_jiffies
#define msecs_to_jiffies(ms) (ms)
#define time_after(a,b) ((long)((b)-(a))<0)
static struct sm5440_direct *power_supply_get_drvdata(struct power_supply *p) {return p->sm;}
static void log_stub(int dev,const char *fmt,...) {(void)dev;(void)fmt;}
#define dev_err log_stub
#define dev_dbg log_stub
#define dev_warn_ratelimited log_stub
#define dev_warn log_stub
#define dev_info log_stub
#define to_delayed_work(w) ((struct delayed_work *)(w))
#define container_of(p,type,member) ((type *)((char *)(p)-offsetof(type,member)))
static int scheduled,changed;
static void cancel_delayed_work_sync(struct delayed_work *w) {(void)w;}
static int schedule_delayed_work(struct delayed_work *w,unsigned long delay) {
 (void)w;(void)delay;scheduled++;return 1;
}
static void power_supply_changed(struct power_supply *p) {(void)p;changed++;}
static u8 regs[64];static int calls,fail_at,never_ready,waits,started,unsafe_writes;
static struct sm5440_direct *current;
static int step(void) {calls++;return calls==fail_at?-EIO:0;}
static int regmap_read(void *m,unsigned int r,unsigned int *v) {
 (void)m;int ret=step();if(ret)return ret;*v=regs[r];
 if(r==SM5440_INT4)regs[r]=0;
 return 0;
}
static int regmap_bulk_read(void *m,unsigned int r,void *v,unsigned int n) {
 (void)m;int ret=step();if(ret)return ret;memcpy(v,regs+r,n);
 if(r==SM5440_INT1)memset(regs+r,0,n);
 return 0;
}
static int regmap_write(void *m,unsigned int r,unsigned int v) {
 (void)m;int ret=step();if(ret)return ret;
 if(r!=SM5440_ADCCNTL2)unsafe_writes++;
 regs[r]=v;return 0;
}
static int regmap_update_bits(void *m,unsigned int r,unsigned int mask,unsigned int v) {
 (void)m;int ret=step();if(ret)return ret;
 if(r==SM5440_CNTL5 && (v&SM5440_MODE_MASK))unsafe_writes++;
 if(r!=SM5440_CNTL5 && r!=SM5440_ADCCNTL1)unsafe_writes++;
 regs[r]=(regs[r]&~mask)|(v&mask);
 if(r==SM5440_ADCCNTL1 && (v&SM5440_ADC_ENABLE)){started=1;waits=0;}
 return 0;
}
static void msleep(unsigned int ms) {
 (void)ms;waits++;
 if(started && waits>=3 && !never_ready)regs[SM5440_INT4]|=SM5440_ADC_READY;
 if(never_ready==2)current->stopped=true;
}
'''
        code += function(src, "static int sm5440_off(") + "\n"
        code += function(src, "static int sm5440_sample_once(") + "\n"
        code += function(src, "static int sm5440_get_property(") + "\n"
        code += function(src, "static bool sm5440_passive_pc_sample(") + "\n"
        code += function(src, "static bool sm5440_startup_revblk(") + "\n"
        code += function(src, "static bool sm5440_startup_matches(") + "\n"
        code += function(src, "static void sm5440_poll(") + "\n"
        code += function(src, "static int sm5440_quiesce(") + "\n"
        code += function(src, "static int sm5440_resume(") + "\n"
        code += r'''
unsigned int value(int what,unsigned int high,unsigned int low) {
 switch(what){case 0:return sm5440_raw13(high,low);
 case 1:return sm5440_vbus_uv(high,low);
 case 2:return sm5440_vbat_uv(high,low);
 case 3:return sm5440_ibus_ua(high,low);
 default:return sm5440_die_decic(high);}
}
int encode(int what,unsigned int v) {
 if(what==0)return sm5440_vbat_code(v);
 if(what==1)return sm5440_ibus_code(v);
 return sm5440_frequency_code(v);
}
unsigned int faults(unsigned int packed,int running,int mode) {
 u8 st[4]={packed,packed>>8,packed>>16,packed>>24};
 return sm5440_decode_faults(st,running,mode);
}
int sample(int failure,int timeout,int bad,int *result) {
 struct sm5440_direct sm={0};struct sm5440_sample data={0};
 memset(regs,0,sizeof(regs));calls=waits=started=unsafe_writes=0;
 fail_at=failure;never_ready=timeout;current=&sm;
 /* VBAT4.0V -> raw3904; VBUS9V -> raw4904. */
 regs[0x1e]=4904>>5;regs[0x1f]=(4904&31)<<3;
 regs[0x27]=3904>>5;regs[0x28]=(3904&31)<<3;
 regs[0x22]=1600>>5;regs[0x23]=(1600&31)<<3;regs[0x26]=25;
 regs[0x0a]=32;regs[0x03]=1; /* deliberately stale ready before start */
 if(bad==1)regs[0x10]=4;
 if(bad==2)regs[0x27]=regs[0x28]=0;
 int ret=sm5440_sample_once(&sm,&data);
 result[0]=waits;result[1]=unsafe_writes;result[2]=data.vbus_uv;
 result[3]=data.vbat_uv;result[4]=data.ibus_ua;result[5]=data.die_decic;
 result[6]=calls;return ret;
}
int provenance(int live,int *result) {
 int ignored[7];sample(0,0,0,ignored);
 struct sm5440_direct sm={0};struct sm5440_sample data={0};current=&sm;
 regs[live?SM5440_STATUS1:SM5440_INT1]=8;
 regs[(live?SM5440_STATUS1:SM5440_INT1)+2]|=2;
 regs[SM5440_CNTL2]=0xa5;regs[SM5440_VBUSCNTL]=0x31;
 regs[SM5440_VBATCNTL]=0x33;regs[SM5440_PRTNCNTL]=0x55;
 int ret=sm5440_sample_once(&sm,&data);
 result[0]=data.int_before[0];result[1]=data.int_before[2];
 result[2]=data.status[0];result[3]=data.status[2];result[4]=data.faults;
 result[5]=data.cntl2;result[6]=data.vbuscntl;result[7]=data.vbatcntl;
 result[8]=data.prtncntl;result[9]=data.int4_wait;
 result[10]=data.mode_before;result[11]=data.mode_after;
 result[12]=data.adc[9];result[13]=unsafe_writes;return ret;
}
int turn_off(int failure,int *result) {
 struct sm5440_direct sm={0};memset(regs,0,sizeof(regs));regs[0x10]=0xac;
 calls=unsafe_writes=0;fail_at=failure;int ret=sm5440_off(&sm);
 result[0]=regs[0x10];result[1]=unsafe_writes;return ret;
}
int property(int p,int valid,int fault,int *v) {
 struct sm5440_direct sm={0};sm.fault=fault;
 sm.sample=(struct sm5440_sample){.valid=valid,.stamp=100,.vbus_uv=9000000,
 .ibus_ua=1000000,.die_decic=350,.online=true};
 struct power_supply psy={.sm=&sm};union power_supply_propval value={0};
 int ret=sm5440_get_property(&psy,p,&value);*v=value.intval;return ret;
}
int startup(int scenario,int *result) {
 int ignored[7];sample(0,0,0,ignored);fake_jiffies=100;
 struct sm5440_direct sm={0};current=&sm;scheduled=changed=0;
 regs[SM5440_ADC_VBUS]=904>>5;regs[SM5440_ADC_VBUS+1]=(904&31)<<3;
 regs[0x22]=regs[0x23]=0;regs[2]=0x62;regs[0x0a]=0x20;
 if(scenario==3)regs[0]=8; /* VBATOVP + REVBLK never exempt */
 if(scenario==4)regs[0x23]=8; /* any nonzero IBUS */
 if(scenario==5){regs[0x1e]=4904>>5;regs[0x1f]=(4904&31)<<3;}
 if(scenario==12)regs[2]=0; /* initial clean, later REVBLK */
 sm5440_poll(&sm.work.work);
 struct power_supply psy={.sm=&sm};union power_supply_propval val={0};
 sm5440_get_property(&psy,POWER_SUPPLY_PROP_HEALTH,&val);
 result[0]=sm.fault;result[1]=sm.startup_confirmations;result[2]=val.intval;
 result[3]=sm5440_get_property(&psy,POWER_SUPPLY_PROP_VOLTAGE_NOW,&val);
 if(scenario==1 || scenario==12)regs[2]=2;
 if(scenario==2)regs[0x0a]=0x22;
 if(scenario==6)fake_jiffies=5101;
 if(scenario==7)regs[SM5440_VBATCNTL]^=1;
 if(scenario==8)regs[0x0a]=0;
 if(scenario==9)fail_at=calls+1;
 if(scenario==10)sm5440_quiesce(&sm);
 sm5440_poll(&sm.work.work);
 result[4]=sm.fault;result[5]=sm.startup_confirmations;
 if(scenario==13){
  struct device dev={.sm=&sm};sm5440_quiesce(&sm);
  result[6]=sm5440_resume(&dev);result[7]=sm.fault;
  result[8]=unsafe_writes;fake_jiffies=100;return 0;
 }
 if(scenario==11)regs[2]=2; /* fail on last confirmation */
 sm5440_poll(&sm.work.work);
 sm5440_get_property(&psy,POWER_SUPPLY_PROP_HEALTH,&val);
 result[6]=sm.fault;result[7]=sm.startup_confirmations;result[8]=val.intval;
 result[9]=unsafe_writes;int transfers=calls;
 if(sm.fault)sm5440_poll(&sm.work.work);
 result[10]=calls-transfers;result[11]=sm.startup_sample.faults;
 fake_jiffies=100;return 0;
}
int startup_bound(int field,unsigned int v) {
 struct sm5440_sample s={.faults=SM5440_FAULT_REVBLK,.int_before={0,0,2,0},
 .status={0,0,32,0},.int4_wait=1,.online=true,.vbus_uv=5000000,
 .vbat_uv=4000000,.ibus_ua=0,.die_decic=300};
 switch(field){case 0:s.vbus_uv=v;break;case 1:s.vbat_uv=v;break;
 case 2:s.ibus_ua=v;break;case 3:s.die_decic=v;break;
 case 4:s.mode_before=v;break;case 5:s.mode_after=v;break;
 case 6:s.status[2]=v;break;case 7:s.faults=v;break;
 case 8:s.online=v;break;case 9:s.int4_wait=v;break;
 case 10:s.int_before[0]=v;break;}
 return sm5440_startup_revblk(&s);
}
int poll_fault(int *result) {
 int ignored[7];sample(0,0,0,ignored);
 struct sm5440_direct sm={0};current=&sm;scheduled=changed=0;
 regs[0x0a]=34;sm5440_poll(&sm.work.work);
 result[0]=sm.fault;result[1]=sm.sample.faults;result[2]=scheduled;
 int transfers=calls;regs[0x0a]=32;sm5440_poll(&sm.work.work);
 result[3]=calls-transfers;result[4]=changed;return 0;
}
'''
        path = Path(cls.temp.name) / "passive.c"
        path.write_text(code)
        binary = Path(cls.temp.name) / "passive.so"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared",
                        "-fPIC", str(path), "-o", str(binary)], check=True,
                       capture_output=True, text=True)
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.value.restype = ctypes.c_uint
        cls.lib.faults.argtypes = [ctypes.c_uint, ctypes.c_int, ctypes.c_int]

    def sample(self, failure=0, timeout=0, bad=0):
        values = (ctypes.c_int * 7)()
        ret = self.lib.sample(failure, timeout, bad, values)
        return ret, list(values)

    def startup(self, scenario=0):
        values = (ctypes.c_int * 12)()
        self.assertEqual(self.lib.startup(scenario, values), 0)
        return list(values)

    def test_startup_revblk_needs_two_new_confirmations(self):
        v = self.startup()
        self.assertEqual(v[:4], [0, 2, 0, -61])  # UNKNOWN, ADC not published
        self.assertEqual(v[4:6], [0, 1])
        self.assertEqual(v[6:10], [0, 0, 1, 0])  # Good only after BOTH
        self.assertEqual(v[11], 0x80)  # original raw-event snapshot retained

    def test_pending_resume_is_refused(self):
        v = self.startup(13)
        self.assertEqual(v[6:9], [-5, 1, 0])

    def test_startup_classifier_bounds_and_fault_sources(self):
        for field, accepted, rejected in (
            (0, (4500000, 5500000), (4499999, 5500001, 9000000)),
            (1, (3500000, 4299999), (3499999, 4300000)),
            (2, (0,), (1, 100000)),
            (3, (225, 419), (224, 420)),
            (4, (0, 1), (4, 8, 12)),
            (5, (0, 1), (4, 8, 12)),
            (6, (32,), (34, 128, 1, 16)),
            (7, (0x80,), (0, 0x82, 0x88)),
            (8, (1,), (0,)), (9, (1,), (0,)),
            (10, (0,), (8, 16, 1)),
        ):
            for value in accepted:
                self.assertEqual(self.lib.startup_bound(field, value), 1)
            for value in rejected:
                self.assertEqual(self.lib.startup_bound(field, value), 0)

    def test_startup_live_or_recurrent_revblk_stays_failure(self):
        for scenario in (1, 2, 11, 12):
            v = self.startup(scenario)
            self.assertEqual(v[6], 1)
            self.assertEqual(v[8], 6)
            self.assertEqual(v[9:11], [0, 0])

    def test_startup_vbatovp_never_exempted(self):
        v = self.startup(3)
        self.assertEqual(v[:3], [1, 0, 6])
        self.assertEqual(v[6], 1)

    def test_startup_nine_volts_or_nonzero_current_not_exempted(self):
        for scenario in (4, 5):
            self.assertEqual(self.startup(scenario)[:3], [1, 0, 6])

    def test_startup_deadline_protection_detach_and_i2c_fail_closed(self):
        for scenario in (6, 7, 8, 9):
            v = self.startup(scenario)
            self.assertEqual(v[6], 1)
            self.assertEqual(v[8:11], [6, 0, 0])

    def test_suspend_during_startup_cannot_clear_fault(self):
        v = self.startup(10)
        self.assertEqual(v[4], 1)
        self.assertEqual(v[8:11], [6, 0, 0])

    def test_first_fault_preserves_latch_and_live_provenance(self):
        for live in (0, 1):
            values = (ctypes.c_int * 14)()
            self.assertEqual(self.lib.provenance(live, values), 0)
            v = list(values)
            self.assertEqual(v[:4], [0, 0, 8, 34] if live else [8, 2, 0, 32])
            self.assertEqual(v[4], 0x82)  # same conservative stop, either source
            self.assertEqual(v[5:9], [0xa5, 0x31, 0x33, 0x55])
            self.assertEqual(v[9:12], [1, 0, 0])
            self.assertEqual(v[12], 3904 >> 5)
            self.assertEqual(v[13], 0)  # added reads cannot program protections

    def test_vendor_adc_scales_and_endianness(self):
        for raw in (0, 1, 31, 32, 3904, 8191):
            high, low = raw >> 5, (raw & 31) << 3
            self.assertEqual(self.lib.value(0, high, low | 7), raw)
            self.assertEqual(self.lib.value(1, high, low), 4096000 + raw * 1000)
            self.assertEqual(self.lib.value(2, high, low), 2048000 + raw * 500)
            self.assertEqual(self.lib.value(3, high, low), raw * 625)
        self.assertEqual(self.lib.value(4, 25, 0), 350)

    def test_register_bounds_and_round_down(self):
        for mv in (3800, 4000, 4300, 4440):
            code = self.lib.encode(0, mv)
            self.assertLessEqual(3800 + code * 12.5, mv)
        for mv in (0, 3799, 4441, 65535):
            self.assertEqual(self.lib.encode(0, mv), -1)
        for ma in (1000, 1499, 1800):
            self.assertLessEqual(self.lib.encode(1, ma) * 50, ma)
        for ma in (0, 999, 1801, 3000):
            self.assertEqual(self.lib.encode(1, ma), -1)
        for khz, code in ((450, 4), (650, 8), (850, 12)):
            self.assertEqual(self.lib.encode(2, khz), code)
        self.assertEqual(self.lib.encode(2, 900), -1)

    def test_complete_conversion_waits_past_stale_ready(self):
        ret, values = self.sample()
        self.assertEqual(ret, 0)
        self.assertEqual(values[:6], [3, 0, 9000000, 4000000, 1000000, 350])

    def test_each_i2c_failure_cannot_publish_complete_sample(self):
        _, clean = self.sample()
        for step in range(1, clean[6] + 1):
            with self.subTest(step=step):
                ret, values = self.sample(failure=step)
                self.assertLess(ret, 0)
                self.assertEqual(values[1], 0)

    def test_adc_timeout_and_suspend_cancel_bounded(self):
        ret, values = self.sample(timeout=1)
        self.assertLess(ret, 0)
        self.assertEqual(values[0], 12)
        ret, values = self.sample(timeout=2)
        self.assertLess(ret, 0)
        self.assertLessEqual(values[0], 1)

    def test_running_pump_and_invalid_pack_rejected(self):
        for bad in (1, 2):
            ret, values = self.sample(bad=bad)
            self.assertLess(ret, 0)
            self.assertEqual(values[1], 0)

    def test_off_preserves_unrelated_bits_and_reports_i2c_failure(self):
        values = (ctypes.c_int * 2)()
        self.assertEqual(self.lib.turn_off(0, values), 0)
        self.assertEqual(list(values), [0xa0, 0])
        for step in (1, 2):
            self.assertLess(self.lib.turn_off(step, values), 0)

    def test_all_vendor_fault_bits_and_lost_mode_vbus(self):
        for word, bit in ((0, 4), (0, 3), (0, 1), (2, 7), (2, 6),
                          (2, 4), (2, 3), (2, 2), (2, 1), (2, 0), (3, 2), (3, 1)):
            fault = self.lib.faults((1 << (word * 8 + bit)) | (32 << 16), 1, 1)
            self.assertNotEqual(fault, 0)
        self.assertNotEqual(self.lib.faults(32 << 16, 1, 0), 0)
        self.assertNotEqual(self.lib.faults(0, 1, 1), 0)
        self.assertEqual(self.lib.faults(64 << 16, 0, 0), 0)  # unplug UVLO
        self.assertEqual(self.lib.faults(((128 | 8) << 8) | (32 << 16), 1, 1), 0)

    def test_real_power_supply_getter_units_and_unavailable_conversion(self):
        value = ctypes.c_int()
        for prop, expected in ((0, 3), (1, 1), (2, 1), (3, 9000000), (4, 1000000), (5, 350)):
            self.assertEqual(self.lib.property(prop, 1, 0, ctypes.byref(value)), 0)
            self.assertEqual(value.value, expected)
        self.assertLess(self.lib.property(3, 0, 0, ctypes.byref(value)), 0)
        self.assertEqual(self.lib.property(1, 0, 1, ctypes.byref(value)), 0)
        self.assertEqual(value.value, 6)

    def test_consumed_irq_fault_stays_latched_without_retry(self):
        result = (ctypes.c_int * 5)()
        self.lib.poll_fault(result)
        self.assertEqual(result[0], 1)
        self.assertNotEqual(result[1], 0)
        self.assertEqual(list(result)[2:], [0, 0, 1])


class PassiveProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("passive_gate", ROOT / "scripts/verify-x710-charging-profile.py")
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def test_exact_resolved_profile_and_protected_changes_rejected(self):
        base = self.gate.BASE.read_text()
        cfg = base + "\nCONFIG_CHARGER_SM5440_DIRECT=y\n"
        self.assertTrue(self.gate.verify(cfg)["valid"])
        for symbol in ("CONFIG_HVC_DCC", "CONFIG_USB_DWC3", "CONFIG_USER_NS",
                       "CONFIG_BATTERY_SM5714", "CONFIG_QCOM_SPMI_ADC5_GEN3"):
            after = self.gate.STAGE2.CONTAINER.read_config(cfg)
            after[symbol] = "n" if after.get(symbol) == "y" else "y"
            self.assertFalse(self.gate.verify("\n".join(f"{k}={v}" for k, v in after.items()))["valid"])

    def test_invalid_profile_rejected_before_any_source_or_build_operation(self):
        for script in ("build-kernel.sh", "prepare-kernel.sh"):
            for profile in ("pps", "direct", "typo"):
                run = subprocess.run(["bash", str(ROOT / "scripts" / script), "/missing-tree"],
                                     env={"PATH": "/usr/bin:/bin", "GTS9_CHARGING_PROFILE": profile},
                                     capture_output=True, text=True)
                self.assertEqual(run.returncode, 2)

    def test_default_stage2_gate_still_rejects_passive_enable(self):
        cfg = self.gate.BASE.read_text() + "\nCONFIG_CHARGER_SM5440_DIRECT=y\n"
        self.assertFalse(self.gate.STAGE2.verify(cfg)["valid"])

    def test_primary_dt_fragment_and_gpi_stay_frozen(self):
        source = (ROOT / "kernel/dts/sm8550-samsung-gts9wifi.dts").read_text()
        part = source.split("&i2c_hub_3 {")[1].split("/*\n * SE8")[0]
        for token in ("400000", "gpi_dma1", "QCOM_GPI_I2C", 'dma-names = "tx", "rx"',
                      'reg = <0x63>', 'status = "disabled"'):
            self.assertIn(token, part)
        overlay = (ROOT / "kernel/dts/charging/sm8550-samsung-gts9wifi-sm5440-passive.dts").read_text()
        self.assertIn('&sm5440_direct {\n\tstatus = "okay";', overlay)
        self.assertNotIn('PDO_PPS', overlay)
        self.assertNotIn('CONFIG_CHARGER_SM5440_DIRECT',
                         (ROOT / 'kernel/config/gts9wifi-mainline.fragment').read_text())
