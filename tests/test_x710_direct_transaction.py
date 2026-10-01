"""Compile the real default-inactive transaction core with a faulting adapter.

This proves C action ordering and refusal/fallback rules, not a live adapter or
the safety of physical pump enable, sensor calibration or hardware OCP.
"""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class TransactionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        source = (ROOT / 'kernel/drivers/x710-charging-policy.c').read_text()
        source = '\n'.join(line for line in source.splitlines() if not line.startswith('#include <linux/'))
        header = ROOT / 'kernel/drivers/x710-charging-policy.h'
        code = r'''
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;
#define MODULE_DESCRIPTION(x)
#define MODULE_LICENSE(x)
''' + source.replace('#include "x710-charging-policy.h"', '#include "' + str(header) + '"')
        code += r'''
static struct x710_charge_facts facts;
static unsigned int bus;static bool pump,inhibited,alive;
static char actions[256];static int n,failstep,step,cancelstep,samplefault,invalid;
static u64 clock_ms;
static unsigned int measure_delay,facts_delay,on_delay,pps_delay,trip_ua;
static int sample_time_mode,contractstep;static bool acquire_fresh;
static bool pause_before_on;static int on_clock_reads;
static int record(char c) {actions[n++]=c;actions[n]=0;step++;
 if(step==cancelstep)alive=false;
 if(step==contractstep)facts.apdo_ma=1750;
 return step==failstep?-EIO:0;
}
static u64 now(void *c) {(void)c;
 if(pause_before_on && step==9 && ++on_clock_reads==2)clock_ms+=501;
 return clock_ms;
}
static bool epoch(void *c,u64 e) {(void)c;return alive && e==facts.epoch;}
static int readfacts(void *c,struct x710_charge_facts *f) {
 (void)c;int r=record('E');clock_ms+=facts_delay;
 if(acquire_fresh)facts.observed_ms=clock_ms;
 *f=facts;return r;
}
static int gate(void *c,bool b) {(void)c;int r=record(b?'I':'S');
 /* Inhibit latches before attempted I/O, restore does not clear on failure. */
 if(b)inhibited=true;else if(!r)inhibited=false;return r;
}
static int off(void *c) {(void)c;int r=record('O');if(!r)pump=false;return r;}
static int pps(void *c,unsigned int mv,unsigned int ma) {
 (void)c;(void)ma;int r=record('P');clock_ms+=pps_delay;
 if(pump)return -EPERM;
 if(!r)bus=mv;
 return r;
}
static int measure(void *c,struct x710_physical_sample *s) {
 (void)c;int r=record('M');s->valid=!invalid;s->online=true;s->pump_on=pump;
 clock_ms+=measure_delay;s->observed_ms=clock_ms;
 if(sample_time_mode==1)s->observed_ms=clock_ms-101;
 if(sample_time_mode==2)s->observed_ms=clock_ms+1;
 if(sample_time_mode==3)s->observed_ms=0;
 s->vbus_mv=bus;s->vbat_mv=facts.vbat_mv;s->ibus_ua=pump?trip_ua:0;
 s->faults=samplefault;return r;
}
static int prepare(void *c,unsigned int ma) {(void)c;(void)ma;return record('C');}
static int on(void *c) {(void)c;int r=record('N');
 clock_ms+=on_delay;
 if(!alive || !inhibited)return -ECANCELED;
 if(!r)pump=true;
 return r;
}
static int fixed(void *c) {(void)c;int r=record('F');
 if(pump)return -EPERM;
 if(!r)bus=9000;
 return r;
}
static const struct x710_charge_ops ops={.now_ms=now,.current_epoch=epoch,.read_facts=readfacts,
 .switching_gate=gate,.pump_off=off,.pps_request=pps,.measure=measure,
 .pump_prepare=prepare,.pump_on=on,.fixed_restore=fixed};
static struct x710_charge_facts good(void) {
 return (struct x710_charge_facts){.epoch=1,.observed_ms=1000,
 .apdo_min_mv=8200,.apdo_max_mv=10500,.apdo_ma=1800,.capacity=50,.pack_decic=250,
 .die_decic=350,.vbat_mv=4000,.fixed_mv=9000,.attached=true,.battery_present=true,
 .healthy=true,.pack_valid=true,.voltage_valid=true,.soc_valid=true,
 .die_valid=true,.adc_valid=true,.fixed_healthy=true,.apdo=true,
 .thermal_normal=true,.software_ocp_verified=true};
}
int eligibility(int capacity,int pack,int vbat,int die,int missing) {
 struct x710_charge_facts f=good();f.capacity=capacity;f.pack_decic=pack;
 f.vbat_mv=vbat;f.die_decic=die;
 switch(missing){case 1:f.pack_valid=false;break;case 2:f.adc_valid=false;break;
 case 3:f.software_ocp_verified=false;break;case 4:f.suspended=true;break;
 case 5:f.fault=true;break;case 6:f.attached=false;break;case 7:f.battery_present=false;break;
 case 8:f.healthy=false;break;case 9:f.apdo=false;break;case 10:f.die_valid=false;break;
 case 11:f.voltage_valid=false;break;case 12:f.soc_valid=false;break;
 case 13:f.thermal_normal=false;break;case 14:f.epoch=0;break;}
 return x710_charge_eligible(&f);
}
int target(unsigned int vb,unsigned int lo,unsigned int hi,unsigned int ma,unsigned int *v) {
 return x710_pps_target(vb,lo,hi,ma,v,v+1);
}
int zone(int temp,int previous) {return x710_vendor_zone(temp,previous);}
unsigned int retry(unsigned int failures) {return x710_retry_seconds(failures);}
const char *trace(void) {return actions;}
int scenario(int kind,int fail,int cancel,int bad,int *out) {
 facts=good();alive=true;pump=inhibited=false;bus=9000;n=step=0;actions[0]=0;
 failstep=fail;cancelstep=cancel;samplefault=invalid=0;
 clock_ms=1000;measure_delay=facts_delay=on_delay=pps_delay=0;trip_ua=1000000;
 sample_time_mode=contractstep=0;acquire_fresh=false;
 pause_before_on=kind==36;on_clock_reads=0;
 struct x710_charge_transaction tx={.state=X710_SWITCHING,.armed=kind!=0,
 .target_mv=8800,.target_ma=1800};
 if(bad==1)facts.pack_valid=false;
 if(bad==2)facts.voltage_valid=false;
 if(bad==3)facts.apdo=false;
 if(bad==4)facts.suspended=true;
 if(bad==5)samplefault=1;
 if(bad==6)invalid=1;
 if(bad==7)facts.apdo_min_mv=9000;
 if(bad==8)facts.apdo_max_mv=8700;
 if(bad==9)facts.apdo_ma=1750;
 if(bad==10)facts.apdo_max_mv=8000;
 if(bad==11)facts.apdo_ma=0;
 if(bad==12)facts.observed_ms=0;
 if(bad==13)facts.observed_ms=499;
 if(bad==14)facts.observed_ms=1001;
 if(bad==15)facts.observed_ms=600;
 if(bad==16)facts.observed_ms=599;
 if(kind==21)contractstep=8;
 if(kind==22)on_delay=101;
 if(kind==23)on_delay=100;
 if(kind==24)clock_ms=0;
 int r=x710_charge_start(&tx,&facts,&ops,0);
 if(!r && kind==2)r=x710_charge_stop(&tx,&ops,0);
 if(!r && kind==3)r=x710_charge_refresh(&tx,&ops,0);
 if(!r && kind==4){alive=false;r=x710_charge_stop(&tx,&ops,0);}
 if(!r && kind==5){facts.suspended=true;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==6){facts.apdo=false;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==7){samplefault=1;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==8){facts.pack_valid=false;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==9){tx.armed=false;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==25){r=x710_charge_stop(&tx,&ops,0);
   if(!r)r=x710_charge_start(&tx,&facts,&ops,0);}
 if(!r && kind==27){pps_delay=2500;acquire_fresh=true;
   r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==28){clock_ms+=101;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && ((kind>=10 && kind<=18) || (kind>=29 && kind<=35))){
   if(kind==11)trip_ua=1800625;
   if(kind==12)clock_ms+=101;
   if(kind==13)measure_delay=101;
   if(kind==14)facts.observed_ms=499;
   if(kind==15)sample_time_mode=1;
   if(kind==16)sample_time_mode=2;
   if(kind==17)clock_ms--;
   if(kind==18)facts.apdo_ma=1750;
   if(kind==29){facts_delay=101;acquire_fresh=true;}
   if(kind==30)facts.observed_ms=1001;
   if(kind==31)facts.observed_ms=0;
   if(kind==32)sample_time_mode=3;
   if(kind==33)clock_ms=0;
   if(kind==34)contractstep=step+2;
   if(kind==35)trip_ua=1800000;
   r=x710_charge_monitor(&tx,&ops,0);
 }
 out[0]=tx.state;out[1]=pump;out[2]=inhibited;out[3]=step;out[4]=tx.last_error;
 out[5]=tx.armed;
 return r;
}
int fresh(u64 stamp,u64 tick,unsigned int age) {return x710_fresh(stamp,tick,age);}
int no_clock(void) {
 struct x710_charge_ops missing=ops;struct x710_charge_transaction tx={.armed=true};
 missing.now_ms=0;return x710_charge_start(&tx,&facts,&missing,0);
}
int stop_switching(void) {
 struct x710_charge_transaction tx={.state=X710_SWITCHING,.armed=true};
 int r=x710_charge_stop(&tx,&ops,0);return r?r:tx.armed;
}
int stop_missing_clock(void) {
 struct x710_charge_transaction tx={.armed=true};struct x710_charge_ops missing=ops;
 missing.now_ms=0;int r=x710_charge_stop(&tx,&missing,0);
 return r==-EINVAL && !tx.armed;
}
int pm_case(int kind,int fail,int cancel,int *out) {
 int scratch[6];scenario(kind==0 || kind==4?0:1,0,0,0,scratch);
 struct x710_charge_transaction tx={.state=scratch[0],.epoch=1,
 .fixed_mv=9000,.target_mv=8800,.target_ma=1800,.armed=true,
 .switching_inhibited=inhibited,.last_clock_ms=1000};
 struct x710_charge_ops current=ops;
 n=step=0;actions[0]=0;failstep=fail;cancelstep=cancel;
 int r, resumed=-999, started=-999;
 if(kind==2)current.now_ms=0;
 if(kind==4){tx.suspended=true;r=x710_charge_start(&tx,&facts,&ops,0);}
 else if(kind==9 || kind==10){tx.suspended=true;
   r=kind==9?x710_charge_monitor(&tx,&ops,0):x710_charge_refresh(&tx,&ops,0);}
 else {r=x710_charge_suspend(&tx,&current,0);
   if(kind==7 && !r)r=x710_charge_suspend(&tx,&current,0);
   resumed=x710_charge_resume(&tx);
   if(kind==3 && !resumed)started=x710_charge_start(&tx,&facts,&ops,0);
 }
 out[0]=tx.state;out[1]=pump;out[2]=inhibited;out[3]=tx.armed;
 out[4]=tx.suspended;out[5]=resumed;out[6]=started;out[7]=step;
 return r;
}
int invalid_pm(int kind) {
 struct x710_charge_transaction tx={.state=X710_SWITCHING};
 if(kind==0)return x710_charge_suspend(0,&ops,0);
 if(kind==1)return x710_charge_resume(0);
 return x710_charge_resume(&tx);
}
'''
        path = Path(cls.temp.name) / 'transaction.c'
        path.write_text(code)
        binary = Path(cls.temp.name) / 'transaction.so'
        run = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared',
                        '-fPIC', str(path), '-o', str(binary)],
                       capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stderr)
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.trace.restype = ctypes.c_char_p
        cls.lib.target.argtypes = [ctypes.c_uint] * 4 + [ctypes.POINTER(ctypes.c_uint)]
        cls.lib.fresh.argtypes = [ctypes.c_uint64, ctypes.c_uint64, ctypes.c_uint]

    def run_case(self, kind=1, fail=0, cancel=0, bad=0):
        result = (ctypes.c_int * 6)()
        ret = self.lib.scenario(kind, fail, cancel, bad, result)
        return ret, list(result), self.lib.trace().decode()

    def pm_case(self, kind=1, fail=0, cancel=0):
        result = (ctypes.c_int * 8)()
        ret = self.lib.pm_case(kind, fail, cancel, result)
        return ret, list(result), self.lib.trace().decode()

    def test_pm_active_exit_is_off_fixed_measure_switching(self):
        ret, state, trace = self.pm_case()
        self.assertEqual(ret, 0)
        self.assertEqual(trace, 'OFMS')
        self.assertEqual(state[:6], [0, 0, 0, 0, 0, 0])

    def test_pm_inactive_suspend_revokes_grant_without_hardware(self):
        ret, state, trace = self.pm_case(kind=0)
        self.assertEqual(ret, 0)
        self.assertEqual(trace, '')
        self.assertEqual(state[:6], [0, 0, 0, 0, 0, 0])

    def test_pm_each_exit_failure_blocks_resume_and_propagates(self):
        for operation in range(1, 5):
            ret, state, trace = self.pm_case(fail=operation)
            self.assertLess(ret, 0)
            self.assertEqual(state[0], 8)
            self.assertEqual(state[2:5], [1, 0, 1])
            self.assertLess(state[5], 0)
            self.assertNotIn('N', trace)
            if operation == 1:
                self.assertEqual(trace, 'O')
                self.assertEqual(state[1], 1)  # OFF not proven; no voltage change.

    def test_pm_invalid_adapter_latches_suspend_and_never_claims_off(self):
        ret, state, trace = self.pm_case(kind=2)
        self.assertLess(ret, 0)
        self.assertEqual(state[1:5], [1, 1, 0, 1])
        self.assertLess(state[5], 0)
        self.assertEqual(trace, '')

    def test_pm_resume_never_arms_or_requests_old_pps(self):
        ret, state, trace = self.pm_case(kind=3)
        self.assertEqual(ret, 0)
        self.assertEqual(state[3:6], [0, 0, 0])
        self.assertLess(state[6], 0)
        self.assertEqual(trace, 'OFMS')

    def test_pm_old_facts_and_manual_grant_cannot_start_while_suspended(self):
        ret, state, trace = self.pm_case(kind=4)
        self.assertLess(ret, 0)
        self.assertEqual(state[4], 1)
        self.assertEqual(trace, '')

    def test_pm_epoch_loss_never_restores_old_connection(self):
        ret, state, trace = self.pm_case(cancel=1)
        self.assertLess(ret, 0)
        self.assertEqual(state[:5], [7, 0, 1, 0, 1])
        self.assertLess(state[5], 0)
        self.assertEqual(trace, 'O')

    def test_pm_repeated_suspend_does_not_rearm_or_repeat_io(self):
        ret, state, trace = self.pm_case(kind=7)
        self.assertEqual(ret, 0)
        self.assertEqual(state[3:6], [0, 0, 0])
        self.assertEqual(trace, 'OFMS')

    def test_pm_monitor_refresh_with_suspend_latch_exit_without_request(self):
        for kind in (9, 10):
            ret, state, trace = self.pm_case(kind=kind)
            self.assertLess(ret, 0)
            self.assertEqual(state[:5], [0, 0, 0, 0, 1])
            self.assertEqual(trace, 'OFMS')

    def test_pm_invalid_or_unpaired_resume_is_refused(self):
        for kind in range(3):
            self.assertLess(self.lib.invalid_pm(kind), 0)

    def test_default_unarmed_calls_no_hardware(self):
        ret, state, trace = self.run_case(kind=0)
        self.assertLess(ret, 0)
        self.assertEqual(trace, '')
        self.assertEqual(state[:3], [0, 0, 0])

    def test_capacity_vbat_and_temperature_bringup_bounds(self):
        for soc in (5, 50, 79):
            self.assertTrue(self.lib.eligibility(soc, 250, 4000, 350, 0))
        for soc in (0, 4, 80, 90, 95, 101):
            self.assertFalse(self.lib.eligibility(soc, 250, 4000, 350, 0))
        for temp in (200, 250, 379):
            self.assertTrue(self.lib.eligibility(50, temp, 4000, 350, 0))
        for temp in (-100, 199, 380, 420, 500):
            self.assertFalse(self.lib.eligibility(50, temp, 4000, 350, 0))
        for vbat in (0, 3499, 4300, 4440, 99999):
            self.assertFalse(self.lib.eligibility(50, 250, vbat, 350, 0))
        for die in (-1, 550, 650):
            self.assertFalse(self.lib.eligibility(50, 250, 4000, die, 0))

    def test_all_absent_invalid_fault_suspend_inputs_fail_closed(self):
        for missing in range(1, 15):
            self.assertFalse(self.lib.eligibility(50, 250, 4000, 350, missing))
        for bad in (1, 2, 3, 4):
            ret, state, trace = self.run_case(bad=bad)
            self.assertLess(ret, 0)
            self.assertEqual(trace, '')
            self.assertEqual(state[1], 0)

    def test_vendor_thermal_zones_and_exact_19_decic_hysteresis(self):
        for temp, zone in ((0, 0), (50, 1), (150, 2), (180, 3), (181, 4),
                           (419, 4), (420, 5), (500, 6)):
            self.assertEqual(self.lib.zone(temp, 4), zone)
        self.assertEqual(self.lib.zone(400, 5), 4)
        self.assertEqual(self.lib.zone(401, 5), 5)
        self.assertEqual(self.lib.zone(199, 3), 3)
        self.assertEqual(self.lib.zone(200, 3), 4)

    def test_pps_target_units_source_cap_and_encoding(self):
        result = (ctypes.c_uint * 2)()
        self.assertEqual(self.lib.target(4000, 3300, 11000, 3000, result), 0)
        self.assertEqual(list(result), [8780, 1800])
        self.assertEqual(self.lib.target(4000, 3300, 11000, 1549, result), 0)
        self.assertEqual(result[1], 1500)
        self.assertEqual(result[0] % 20, 0)
        for args in ((4000, 3300, 8500, 3000), (4000, 3300, 11000, 999),
                     (0, 3300, 11000, 3000), (4300, 3300, 11000, 3000),
                     (4000, 12000, 20000, 3000), (4000, 9000, 8500, 3000),
                     (0xffffffff, 3300, 11000, 0xffffffff)):
            self.assertLess(self.lib.target(*args, result), 0)

    def test_entry_on_last_and_actual_adc_required(self):
        ret, state, trace = self.run_case()
        self.assertEqual(ret, 0)
        self.assertEqual(state[:3], [4, 1, 1])
        self.assertLess(trace.index('I'), trace.index('P'))
        self.assertLess(trace.index('O'), trace.index('P'))
        self.assertLess(trace.index('P'), trace.index('M'))
        self.assertLess(trace.index('M'), trace.index('N'))
        for bad in (5, 6):
            ret, state, trace = self.run_case(bad=bad)
            self.assertLess(ret, 0)
            self.assertNotIn('N', trace)
            self.assertEqual(state[1], 0)

    def test_every_entry_operation_failure_stops_or_safe_fallback(self):
        _, clean, _ = self.run_case()
        for step in range(1, clean[3] + 1):
            with self.subTest(step=step):
                ret, state, trace = self.run_case(fail=step)
                self.assertLess(ret, 0)
                self.assertEqual(state[1], 0)
                self.assertNotEqual(state[0], 4)

    def test_detach_during_each_entry_stage_no_new_epoch_rearm(self):
        _, clean, _ = self.run_case()
        for step in range(1, clean[3] + 1):
            ret, state, trace = self.run_case(cancel=step)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)
            self.assertNotIn('F', trace)
            self.assertNotIn('S', trace)

    def test_exit_pump_off_before_fixed_before_switching(self):
        ret, state, trace = self.run_case(kind=2)
        self.assertEqual(ret, 0)
        self.assertEqual(state[:3], [0, 0, 0])
        exit_trace = trace[trace.index('N') + 2:]
        self.assertEqual(exit_trace, 'OFMS')

    def test_exit_off_unknown_refuses_voltage_change(self):
        _, entry, _ = self.run_case()
        ret, state, trace = self.run_case(kind=2, fail=entry[3] + 1)
        self.assertLess(ret, 0)
        self.assertEqual(state[0], 8)
        self.assertEqual(state[2], 1)
        self.assertNotIn('F', trace)
        self.assertNotIn('S', trace)

    def test_refresh_off_then_request_adc_then_on(self):
        ret, state, trace = self.run_case(kind=3)
        self.assertEqual(ret, 0)
        self.assertEqual(state[:3], [4, 1, 1])
        refresh = trace[trace.index('N') + 2:]
        self.assertEqual(refresh, 'OEPMENM')

    def test_pps_failure_adc_failure_and_revblk_during_refresh(self):
        _, entry, _ = self.run_case()
        for step in range(entry[3] + 1, entry[3] + 8):
            ret, state, _ = self.run_case(kind=3, fail=step)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)
        for kind in (5, 6, 7, 8, 9):
            ret, state, _ = self.run_case(kind=kind)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)

    def test_detach_stop_does_not_negotiate_or_restore_old_attach(self):
        ret, state, trace = self.run_case(kind=4)
        self.assertLess(ret, 0)
        self.assertEqual(state[:3], [7, 0, 1])
        self.assertNotIn('F', trace)
        self.assertNotIn('S', trace)

    def test_backoff_is_bounded_and_never_shift_overflows(self):
        for count, seconds in ((0, 0), (1, 2), (2, 4), (3, 8), (4, 16), (5, 300), (1000, 300)):
            self.assertEqual(self.lib.retry(count), seconds)

    def test_latest_source_offer_required_before_any_path_change(self):
        for bad in range(7, 13):
            with self.subTest(bad=bad):
                ret, state, trace = self.run_case(bad=bad)
                self.assertLess(ret, 0)
                self.assertEqual(trace, '')
                self.assertEqual(state[1], 0)

    def test_source_contracts_before_on_or_during_monitor(self):
        for kind in (21, 18, 34):
            ret, state, trace = self.run_case(kind=kind)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)
            self.assertFalse(state[5])
            if kind == 21:
                self.assertNotIn('N', trace)

    def test_epoch_changes_inside_facts_callback_before_inhibit(self):
        ret, state, trace = self.run_case(cancel=1)
        self.assertLess(ret, 0)
        self.assertEqual(trace, 'E')
        self.assertEqual(state[1], 0)
        self.assertFalse(state[5])

    def test_stale_and_future_facts_cannot_enter_direct(self):
        for bad in (13, 14):
            ret, state, trace = self.run_case(bad=bad)
            self.assertLess(ret, 0)
            self.assertEqual(trace, 'E')
            self.assertEqual(state[1], 0)

    def test_monotonic_age_bounds_no_zero_future_or_wraparound(self):
        for stamp, now, age, expected in (
            (1000, 1100, 100, True), (1000, 1101, 100, False),
            (1000, 1500, 500, True), (1000, 1501, 500, False),
            (0, 1000, 100, False), (1001, 1000, 100, False),
            (2**64-101, 2**64-1, 100, True),
            (2**64-1, 1, 100, False), (1, 2**64-1, 100, False)):
            self.assertEqual(bool(self.lib.fresh(stamp, now, age)), expected)
        self.assertLess(self.lib.no_clock(), 0)

    def test_post_on_observation_has_elapsed_deadline(self):
        self.assertEqual(self.run_case(kind=23)[0], 0)
        ret, state, _ = self.run_case(kind=22)
        self.assertLess(ret, 0)
        self.assertEqual(state[1], 0)
        self.assertFalse(state[5])

    def test_on_rechecks_facts_and_reserves_full_observation_budget(self):
        self.assertEqual(self.run_case(kind=23, bad=15)[0], 0)
        for kind, bad in ((1, 16), (36, 0)):
            ret, state, trace = self.run_case(kind=kind, bad=bad)
            self.assertLess(ret, 0)
            self.assertNotIn('N', trace)
            self.assertEqual(state[1], 0)
            self.assertFalse(state[5])

    def test_healthy_monitor_does_not_touch_pump_or_pps(self):
        ret, state, trace = self.run_case(kind=10)
        self.assertEqual(ret, 0)
        self.assertEqual(state[:3], [4, 1, 1])
        self.assertEqual(trace[trace.index('N') + 2:], 'EME')

    def test_sub_milliamp_overcurrent_preserved_and_exact_cap_allowed(self):
        self.assertEqual(self.run_case(kind=35)[0], 0)
        ret, state, trace = self.run_case(kind=11)
        self.assertLess(ret, 0)
        self.assertEqual(state[1], 0)
        self.assertFalse(state[5])
        monitor = trace[trace.index('N') + 2:]
        self.assertLess(monitor.index('O'), monitor.index('F'))
        self.assertNotIn('P', monitor)

    def test_active_monitor_deadline_or_callback_overrun_stops(self):
        for kind in (12, 13, 29):
            ret, state, _ = self.run_case(kind=kind)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)
            self.assertFalse(state[5])

    def test_invalid_timestamps_clock_and_facts_fail_closed(self):
        for kind in (14, 15, 16, 17, 24, 30, 31, 32, 33):
            ret, state, _ = self.run_case(kind=kind)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)

    def test_every_monitor_callback_failure_pump_off_and_no_rearm(self):
        _, entry, _ = self.run_case()
        for step in range(entry[3] + 1, entry[3] + 4):
            ret, state, _ = self.run_case(kind=10, fail=step)
            self.assertLess(ret, 0)
            self.assertEqual(state[1], 0)
            self.assertFalse(state[5])

    def test_stop_revokes_authorization_even_when_already_switching(self):
        self.assertEqual(self.lib.stop_switching(), 0)
        self.assertTrue(self.lib.stop_missing_clock())
        for kind in (2, 4, 25):
            ret, state, _ = self.run_case(kind=kind)
            self.assertFalse(state[5])
            self.assertEqual(state[1], 0)
            if kind == 25:
                self.assertLess(ret, 0)

    def test_refresh_off_wait_allowed_but_overdue_active_rearm_rejected(self):
        ret, state, trace = self.run_case(kind=27)
        self.assertEqual(ret, 0)
        self.assertEqual(state[:3], [4, 1, 1])
        self.assertEqual(trace[trace.index('N') + 2:], 'OEPMENM')
        ret, state, trace = self.run_case(kind=28)
        self.assertLess(ret, 0)
        self.assertEqual(state[1], 0)
        self.assertFalse(state[5])
        self.assertNotIn('P', trace[trace.index('N') + 2:])
