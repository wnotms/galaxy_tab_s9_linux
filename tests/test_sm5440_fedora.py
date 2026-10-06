"""Actual Fedora-port C: hardware programming, owned handoff and terminal faults."""
import ctypes
import gzip
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'kernel/drivers/sm5440-fedora.c'


class FedoraPortTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        src = SOURCE.read_text()
        prefix = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define DIV_ROUND_UP(n,d) (((n)+(d)-1)/(d))
#define clamp(n,l,h) ((n)<(l)?(l):((n)>(h)?(h):(n)))
#define clamp_val clamp
#define min(a,b) ((a)<(b)?(a):(b))
#define msecs_to_jiffies(n) (n)
#define container_of(p,t,m) ((t *)((char *)(p)-offsetof(t,m)))
#define to_delayed_work(p) ((struct delayed_work *)(p))
#define POWER_SUPPLY_HEALTH_GOOD 1
#define PM_SUSPEND_PREPARE 1
#define PM_POST_SUSPEND 2
#define PM_HIBERNATION_PREPARE 3
#define PM_POST_HIBERNATION 4
#define PM_RESTORE_PREPARE 5
#define PM_POST_RESTORE 6
#define NOTIFY_DONE 0
#define notifier_from_errno(n) (n)
struct device { int unused; }; struct i2c_client { int unused; };
struct power_supply { int unused; }; struct work_struct { int unused; };
struct delayed_work { struct work_struct work; };
struct notifier_block { int (*notifier_call)(struct notifier_block *,unsigned long,void *); };
'''
        prefix += '\n#include "' + str(ROOT / 'kernel/drivers/sm5714-stage2.h') + '"\n'
        prefix += '\n#include "' + str(ROOT / 'kernel/drivers/sm5440-hw.h') + '"\n'
        prefix += '\n'.join(line for line in src.splitlines()
                           if (line.startswith('#define SM5440_') or line.startswith('#define  SM5440_')) and not line.startswith('#define SM5440_WRITE')) + '\n'
        prefix += function(src, 'struct sm5440_direct {') + ';\n'
        prefix += r'''
static bool direct_charge, fixed_return_check;
static struct sm5440_direct sm;
static struct i2c_client client;
static struct device dev;
static struct sm5714_pd_snapshot source;
static struct sm5714_pack_snapshot pack;
static u8 regs[64];
static u64 clock_ms, owned_lease;
static int calls, fail_at, pps_calls, fixed_calls, releases, pump_ons, unsafe_pps;
static int request_error, fixed_error, off_error, release_error, pack_error;
static int detach_wait, scheduled, canceled;
static int fixed_snapshot_calls, owned_snapshot_calls, fail_owned_at, mutate_pack, fixed_adc_offset;
static unsigned long scheduled_delay;
static int fixed_sampling, fixed_sample_count, fixed_pattern;
static u64 fixed_return_started;
static void log_stub(struct device *d,const char *fmt,...) {(void)d;(void)fmt;}
#define dev_info log_stub
#define dev_info_ratelimited log_stub
#define dev_warn log_stub
#define dev_err log_stub
static int step(void) {calls++;return calls==fail_at?-EIO:0;}
static void raw13(int reg,int raw) {regs[reg]=raw>>5;regs[reg+1]=(raw&31)<<3;}
static void set_vbus(int mv) {raw13(SM5440_REG_ADC_VBUS1,mv-4096);}
static int i2c_smbus_read_byte_data(struct i2c_client *c,int reg) {
 (void)c;int ret=step();if(ret)return ret;int value=regs[reg];
 if(reg>=0&&reg<4)regs[reg]=0;
 return value;
}
static int i2c_smbus_write_byte_data(struct i2c_client *c,int reg,int value) {
 (void)c;int ret=step();if(ret)return ret;
 if(reg==SM5440_REG_CNTL5 && (value&12) && off_error==-EBUSY)return -EIO;
 if(reg==SM5440_REG_CNTL5 && !(value&12) && off_error)return off_error;
 if(reg==SM5440_REG_CNTL5 && (value&12))pump_ons++;
 regs[reg]=value;
 if(reg==SM5440_REG_CNTL1 && value==1){regs[reg]=0;regs[SM5440_REG_CNTL5]=0;}
 return 0;
}
static void msleep(unsigned int ms) {
 clock_ms+=ms;
 if(fixed_sampling){
  fixed_sample_count++;
  int mv=9000+fixed_adc_offset;
  if(fixed_pattern==1)mv+=(fixed_sample_count%2?60:-60);
  if(fixed_pattern==2 && fixed_sample_count==1)mv=9600;
  if(fixed_pattern==3 && !(fixed_sample_count%2))mv=9600;
  if(fixed_pattern==4)mv+=(fixed_sample_count-1)*40;
  set_vbus(mv);
 }
 if(detach_wait){source.source_generation++;source.online=0;detach_wait=0;}
}
static void usleep_range(unsigned int a,unsigned int b) {(void)b;clock_ms+=(a+999)/1000;}
static u64 ktime_get_boottime(void) {return clock_ms*1000000;}
#define ktime_to_ms(n) ((n)/1000000)
static int schedule_delayed_work(struct delayed_work *w,unsigned long ms) {(void)w;scheduled_delay=ms;scheduled++;return 0;}
static void cancel_delayed_work_sync(struct delayed_work *w) {(void)w;canceled++;}
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *out) {
 fixed_snapshot_calls++;
 /* Actual public API is fixed-only, not a universal snapshot mock. */
 if(source.pps_contract)return -EAGAIN;
 *out=source;return 0;
}
int sm5714_pd_read_owned_snapshot(u64 instance,u64 generation,u64 lease,struct sm5714_pd_snapshot *out) {
 owned_snapshot_calls++;
 if(owned_snapshot_calls==fail_owned_at)return -EAGAIN;
 if(instance!=source.instance||generation!=source.source_generation||lease!=owned_lease||!source.pps_contract)return -ESTALE;
 *out=source;return 0;
}
int sm5714_battery_read_pack(u64 lease,struct sm5714_pack_snapshot *out) {
 if(pack_error)return pack_error;
 if(lease&&lease!=owned_lease)return -ESTALE;
 *out=pack;out->typec_mv=source.budget_mv;out->typec_ma=source.budget_ma;
 if(mutate_pack && source.pps_contract){source.source_generation++;mutate_pack=0;}
 return 0;
}
int sm5714_battery_switching_acquire(u64 *lease) {owned_lease=7;*lease=7;return 0;}
int sm5714_pd_request_pps(u64 instance,u64 generation,u64 lease,unsigned int mv,unsigned int ma,struct sm5714_pd_snapshot *out) {
 pps_calls++;
 if(regs[SM5440_REG_CNTL5]&12)unsafe_pps++;
 if(request_error)return request_error;
 if(instance!=source.instance||generation!=source.source_generation||lease!=owned_lease||!source.online)return -ESTALE;
 source.pps_contract=true;source.online=2;source.budget_mv=mv;source.budget_ma=ma;source.budget_generation++;
 set_vbus(mv);*out=source;return 0;
}
int sm5714_pd_restore_fixed(u64 instance,u64 generation,u64 lease,struct sm5714_pd_snapshot *out) {
 fixed_calls++;
 if(fixed_error)return fixed_error;
 if(instance!=source.instance||generation!=source.source_generation||lease!=owned_lease||!source.online)return -ESTALE;
 source.pps_contract=false;source.online=1;source.budget_mv=9000;source.budget_ma=1500;source.budget_generation++;
 fixed_sampling=1;fixed_sample_count=0;fixed_return_started=clock_ms;
 set_vbus(9000+fixed_adc_offset);*out=source;return 0;
}
int sm5714_pd_release_fixed(u64 instance,u64 generation,u64 lease,const struct sm5714_fixed_proof *proof) {
 if(release_error)return release_error;
 if(instance!=source.instance||generation!=source.source_generation||lease!=owned_lease||source.pps_contract||!proof->pump_off||proof->ibus_ua||
    (regs[SM5440_REG_CNTL5]&12)||clock_ms-proof->observed_ms>100||!sm5714_fixed_vbus_valid(source.budget_mv,proof->vbus_uv))return -ESTALE;
 releases++;owned_lease=0;return 0;
}
'''
        names = ['sm5440_update_bits', 'sm5440_read_adc_pair', 'sm5440_adc_vbus_mv',
                 'sm5440_adc_ibus_ma', 'sm5440_adc_vbat_mv', 'sm5440_adc_die_temp',
                 'sm5440_direct_enabled', 'sm5440_read_source', 'sm5440_read_pack', 'sm5440_pps_retry',
                 'sm5440_pps_target_mv', 'sm5440_set_ibus_limit', 'sm5440_negotiate_pps',
                 'sm5440_refresh_pps', 'sm5440_set_freq', 'sm5440_select_freq',
                 'sm5440_pump_off', 'sm5440_pump_on', 'sm5440_wait_vbus_settled',
                 'sm5440_renegotiate_pps', 'sm5440_monitor_faults', 'sm5440_log_faults',
                 'sm5440_restore_switching', 'sm5440_hw_init', 'sm5440_start',
                 'sm5440_eligible', 'sm5440_fixed_check_ready', 'sm5440_fixed_return_once',
                 'sm5440_backoff', 'sm5440_work',
                 'sm5440_cancel_work', 'sm5440_pm_notify']
        for name in names:
            import re
            match = re.search(r'^static [^\n]*\b' + name + r'\(', src, re.M)
            prefix += function(src, match.group()) + '\n'
        prefix += r'''
void reset(void) {
 memset(&sm,0,sizeof(sm));memset(regs,0,sizeof(regs));sm.client=&client;sm.dev=&dev;
 source=(struct sm5714_pd_snapshot){.instance=12,.source_generation=44,.budget_generation=88,.budget_mv=9000,.budget_ma=1500,.online=1,.charge_requested=true};
 pack=(struct sm5714_pack_snapshot){.instance=9,.capacity=50,.voltage_uv=4180000,.pack_decic=300,.battery_present=true,.attached=true,.thermal_normal=true,.health=1};
 regs[SM5440_REG_ADCCNTL2]=0xdf;regs[SM5440_REG_STATUS3]=32;regs[SM5440_REG_DEVICEID]=0x21;set_vbus(9000);
 raw13(SM5440_REG_ADC_VBAT1,(4180-2048)*2);regs[SM5440_REG_ADC_DIETEMP]=15;
 clock_ms=1000;owned_lease=0;direct_charge=true;fixed_return_check=false;
 sm.fixed_check_deadline=clock_ms+SM5440_FIXED_CHECK_WAIT_MS;
 calls=fail_at=pps_calls=fixed_calls=releases=pump_ons=unsafe_pps=0;
 fixed_snapshot_calls=owned_snapshot_calls=fail_owned_at=mutate_pack=fixed_adc_offset=0;
 fixed_sampling=fixed_sample_count=fixed_pattern=0;fixed_return_started=0;
 request_error=fixed_error=off_error=release_error=pack_error=detach_wait=scheduled=canceled=0;
}
int eligible(void) {return sm5440_eligible(&sm);}
int start(void) {if(!sm5440_eligible(&sm))return -EPERM;return sm5440_start(&sm);}
int refresh(void) {return sm5440_renegotiate_pps(&sm);}
int cleanup(void) {return sm5440_restore_switching(&sm);}
void prepare_fixed_return(void) {sm.source=source;sm.lease=owned_lease=7;}
void work(void) {sm5440_work(&sm.work.work);}
int pm(int n) {return sm5440_pm_notify(&sm.pm_nb,n,0);}
void remove_worker(void) {sm5440_cancel_work(&sm);}
void input(int key,int value) {
 switch(key){case 0:direct_charge=value;break;case 1:pack.capacity=value;break;
 case 2:pack.voltage_uv=value;break;case 3:pack.pack_decic=value;break;case 4:pack_error=value;break;
 case 5:request_error=value;break;case 6:fixed_error=value;break;case 7:off_error=value;break;
 case 8:release_error=value;break;case 9:fail_at=value;break;case 10:detach_wait=value;break;
 case 11:regs[SM5440_REG_INT3]=value;break;case 12:regs[SM5440_REG_CNTL5]=value;break;
 case 13:sm.pps_ticks=value;break;case 14:raw13(SM5440_REG_ADC_IBUS1,value);break;
 case 15:pack.thermal_normal=value;break;case 16:fail_owned_at=value;break;
 case 17:mutate_pack=value;break;case 18:fixed_adc_offset=value;break;
 case 19:fixed_pattern=value;break;case 20:fixed_return_check=value;break;
 case 21:sm.fixed_check_deadline=value;break;
 case 22:source.budget_mv=value;break;case 23:regs[SM5440_REG_ADCCNTL2]=value;break;}
}
int value(int key) {
 switch(key){case 0:return sm.active;case 1:return regs[SM5440_REG_CNTL5]&12;
 case 2:return owned_lease;case 3:return releases;case 4:return pps_calls;
 case 5:return fixed_calls;case 6:return unsafe_pps;case 7:return sm.fault_latched;
 case 8:return calls;case 9:return pump_ons;case 10:return regs[SM5440_REG_IBUSCNTL];
 case 11:return scheduled;case 12:return sm.last_cleanup_error;case 13:return sm.target_mv;
 case 14:return sm.target_ma;case 15:return canceled;
 case 22:return sm.fixed_check_done;case 20:return clock_ms-fixed_return_started;case 21:return fixed_sample_count;
 case 18:return fixed_snapshot_calls;case 19:return owned_snapshot_calls;
 case 16:return scheduled_delay;case 17:return regs[SM5440_REG_CNTL1]&128;
 default:return -1;}
}
'''
        c = Path(cls.temp.name) / 'port.c'
        so = Path(cls.temp.name) / 'port.so'
        c.write_text(prefix)
        compiled = subprocess.run(['cc', '-shared', '-fPIC', '-O0', '-Wall', '-Werror',
                                   '-Wno-unused-function', '-Wno-unused-parameter',
                                   str(c), '-o', str(so)], capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)
        cls.lib = ctypes.CDLL(str(so))

    def setUp(self):
        self.lib.reset()

    def v(self, n):
        return self.lib.value(n)

    def test_default_off_has_no_handoff_or_requests(self):
        self.lib.input(0, 0)
        self.assertEqual(self.lib.eligible(), 0)
        self.assertEqual(self.lib.start(), -1)
        self.assertEqual([self.v(n) for n in (2, 4, 8, 9)], [0, 0, 0, 0])

    def test_off_only_fixed_check_is_single_shot_without_pps_or_pump_on(self):
        self.lib.input(0, 0); self.lib.input(20, 1)
        self.lib.input(18, 272)
        self.lib.work()
        self.assertEqual([self.v(k) for k in (1, 2, 3, 4, 5, 9, 22)],
                         [0, 0, 1, 0, 1, 0, 1])
        counts = [self.v(k) for k in (4, 5, 8, 9, 11)]
        self.lib.work()
        self.assertEqual(counts, [self.v(k) for k in (4, 5, 8, 9, 11)])

    def test_fixed_check_waits_readonly_on_pc_and_has_absolute_deadline(self):
        self.lib.input(0, 0); self.lib.input(20, 1); self.lib.input(22, 5000)
        self.lib.work()
        self.assertEqual([self.v(k) for k in (2, 4, 8, 9, 22)], [0, 0, 0, 0, 0])
        self.assertEqual(self.v(11), 1)
        self.lib.input(21, 1000)
        self.lib.work()
        self.assertEqual([self.v(k) for k in (2, 4, 8, 9, 22)], [0, 0, 0, 0, 1])
        self.assertEqual(self.v(7), 1)
        self.assertEqual(self.v(11), 1)  # no scheduling after completion/failure

    def test_fixed_check_refuses_direct_optin_and_unhealthy_pack(self):
        for key, value in [(0, 1), (1, 80), (2, 4300000), (3, 380),
                           (4, -5), (15, 0), (22, 12000)]:
            self.lib.reset(); self.lib.input(0, 0); self.lib.input(20, 1)
            self.lib.input(key, value); self.lib.work()
            self.assertEqual([self.v(k) for k in (2, 3, 4, 8, 9, 22)],
                             [0, 0, 0, 0, 0, 1])
            self.assertEqual(self.lib.eligible(), 0)

    def test_fixed_check_refuses_unknown_adc_channels_without_reconfiguration(self):
        self.lib.input(0, 0); self.lib.input(20, 1); self.lib.input(23, 0)
        self.lib.work()
        self.assertEqual([self.v(k) for k in (1, 2, 3, 4, 7, 9, 22)],
                         [0, 0, 0, 0, 1, 0, 1])

    def test_fixed_check_proof_failure_is_not_retried(self):
        self.lib.input(0, 0); self.lib.input(20, 1); self.lib.input(18, 451)
        self.lib.work()
        self.assertEqual([self.v(k) for k in (1, 2, 3, 4, 7, 9, 22)],
                         [0, 7, 0, 0, 1, 0, 1])
        count = self.v(8); self.lib.work(); self.assertEqual(self.v(8), count)

    def test_actual_entry_and_transactional_fixed_return(self):
        self.assertEqual(self.lib.start(), 0)
        self.assertEqual([self.v(n) for n in (0, 1, 2, 10, 14)], [1, 4, 7, 36, 1800])
        self.assertTrue(8200 <= self.v(13) <= 10500)
        self.assertEqual(self.lib.cleanup(), 0)
        self.assertEqual([self.v(n) for n in (0, 1, 2, 3, 6, 7)], [0, 0, 0, 1, 0, 0])

    def test_pps_checks_use_owned_snapshot_both_sides(self):
        self.assertEqual(self.lib.start(), 0)
        self.assertEqual(self.v(19), 2)
        before = self.v(18)
        self.assertEqual(self.lib.refresh(), 0)
        self.assertEqual(self.v(18), before)  # PPS refresh must never call fixed-only API.
        self.assertGreaterEqual(self.v(19), 4)

    def test_first_or_second_owned_read_failure_never_starts_pump(self):
        for n in [1, 2]:
            self.lib.reset(); self.lib.input(16, n)
            self.assertEqual(self.lib.start(), -11)
            self.assertEqual([self.v(k) for k in (0, 1, 2, 3, 9)], [0, 0, 0, 1, 0])

    def test_generation_changes_during_pack_read_abort_handoff(self):
        self.lib.input(17, 1)
        self.assertNotEqual(self.lib.start(), 0)
        self.assertEqual([self.v(k) for k in (0, 1, 3, 7, 9)], [0, 0, 0, 1, 0])

    def test_stable_observed_fixed_offset_releases_after_three_samples(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(18, 272)  # Test330 fixed9V ADC; no offset/calibration change.
        self.assertEqual(self.lib.cleanup(), 0)
        self.assertEqual([self.v(k) for k in (0, 1, 2, 3, 7)], [0, 0, 0, 1, 0])
        self.assertEqual(self.v(21), 3)
        self.assertGreaterEqual(self.v(20), 120)

    def test_fixed_return_from_off_does_not_request_pps_or_enable_pump(self):
        self.lib.prepare_fixed_return()
        self.lib.input(18, 272)
        self.assertEqual(self.lib.cleanup(), 0)
        self.assertEqual([self.v(k) for k in (1, 2, 3, 4, 9)], [0, 0, 1, 0, 0])

    def test_each_fixed_return_i2c_failure_keeps_lease_and_pump_off(self):
        self.lib.prepare_fixed_return()
        before = self.v(8)
        self.assertEqual(self.lib.cleanup(), 0)
        count = self.v(8) - before
        for call in range(1, count + 1):
            with self.subTest(call=call):
                self.lib.reset(); self.lib.prepare_fixed_return()
                self.lib.input(9, call)
                self.assertEqual(self.lib.cleanup(), -5)
                self.assertEqual([self.v(k) for k in (1, 2, 3, 4, 7, 9)],
                                 [0, 7, 0, 0, 1, 0])

    def test_detach_during_fixed_settling_never_releases_new_connection(self):
        self.lib.prepare_fixed_return()
        self.lib.input(10, 1)
        self.assertNotEqual(self.lib.cleanup(), 0)
        self.assertEqual([self.v(k) for k in (1, 2, 3, 4, 7, 9)],
                         [0, 7, 0, 0, 1, 0])

    def test_outside_fixed_window_never_releases(self):
        for offset in [451, -451]:
            self.lib.reset(); self.assertEqual(self.lib.start(), 0)
            self.lib.input(18, offset)
            self.assertEqual(self.lib.cleanup(), -110)
            self.assertEqual([self.v(k) for k in (0, 1, 2, 3, 7)], [0, 0, 7, 0, 1])

    def test_fixed_window_boundaries_are_inclusive(self):
        for offset in [450, -450]:
            self.lib.reset(); self.assertEqual(self.lib.start(), 0)
            self.lib.input(18, offset)
            self.assertEqual(self.lib.cleanup(), 0)
            self.assertEqual(self.v(3), 1)

    def test_fluctuating_in_window_voltage_never_releases(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(19, 1)  # Every reading is valid, but range is120mV.
        self.assertEqual(self.lib.cleanup(), -110)
        self.assertEqual([self.v(k) for k in (1, 2, 3, 7)], [0, 7, 0, 1])
        self.assertEqual(self.v(21), 30)

    def test_outside_sample_restarts_the_full_settling_interval(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(19, 2)
        self.assertEqual(self.lib.cleanup(), 0)
        self.assertEqual(self.v(21), 4)
        self.assertGreaterEqual(self.v(20), 170)

    def test_intermittent_outside_voltage_never_accumulates_proof(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(19, 3)
        self.assertEqual(self.lib.cleanup(), -110)
        self.assertEqual([self.v(k) for k in (1, 2, 3, 7)], [0, 7, 0, 1])

    def test_stability_limit_is_range_not_endpoint_error(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(19, 4)  # 40mV steps; total80mV across three reads.
        self.assertEqual(self.lib.cleanup(), 0)
        self.assertEqual(self.v(21), 3)

    def test_refresh_parks_pump_across_pps(self):
        self.assertEqual(self.lib.start(), 0)
        self.assertEqual(self.lib.refresh(), 0)
        self.assertEqual([self.v(n) for n in (1, 4, 6, 9)], [4, 2, 0, 2])

    def test_entry_temperature_soc_voltage_and_invalid_sensor(self):
        for key, val in [(1, 4), (1, 80), (2, 3499000), (2, 4300000),
                         (3, 149), (3, 380), (4, -5), (15, 0)]:
            with self.subTest(key=key, value=val):
                self.lib.reset(); self.lib.input(key, val)
                self.assertEqual(self.lib.start(), -1)
                self.assertEqual([self.v(n) for n in (2, 4, 9)], [0, 0, 0])

    def test_pps_refusal_restores_and_never_starts(self):
        self.lib.input(5, -5)
        self.assertEqual(self.lib.start(), -5)
        self.assertEqual([self.v(n) for n in (0, 1, 2, 3, 9)], [0, 0, 0, 1, 0])

    def test_each_cleanup_failure_keeps_switching_inhibited(self):
        for key in (6, 7, 8):
            with self.subTest(key=key):
                self.lib.reset(); self.assertEqual(self.lib.start(), 0)
                self.lib.input(key, -5)
                self.assertEqual(self.lib.cleanup(), -5)
                self.assertEqual([self.v(n) for n in (2, 3, 7, 12)], [7, 0, 1, -5])
                self.assertEqual(self.lib.eligible(), 0)

    def test_nonzero_fractional_mA_blocks_fixed_release(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(14, 1)  # 625uA: Fedora's mA conversion truncates to zero.
        self.assertEqual(self.lib.cleanup(), -110)
        self.assertEqual([self.v(n) for n in (1, 2, 3, 7)], [0, 7, 0, 1])

    def test_fault_or_mode_loss_precedes_refresh(self):
        for key, val in [(11, 2), (11, 128), (11, 64), (11, 8), (11, 1),
                         (12, 0), (4, -5), (3, 420)]:
            with self.subTest(key=key, value=val):
                self.lib.reset(); self.assertEqual(self.lib.start(), 0)
                self.lib.input(13, 3); self.lib.input(key, val)
                self.lib.work()
                self.assertEqual([self.v(n) for n in (0, 1, 2, 4)], [0, 0, 0, 1])

    def test_detach_during_start_cannot_release_new_connection(self):
        self.lib.input(10, 1)
        self.assertNotEqual(self.lib.start(), 0)
        self.assertEqual([self.v(n) for n in (1, 2, 3, 7)], [0, 7, 0, 1])

    def test_pm_and_remove_drain_before_cleanup(self):
        for action in (1, 3, 5):
            self.lib.reset(); self.assertEqual(self.lib.start(), 0)
            self.lib.pm(action)
            self.assertEqual([self.v(n) for n in (0, 1, 2, 15)], [0, 0, 0, 1])
        self.lib.reset(); self.assertEqual(self.lib.start(), 0)
        self.lib.remove_worker()
        self.assertEqual([self.v(n) for n in (0, 1, 2, 15)], [0, 0, 0, 1])
        self.assertEqual(self.lib.eligible(), 0)

    def test_unproven_off_preserves_watchdog_and_vetoes_suspend(self):
        self.assertEqual(self.lib.start(), 0)
        self.lib.input(7, -5)
        self.assertNotEqual(self.lib.pm(1), 0)
        self.assertEqual([self.v(n) for n in (1, 2, 7, 17)], [4, 7, 1, 128])

    def test_repeated_first_poll_fault_reaches_quiet_backoff(self):
        delays = []
        for _ in range(5):
            self.lib.work()  # entry
            self.assertEqual(self.v(0), 1)
            self.lib.input(11, 2)  # immediate REVBLK
            self.lib.work()
            self.assertEqual(self.v(0), 0)
            delays.append(self.v(16))
        self.assertEqual(delays, [4000, 8000, 16000, 30000, 300000])

    def test_all_entry_i2c_failures_cleanup(self):
        self.assertEqual(self.lib.start(), 0)
        count = self.v(8)
        for n in range(1, count + 1):
            with self.subTest(call=n):
                self.lib.reset(); self.lib.input(9, n)
                self.assertNotEqual(self.lib.start(), 0)
                self.assertEqual([self.v(k) for k in (0, 1, 6)], [0, 0, 0])


class FedoraIntegrationTests(unittest.TestCase):
    def test_original_source_archive_and_default_off_probe(self):
        import hashlib
        r = ROOT / 'reference/charging/sm5440-fedora-port'
        origin = gzip.decompress((r / 'upstream-sm5440_direct.c.gz').read_bytes())
        self.assertEqual(hashlib.sha256(origin).hexdigest(), json.loads((r / 'SOURCE.json').read_text())['sha256'])
        src = SOURCE.read_text()
        probe = function(src, 'static int sm5440_probe(')
        self.assertNotIn('sm5440_hw_init(', probe)
        self.assertNotIn('sm5440_start(', probe)
        self.assertIn('module_param(direct_charge, bool, 0400)', src)
        self.assertNotIn('sm5440_conversion_', src)
        self.assertNotIn('max_pps_ma', src)

    def test_alternative_profile_selects_only_fedora_driver(self):
        spec = importlib.util.spec_from_file_location('fedora_config', ROOT / 'scripts/verify-x710-charging-profile.py')
        m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
        baseline = m.BASE.read_text()
        config = baseline + '\n# CONFIG_CHARGER_SM5440_DIRECT is not set\nCONFIG_CHARGER_SM5440_FEDORA=y\n'
        result = m.verify(config, profile='sm5440-fedora')
        self.assertTrue(result['valid'])
        self.assertTrue(result['pump_activation_available'])
        self.assertFalse(result['direct_charge_default'])
        self.assertTrue(result['requires_registered_boot_opt_in'])
        self.assertFalse(m.verify(config, profile='sm5440-passive')['valid'])
        self.assertFalse(m.verify(config.replace('# CONFIG_CHARGER_SM5440_DIRECT is not set', 'CONFIG_CHARGER_SM5440_DIRECT=y'), profile='sm5440-fedora')['valid'])
