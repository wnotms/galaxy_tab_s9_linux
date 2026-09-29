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
static int record(char c) {actions[n++]=c;actions[n]=0;step++;
 if(step==cancelstep)alive=false;
 return step==failstep?-EIO:0;
}
static bool epoch(void *c,u64 e) {(void)c;return alive && e==facts.epoch;}
static int readfacts(void *c,struct x710_charge_facts *f) {
 (void)c;int r=record('E');*f=facts;return r;
}
static int gate(void *c,bool b) {(void)c;int r=record(b?'I':'S');
 /* Inhibit latches before attempted I/O, restore does not clear on failure. */
 if(b)inhibited=true;else if(!r)inhibited=false;return r;
}
static int off(void *c) {(void)c;int r=record('O');if(!r)pump=false;return r;}
static int pps(void *c,unsigned int mv,unsigned int ma) {
 (void)c;(void)ma;int r=record('P');if(pump)return -EPERM;if(!r)bus=mv;return r;
}
static int measure(void *c,struct x710_physical_sample *s) {
 (void)c;int r=record('M');s->valid=!invalid;s->online=true;s->pump_on=pump;
 s->vbus_mv=bus;s->vbat_mv=facts.vbat_mv;s->ibus_ma=pump?1000:0;
 s->faults=samplefault;return r;
}
static int prepare(void *c,unsigned int ma) {(void)c;(void)ma;return record('C');}
static int on(void *c) {(void)c;int r=record('N');
 if(!alive || !inhibited)return -ECANCELED;
 if(!r)pump=true;
 return r;
}
static int fixed(void *c) {(void)c;int r=record('F');
 if(pump)return -EPERM;
 if(!r)bus=9000;
 return r;
}
static const struct x710_charge_ops ops={.current_epoch=epoch,.read_facts=readfacts,
 .switching_gate=gate,.pump_off=off,.pps_request=pps,.measure=measure,
 .pump_prepare=prepare,.pump_on=on,.fixed_restore=fixed};
static struct x710_charge_facts good(void) {
 return (struct x710_charge_facts){.epoch=1,.capacity=50,.pack_decic=250,
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
 struct x710_charge_transaction tx={.state=X710_SWITCHING,.armed=kind!=0,
 .target_mv=8800,.target_ma=1800};
 if(bad==1)facts.pack_valid=false;
 if(bad==2)facts.voltage_valid=false;
 if(bad==3)facts.apdo=false;
 if(bad==4)facts.suspended=true;
 if(bad==5)samplefault=1;
 if(bad==6)invalid=1;
 int r=x710_charge_start(&tx,&facts,&ops,0);
 if(!r && kind==2)r=x710_charge_stop(&tx,&ops,0);
 if(!r && kind==3)r=x710_charge_refresh(&tx,&ops,0);
 if(!r && kind==4){alive=false;r=x710_charge_stop(&tx,&ops,0);}
 if(!r && kind==5){facts.suspended=true;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==6){facts.apdo=false;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==7){samplefault=1;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==8){facts.pack_valid=false;r=x710_charge_refresh(&tx,&ops,0);}
 if(!r && kind==9){tx.armed=false;r=x710_charge_refresh(&tx,&ops,0);}
 out[0]=tx.state;out[1]=pump;out[2]=inhibited;out[3]=step;out[4]=tx.last_error;
 return r;
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

    def run_case(self, kind=1, fail=0, cancel=0, bad=0):
        result = (ctypes.c_int * 5)()
        ret = self.lib.scenario(kind, fail, cancel, bad, result)
        return ret, list(result), self.lib.trace().decode()

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
