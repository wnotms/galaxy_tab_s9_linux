"""Execute actual admitted ON -> park -> receipt/physical-proof resume -> stop."""
import ctypes
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import test_sm5440_actuator as fixture

ROOT = Path(__file__).resolve().parents[1]


class ParkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        p = Path(cls.tmp.name)
        fixture.ActuatorTests.setUpClass()
        try:
            shutil.copytree(Path(fixture.ActuatorTests.tmp.name) / 'linux', p / 'linux')
        finally:
            fixture.ActuatorTests.tearDownClass()
        (p / 'mock.c').write_text(r'''
#include <string.h>
#include "sm5440-actuator.h"
#include "sm5440-hw.h"
uint64_t fake_clock;
static u64 generation;
struct regmap {u8 reg[256],original[256];int phase,calls,fail_pause,fail_resume,persistent,
 uncertain,drop,step,on,off,unsafe,scenario,pause_off_call;};
static int bad(struct regmap *m){
 if(m->phase)m->calls++;fake_clock+=m->step;
 int fail=m->phase==1?m->fail_pause:m->phase==2?m->fail_resume:0;
 return fail && (m->calls==fail || (m->persistent && m->calls>=fail));
}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v){
 if(bad(m))return -5;*v=m->reg[r];return 0;
}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n){
 if(r!=8||n!=4)m->unsafe++;if(bad(m))return -5;memcpy(v,m->reg+r,n);return 0;
}
static void written(struct regmap *m,unsigned int r,unsigned int v){
 if(r==0x10){
  if((v&12)==4){if(m->phase)m->on++;if(m->phase==2 && m->scenario==20)generation++;
   if(m->phase==2 && m->scenario==21)v=1;}
  else if(!(v&12)){if(m->phase)m->off++;if(m->phase==1 && m->scenario==19)generation++;}
  else m->unsafe++;
 }
 else if(r==0x0c){if((v&1)||(!(v&128)&&(m->reg[0x10]&12)))m->unsafe++;}
 else if(r!=0x11 && r!=0x16 && r!=0x14 && r!=0x12)m->unsafe++;
 if(!(m->phase && m->calls==m->drop))m->reg[r]=v;
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int v){
 int b=bad(m);if(!b||m->uncertain)written(m,r,v);return b?-5:0;
}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int v){
 int b=bad(m);unsigned int next=(m->reg[r]&~mask)|(v&mask);
 if(m->phase==1 && r==0x10 && !(v&12))m->pause_off_call=m->calls;
 if((!b||m->uncertain)&&next!=m->reg[r])written(m,r,next);return b?-5:0;
}
void default_pause(int *out){struct regmap m={0};struct sm5440_actuator a={0};
 m.phase=1;out[0]=sm5440_actuator_pause(&m,&a);out[1]=m.calls;out[2]=m.on;out[3]=m.off;}
void exercise(int scenario,int fail_pause,int fail_resume,int persistent,int uncertain,int drop,int *o){
 struct regmap m={0};struct sm5440_actuator a={0};struct x710_charge_facts f={0};
 struct x710_physical_sample physical={0};struct sm5714_pd_snapshot p={0};unsigned int mv=9000,ma=1500;
 fake_clock=1000;generation=1;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x42;
 m.reg[0x0d]=0xf2;m.reg[0x0e]=0xb8;m.reg[0x0f]=0xff;m.reg[0x11]=0x89;
 m.reg[0x13]=0xe7;m.reg[0x15]=0x3f;m.reg[0x19]=0xfe;m.reg[0x1a]=0x0c;
 m.reg[0x16]=0x41;m.reg[0x14]=0x37;m.reg[0x12]=12;m.reg[0x1c]=0x82;
 memcpy(m.original,m.reg,256);
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
 p.budget_mv=9000;p.budget_ma=1500;p.online=2;p.usb_type=8;p.voltage_uv=9000000;p.current_ua=1500000;
 p.charge_requested=p.pps_contract=true;p.nr_source_pdos=1;
 p.source_pdos[0]=0xc0000000U|(110U<<17)|(33U<<8)|36;
 o[2]=sm5440_actuator_start(&m,&a,&f,&physical,&p,9000,1500);
 m.phase=1;m.scenario=scenario;m.fail_pause=fail_pause;m.fail_resume=fail_resume;
 m.persistent=persistent;m.uncertain=uncertain;m.drop=drop;
 if(scenario==3)generation++;
 if(scenario==15){fake_clock=1002;a.watchdog.serviced_ms=1;}
 if(scenario==16)m.reg[0x1c]|=1;
 if(scenario==18)m.reg[0x11]^=0x40;
 if(scenario==30)a.pause_sequence=~0ULL;
 o[3]=sm5440_actuator_pause(&m,&a);o[4]=m.calls;o[5]=m.reg[0x10];o[6]=m.reg[0x0c];
 o[7]=a.controls.pending;o[8]=a.watchdog.owned;o[9]=a.off_verified;o[10]=a.mode_possible;
 o[11]=a.operation_error;o[12]=a.cleanup_error;o[13]=m.pause_off_call;
 o[14]=sm5440_actuator_pause(&m,&a);o[15]=m.calls;
 if(o[3]==0){
  fake_clock+=60;p.budget_generation+=2;p.started_ms=p.completed_ms=f.observed_ms=physical.observed_ms=fake_clock;
  if(scenario==1){mv=9020;ma=1000;}
  if(scenario==2)ma=1800;
  p.budget_mv=mv;p.budget_ma=ma;p.voltage_uv=mv*1000;p.current_ua=ma*1000;physical.vbus_mv=mv;
  if(scenario==4)p.budget_generation=3;
  if(scenario==5)p.online=1;
  if(scenario==6)p.nr_source_pdos=0;
  if(scenario==7)p.started_ms=a.pause_started_ms-1;
  if(scenario==8){fake_clock=a.pause_started_ms+1001;p.started_ms=p.completed_ms=f.observed_ms=physical.observed_ms=fake_clock;}
  if(scenario==9)p.source_generation++;
  if(scenario==10)p.instance++;
  if(scenario==11)physical.ibus_ua=625;
  if(scenario==12)physical.vbus_mv=mv-120;
  if(scenario==13)f.software_ocp_verified=false;
  if(scenario==14)f.die_decic=420;
  if(scenario==17)m.reg[0x1c]|=1;
  if(scenario==23)p.completed_ms=fake_clock+1;
  if(scenario==24)physical.observed_ms=fake_clock-101;
  if(scenario==25)f.observed_ms=fake_clock-401;
  if(scenario==26)p.source_pdos[0]|=1U<<28;
  if(scenario==32)p.budget_generation=2;
  if(scenario==34)p.charge_requested=false;
  if(scenario==35)f.suspended=true;
  if(scenario==37)physical.observed_ms=p.completed_ms-1;
  m.phase=2;m.calls=0;if(scenario==22)m.step=4;
  o[16]=sm5440_actuator_resume(&m,&a,scenario==36?0:&f,&physical,&p,mv,ma);
  o[17]=m.calls;o[18]=m.reg[0x10];o[19]=a.active_mv;o[20]=a.active_ma;
  o[21]=m.reg[0x16];o[22]=m.reg[0x12];o[23]=a.budget_generation;o[24]=a.paused;
  o[25]=a.operation_error;o[26]=a.cleanup_error;o[27]=a.mode_possible;
  o[28]=sm5440_actuator_resume(&m,&a,&f,&physical,&p,mv,ma);o[29]=m.calls;
  if(scenario==29 && !o[16]){
   m.phase=1;m.calls=0;o[30]=sm5440_actuator_pause(&m,&a);
   fake_clock+=60;p.budget_generation+=2;p.started_ms=p.completed_ms=f.observed_ms=physical.observed_ms=fake_clock;
   m.phase=2;m.calls=0;o[31]=sm5440_actuator_resume(&m,&a,&f,&physical,&p,mv,ma);
  }
 }
 m.phase=3;m.calls=0;o[32]=sm5440_actuator_stop(&m,&a);o[33]=m.calls;
 o[34]=m.reg[0x10];o[35]=m.reg[0x0c];o[36]=a.mode_possible;o[37]=a.off_verified;
 o[38]=a.watchdog.owned;o[39]=a.controls.pending;o[40]=a.cleanup_error;
 o[41]=m.on;o[42]=m.off;o[43]=m.unsafe;o[44]=a.pause_sequence;
 o[45]=0;for(int i=0;i<256;i++)if(i!=0x1c && m.reg[i]!=m.original[i])o[45]++;
 o[46]=sm5440_actuator_stop(&m,&a);o[47]=m.calls;
}
''')
        names = ['sm5440-actuator.c', 'sm5440-control.c', 'sm5440-watchdog.c', 'x710-charging-policy.c']
        cmd = ['cc', '-shared', '-fPIC', '-std=c11', '-D__KERNEL__', '-Wall', '-Wextra',
               '-Werror', '-Wno-misleading-indentation', '-I' + str(p),
               '-I' + str(ROOT / 'kernel/drivers')]
        cmd += [str(ROOT / 'kernel/drivers' / n) for n in names]
        cmd += [str(p / 'mock.c'), '-o', str(p / 'park.so')]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(p / 'park.so'))
        cls.lib.exercise.argtypes = [ctypes.c_int] * 6 + [ctypes.POINTER(ctypes.c_int)]

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def case(self, scenario=0, fail_pause=0, fail_resume=0, persistent=0, uncertain=0, drop=0):
        out = (ctypes.c_int * 48)()
        self.lib.exercise(scenario, fail_pause, fail_resume, persistent, uncertain, drop, out)
        self.assertEqual(out[:3], [0, 0, 0])
        self.assertEqual(out[43], 0, 'unowned register/reset or WDT disabled while ON')
        self.assertEqual(out[14], -114)
        self.assertEqual(out[4], out[15], 'duplicate park does no I/O')
        if not out[3]:
            self.assertEqual(out[28], -114)
            self.assertEqual(out[17], out[29], 'duplicate resume does no I/O')
        self.assertEqual(out[32], out[46])
        self.assertEqual(out[33], out[47], 'terminal cleanup cannot retry')
        return list(out)

    def test_park_keeps_owned_settings_watchdog_then_refresh_resumes(self):
        o = self.case()
        self.assertEqual(o[3], 0)
        self.assertEqual(o[5:11], [1, 0xc2, 1, 1, 1, 0])
        self.assertEqual(o[16], 0)
        self.assertEqual(o[18:25], [5, 9000, 1500, 30, 8, 5, 0])
        self.assertEqual(o[32], 0)
        self.assertEqual(o[34:40], [1, 0x42, 0, 1, 0, 0])
        self.assertEqual(o[45], 0, 'every original byte restored')

    def test_retarget_reduces_current_and_frequency_without_losing_originals(self):
        o = self.case(1)
        self.assertEqual(o[16], 0)
        self.assertEqual(o[19:23], [9020, 1000, 20, 4])
        self.assertEqual(o[45], 0)

    def test_multiple_successful_park_cycles_have_advancing_receipts(self):
        o = self.case(29)
        self.assertEqual(o[30:32], [0, 0])
        self.assertEqual(o[44], 2)
        self.assertEqual(o[41], 2)
        self.assertEqual(o[45], 0)

    def test_disabled_unowned_default_pause_never_touches_bus(self):
        out = (ctypes.c_int * 4)()
        self.lib.default_pause(out)
        self.assertEqual(list(out), [-1, 0, 0, 0])

    def test_resume_rejects_old_capabilities_budget_native_time_and_unknown_source(self):
        for scenario in (2, 4, 5, 6, 7, 8, 9, 10, 23, 26, 32, 34):
            with self.subTest(scenario=scenario):
                o = self.case(scenario)
                self.assertLess(o[16], 0)
                self.assertEqual(o[41], 0)
                self.assertEqual(o[34], 1)

    def test_real_OFF_proof_ocp_pack_ADC_and_freshness_required(self):
        for scenario in (11, 12, 13, 14, 17, 22, 24, 25, 35, 36, 37):
            o = self.case(scenario)
            self.assertLess(o[16], 0)
            self.assertEqual(o[41], 0)
            self.assertEqual(o[34], 1)

    def test_cancel_pending_converter_drift_WDT_and_overflow_stop_instead_of_park(self):
        for scenario in (3, 15, 16, 18, 19, 30):
            o = self.case(scenario)
            self.assertLess(o[3], 0)
            self.assertEqual(o[41], 0)
            self.assertEqual(o[34], 1)

    def test_cancel_or_lost_mode_after_resume_ON_invokes_one_terminal_OFF(self):
        for scenario in (20, 21):
            o = self.case(scenario)
            self.assertLess(o[16], 0)
            self.assertEqual(o[41], 1)
            self.assertEqual(o[34], 1)
            self.assertEqual(o[45], 0)

    def test_every_pause_bus_fault_preserves_uncertainty_and_first_error(self):
        for call in range(1, self.case()[4] + 1):
            for uncertain in (0, 1):
                with self.subTest(call=call, uncertain=uncertain):
                    o = self.case(fail_pause=call, uncertain=uncertain)
                    self.assertEqual(o[3], -5)
                    self.assertEqual(o[11], -5)
                    self.assertEqual(o[41], 0)
                    if o[9]:
                        self.assertEqual(o[34], 1)
                    else:
                        self.assertEqual(o[12], -5)
                        self.assertEqual(o[38:40], [1, 1])

    def test_uncertain_first_pause_OFF_never_issues_hidden_second_OFF(self):
        call = self.case()[13]
        for fail in (call, call + 1):
            for uncertain in (0, 1):
                o = self.case(fail_pause=fail, uncertain=uncertain)
                self.assertEqual(o[3], -5)
                self.assertEqual(o[12], -5)
                self.assertEqual(o[33], 0)
                self.assertEqual(o[37:40], [0, 1, 1])
                self.assertEqual(o[35], 0xc2)

    def test_every_resume_bus_fault_stops_and_keeps_first_error(self):
        for scenario in (0, 1):
            for call in range(1, self.case(scenario)[17] + 1):
                with self.subTest(scenario=scenario, call=call):
                    o = self.case(scenario, fail_resume=call, uncertain=1)
                    self.assertEqual(o[16], -5)
                    self.assertEqual(o[25], -5)
                    self.assertEqual(o[34], 1)
                    self.assertLessEqual(o[41], 1)

    def test_persistent_resume_bus_loss_keeps_unverified_OFF_and_ownership(self):
        for call in range(1, self.case()[17] + 1):
            o = self.case(fail_resume=call, persistent=1)
            self.assertEqual(o[16], -5)
            self.assertEqual(o[26], -5)
            self.assertEqual(o[37:40], [0, 1, 1])


if __name__ == '__main__':
    unittest.main()
