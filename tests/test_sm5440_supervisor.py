"""Actual converter/OFF/WDT chain; host faults are not physical OCP proof."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import test_sm5440_actuator as fixture

ROOT = Path(__file__).resolve().parents[1]


class SupervisorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = Path(cls.tmp.name)
        # Reuse pinned Linux PD macros/enum and mock header vocabulary. Tests
        # below link all actual hardware helpers, not the fixture's adapter.
        fixture.ActuatorTests.setUpClass()
        try:
            shutil.copytree(Path(fixture.ActuatorTests.tmp.name) / 'linux', p / 'linux')
        finally:
            fixture.ActuatorTests.tearDownClass()
        (p / 'mock.c').write_text(r'''
#include <string.h>
#include "sm5440-supervisor.h"
#include "sm5440-hw.h"
uint64_t fake_clock;
static u64 generation;
struct regmap {
 u8 reg[256];
 int phase,calls,writes,feeds,on,off,unsafe,fail,persistent,uncertain,drop,step,scenario;
 int ready_sent,order,error_seen,first_error_call,off_command_seen;
 u64 enabled_ms;
};
static int bad(struct regmap *m) {
 if(m->phase)m->calls++;
 fake_clock+=m->step;
 int b=m->phase && m->fail && (m->calls==m->fail || (m->persistent && m->calls>=m->fail));
 if(b){m->error_seen=1;if(!m->first_error_call)m->first_error_call=m->calls;}return b;
}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v) {
 if(bad(m))return -5;*v=m->reg[r];if(r<=3)m->reg[r]=0;return 0;
}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n) {
 if(bad(m))return -5;
 if(r==0 && m->enabled_ms && !m->ready_sent && fake_clock>=m->enabled_ms+30 && m->scenario!=33) {
  m->reg[3]|=1;m->ready_sent=1;
 }
 if(r==0x1e && m->scenario==22)m->reg[0x10]=1;
 if(r==0x1e && m->scenario>=15 && m->scenario<=18)m->error_seen=1;
 memcpy(v,m->reg+r,n);if(r==0)memset(m->reg,0,n);return 0;
}
static void written(struct regmap *m,unsigned int r,unsigned int v) {
 if(m->phase)m->writes++;
 if(r==0x10) {
  if((v&12)==4){if(m->phase)m->on++;}
  else if(!(v&12)){if(m->phase)m->off++;}
  else m->unsafe++;
 }
 else if(r==0x0c) {
  if(v&1)m->unsafe++;
  if(m->phase && (v&128)) {
   m->feeds++;if(m->scenario==34)generation++;
  }
  if(!(v&128) && (m->reg[0x10]&12))m->unsafe++;
 }
 else if(r==0x1c) {
  if(v&1) {
   m->enabled_ms=fake_clock;m->ready_sent=0;
   if(m->scenario==19){m->reg[0x0a]|=2;m->error_seen=1;}
   if(m->scenario==21)generation++;
   if(m->scenario==23)m->reg[0x16]^=1;
  }
  else if(m->enabled_ms && m->phase && m->error_seen &&
          m->calls!=m->first_error_call && !m->off_command_seen)m->order++;
 }
 else if(r!=0x1d && r!=0x11 && r!=0x16 && r!=0x14 && r!=0x12)m->unsafe++;
 if(!m->phase || m->calls!=m->drop)m->reg[r]=v;
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int v) {
 int b=bad(m);if(!b||m->uncertain)written(m,r,v);return b?-5:0;
}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int v) {
 if(m->phase && r==0x10 && mask==12 && !(v&12))m->off_command_seen=1;
 int b=bad(m);unsigned int next=(m->reg[r]&~mask)|(v&mask);
 if((!b||m->uncertain)&&next!=m->reg[r])written(m,r,next);return b?-5:0;
}
static void raw13(u8 *p,unsigned int raw){p[0]=raw>>5;p[1]=(raw&31)<<3;}
void exercise(int scenario,int fail,int persistent,int uncertain,int drop,int step,int *o) {
 struct regmap m={0};struct sm5440_actuator a={0};struct sm5440_supervisor s={0};
 struct x710_charge_facts f={0};struct x710_physical_sample physical={0};
 struct sm5714_pd_snapshot p={0};int ret;
 fake_clock=1000;generation=1;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x42;
 m.reg[0x0d]=0xf2;m.reg[0x0e]=0xb8;m.reg[0x0f]=0xff;m.reg[0x11]=0x89;
 m.reg[0x13]=0xe7;m.reg[0x15]=0x3f;m.reg[0x19]=0xfe;m.reg[0x1a]=0x0c;
 m.reg[0x16]=0x41;m.reg[0x14]=0x37;m.reg[0x12]=12;
 m.reg[0x1c]=0x82;m.reg[0x1d]=0x55;
 raw13(m.reg+0x1e,4904);raw13(m.reg+0x22,2400);m.reg[0x26]=15;raw13(m.reg+0x27,3504);
 a.enabled=true;a.switching_inhibited=true;a.generation=&generation;a.epoch=1;
 a.instance=7;a.source_generation=2;a.budget_generation=3;a.lease=99;
 o[0]=sm5440_control_prepare(&m,1500,&a.controls);
 o[1]=sm5440_watchdog_arm_off(&m,&a.watchdog,1,1000);
 f.epoch=1;f.observed_ms=1000;f.capacity=30;f.pack_decic=310;f.die_decic=300;f.vbat_mv=3800;
 f.fixed_mv=9000;f.apdo_min_mv=3300;f.apdo_max_mv=11000;f.apdo_ma=1800;
 f.attached=f.battery_present=f.healthy=f.pack_valid=f.voltage_valid=f.soc_valid=true;
 f.die_valid=f.adc_valid=f.fixed_healthy=f.apdo=f.thermal_normal=f.software_ocp_verified=true;
 physical.observed_ms=1000;physical.vbus_mv=9000;physical.vbat_mv=3800;
 physical.valid=physical.online=true;
 p.instance=7;p.source_generation=2;p.budget_generation=3;p.started_ms=p.completed_ms=1000;
 p.budget_mv=9000;p.budget_ma=1500;p.online=2;p.usb_type=8;
 p.voltage_uv=9000000;p.current_ua=1500000;p.charge_requested=p.pps_contract=true;
 p.nr_source_pdos=1;p.source_pdos[0]=0xc0000000U|(110U<<17)|(33U<<8)|36;
 o[2]=sm5440_actuator_start(&m,&a,&f,&physical,&p,9000,1500);
 s.actuator=&a;s.enabled=true;s.target_mv=9000;s.target_ma=1500;
 m.scenario=scenario;m.phase=1;m.calls=m.writes=m.on=m.off=m.feeds=0;
 m.fail=fail;m.persistent=persistent;m.uncertain=uncertain;m.drop=drop;m.step=step;
 if(scenario==1)s.enabled=false;
 if(scenario==2)f.software_ocp_verified=false;
 if(scenario==3)fake_clock=1101;
 if(scenario==4)generation++;
 if(scenario==5)f.observed_ms=599;
 if(scenario==6)p.online=1;
 if(scenario==7)p.source_pdos[0]|=1U<<28;
 if(scenario==8)p.source_generation++;
 if(scenario==9)p.budget_generation++;
 if(scenario==10)f.pack_decic=420;
 if(scenario==11)f.capacity=80;
 if(scenario==12)f.vbat_mv=4300;
 if(scenario==13)m.reg[0x1c]|=1;
 if(scenario==14)m.reg[0x10]=1;
 if(scenario==15)raw13(m.reg+0x22,2401); /* over approved1500mA by625uA */
 if(scenario==16)raw13(m.reg+0x27,4504); /* physical4300mV */
 if(scenario==17)raw13(m.reg+0x1e,5005); /* physical9101mV */
 if(scenario==18)m.reg[0x26]=39; /* die42C */
 if(scenario==25)p.completed_ms=1001;
 if(scenario==28)s.target_ma=1800;
 if(scenario==29)p.instance++;
 if(scenario==30)a.lease=0;
 if(scenario==31)s.samples=~0ULL;
 if(scenario==32)fake_clock=1;
 if(scenario==27)ret=sm5440_supervisor_cancel(&m,&s);
 else if(scenario==36)ret=sm5440_supervisor_begin(&m,&s,0,&p);
 else if(scenario==37)ret=sm5440_supervisor_begin(&m,&s,&f,0);
 else ret=sm5440_supervisor_begin(&m,&s,&f,&p);
 o[3]=ret;
 for(int i=0;ret==-115 && i<40;i++) {
  fake_clock+=5;
  if(scenario==38 && i==4)ret=sm5440_supervisor_advance(&m,&s,0,&p);
  else if(scenario==26 && i==4)ret=sm5440_supervisor_cancel(&m,&s);
  else ret=sm5440_supervisor_advance(&m,&s,&f,&p);
 }
 if(scenario==35 && ret==0) { /* fresh second acquisition, same native source */
  f.observed_ms=p.started_ms=p.completed_ms=fake_clock;
  ret=sm5440_supervisor_begin(&m,&s,&f,&p);
  for(int i=0;ret==-115 && i<40;i++){fake_clock+=5;ret=sm5440_supervisor_advance(&m,&s,&f,&p);}
 }
 o[4]=ret;o[5]=s.operation_error;o[6]=s.actuator_error;o[7]=s.converter_error;
 o[8]=s.hardware_quiesced;o[9]=s.stopped;o[10]=s.enabled;o[11]=s.samples;
 o[12]=m.reg[0x10];o[13]=m.reg[0x0c];o[14]=m.reg[0x1c];o[15]=m.reg[0x1d];
 o[16]=m.feeds;o[17]=m.off;o[18]=m.on;o[19]=m.unsafe;o[20]=m.calls;
 o[21]=a.off_verified;o[22]=a.mode_possible;o[23]=a.watchdog.owned;o[24]=a.controls.pending;
 o[25]=s.adc.owned;o[26]=s.adc.cleanup_error;o[27]=s.adc.sample.valid;
 o[28]=s.adc.ibus_ua;o[29]=s.adc.acquired_ms;o[30]=s.last_good_ms;
 if(ret!=0) {
  o[31]=sm5440_supervisor_cancel(&m,&s);
  o[32]=sm5440_supervisor_begin(&m,&s,&f,&p);
  o[33]=sm5440_supervisor_advance(&m,&s,&f,&p);
 }
 o[34]=m.calls;o[35]=m.order;
 o[36]=s.adc.adc_off_verified;
}
''')
        names = ['sm5440-supervisor.c', 'sm5440-conversion.c', 'sm5440-actuator.c',
                 'sm5440-watchdog.c', 'sm5440-control.c', 'x710-charging-policy.c']
        cmd = ['cc', '-shared', '-fPIC', '-std=c11', '-D__KERNEL__', '-Wall', '-Wextra',
               '-Werror', '-Wno-misleading-indentation', '-I' + str(p),
               '-I' + str(ROOT / 'kernel/drivers')]
        cmd += [str(ROOT / 'kernel/drivers' / n) for n in names]
        cmd += [str(p / 'mock.c'), '-o', str(p / 'supervisor.so')]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(p / 'supervisor.so'))
        cls.lib.exercise.argtypes = [ctypes.c_int] * 6 + [ctypes.POINTER(ctypes.c_int)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def case(self, scenario=0, fail=0, persistent=0, uncertain=0, drop=0, step=0):
        out = (ctypes.c_int * 37)()
        self.lib.exercise(scenario, fail, persistent, uncertain, drop, step, out)
        self.assertEqual(out[:3], [0, 0, 0], 'actual settings/WDT/admitted ON setup')
        self.assertEqual(out[18:20], [0, 0], 'monitor cannot enable pump or write unowned fields')
        if out[4]:
            self.assertEqual(out[31:34], [out[4]] * 3, 'terminal first error survives all later calls')
            self.assertEqual(out[20], out[34], 'no second OFF/cleanup/retry')
        return list(out)

    def test_measured_current_then_actual_equal_value_watchdog_write(self):
        o = self.case()
        self.assertEqual(o[4:12], [0, 0, 0, 0, 0, 0, 1, 1])
        self.assertEqual(o[12:17], [5, 0xc2, 0x82, 0x55, 1])
        self.assertEqual(o[27:29], [1, 1500000])
        self.assertGreater(o[30], o[29])

    def test_two_cycles_use_new_measurements_and_service_writes(self):
        o = self.case(35)
        self.assertEqual(o[4], 0)
        self.assertEqual(o[11], 2)
        self.assertEqual(o[16], 2)
        self.assertGreater(o[29], 1050)

    def test_no_ocp_permission_disabled_monitor_and_stale_facts_shut_down(self):
        for scenario in (1, 2, 3, 5, 10, 11, 12, 25, 30, 31, 32):
            with self.subTest(scenario=scenario):
                o = self.case(scenario)
                self.assertLess(o[4], 0)
                self.assertEqual(o[8], 1)
                self.assertEqual(o[12], 1)
                self.assertEqual(o[16], 0)

    def test_fixed_capability_and_changed_source_budget_or_instance_stop(self):
        for scenario in (4, 6, 7, 8, 9, 28, 29):
            o = self.case(scenario)
            self.assertLess(o[4], 0)
            self.assertEqual(o[12], 1)
            self.assertEqual(o[16], 0)

    def test_one_625ua_over_limit_stops_before_feeding_watchdog(self):
        o = self.case(15)
        self.assertEqual(o[4], -34)
        self.assertEqual(o[28], 1500625)
        self.assertEqual(o[16], 0)
        self.assertEqual(o[8], 1)
        self.assertEqual(o[12], 1)
        self.assertEqual(o[27], 0, 'raw excessive current never published valid')
        self.assertEqual(o[35], 0, 'OFF command precedes any ADC cleanup on excessive current')

    def test_physical_voltage_vbat_die_limits_and_revblk_stop(self):
        for scenario in (16, 17, 18, 19):
            o = self.case(scenario)
            self.assertLess(o[4], 0)
            self.assertEqual(o[12], 1)
            self.assertEqual(o[16], 0)

    def test_detach_during_sampling_cancels_before_next_feed(self):
        o = self.case(21)
        self.assertEqual(o[4], -125)
        self.assertEqual(o[12], 1)
        self.assertEqual(o[16], 0)

    def test_lost_mode_operating_register_drift_and_ADC_timeout(self):
        for scenario in (14, 22, 23, 33):
            o = self.case(scenario)
            self.assertLess(o[4], 0)
            self.assertEqual(o[16], 0)
            self.assertEqual(o[12], 1)

    def test_foreign_enabled_converter_is_not_adopted_or_declared_quiesced(self):
        o = self.case(13)
        self.assertEqual(o[4], -16)
        self.assertEqual(o[12], 1)
        self.assertEqual(o[8], 0)
        self.assertEqual(o[14] & 1, 1)

    def test_PM_cancel_before_and_during_measurement_is_terminal(self):
        for scenario in (26, 27):
            o = self.case(scenario)
            self.assertEqual(o[4], -125)
            self.assertEqual(o[8], 1)
            self.assertEqual(o[12], 1)
            self.assertEqual(o[16], 0)

    def test_missing_native_facts_or_source_is_actual_shutdown_not_bare_error(self):
        for scenario in (36, 37, 38):
            o = self.case(scenario)
            self.assertEqual(o[4], -22)
            self.assertEqual(o[12], 1)
            self.assertEqual(o[16], 0)
            self.assertEqual(o[8], 1)

    def test_generation_change_during_watchdog_service_is_stopped_after_readback(self):
        o = self.case(34)
        self.assertEqual(o[4], -125)
        self.assertEqual(o[12], 1)
        self.assertEqual(o[16], 1, 'generation changes during real write, then OFF')

    def test_each_bus_error_causes_one_terminal_actual_shutdown(self):
        for call in range(1, self.case()[20] + 1):
            for uncertain in (0, 1):
                with self.subTest(call=call, uncertain=uncertain):
                    o = self.case(fail=call, uncertain=uncertain)
                    self.assertLess(o[4], 0)
                    self.assertEqual(o[12], 1)
                    if o[25]:
                        self.assertLess(o[26], 0, 'failed cleanup remains owned, never retried')
                        self.assertEqual(o[8], 0)
                    elif o[36]:
                        self.assertEqual(o[8], 1)
                    else:
                        self.assertEqual(o[8], 0, 'no ADC-OFF proof cannot be called quiesced')
                    self.assertEqual(o[35], 0, 'attempt pump OFF before converter error cleanup')

    def test_persistent_bus_loss_keeps_unknown_OFF_and_watchdog_ownership(self):
        for call in range(1, self.case()[20] + 1):
            with self.subTest(call=call):
                o = self.case(fail=call, persistent=1, uncertain=0)
                self.assertLess(o[4], 0)
                self.assertEqual(o[8], 0)
                self.assertEqual(o[21], 0)
                self.assertEqual(o[22:24], [1, 1])

    def test_current_trip_cleanup_fault_retains_first_trip_and_separate_cleanup_error(self):
        for call in range(1, self.case(15)[20] + 1):
            with self.subTest(call=call):
                o = self.case(15, fail=call, uncertain=1)
                self.assertLess(o[4], 0)
                self.assertEqual(o[16], 0)
                self.assertEqual(o[35], 0)
                if o[6] or o[7]:
                    self.assertEqual(o[4], -34, 'cleanup cannot erase already observed current trip')
                    self.assertEqual(o[8], 0)

    def test_delayed_bus_stops_instead_of_resetting_the_monitor_clock(self):
        o = self.case(step=4)
        self.assertEqual(o[4], -110)
        self.assertEqual(o[12], 1)
        self.assertEqual(o[16], 0)


if __name__ == '__main__':
    unittest.main()
