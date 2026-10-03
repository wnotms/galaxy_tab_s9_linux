"""Run the actual fixed9 OFF coordinator/control C against framework/bus faults."""
import ctypes
import errno
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_sm5440_adc_condition import condition_fixture_source, ROOT
from test_sm5714_policy import function


class FixedContextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        source = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        code = condition_fixture_source(source)
        code = code.replace('static int depth,errors,', 'static int scenario,source_calls,pack_calls,acquires,checks;\nstatic int depth,errors,')
        code = code.replace('memcpy(v,regs+r,n);', '''
 if(r==SM5440_INT1 && scenario==12 && current->conversion_seq>=2)regs[r+2]|=2;
 memcpy(v,regs+r,n);''')
        code = code.replace('regs[r]=(regs[r]&~mask)|(v&mask);', '''regs[r]=(regs[r]&~mask)|(v&mask);
 if(scenario==21 && r==SM5440_CNTL6 && !(v&SM5440_ENHIZ))regs[SM5440_STATUS1+2]|=2;''')
        code += '#include "'+str(ROOT/'kernel/drivers/sm5714-stage2.h')+'"\n'
        code += r'''
#include <stdlib.h>
#include <limits.h>
#define ARRAY_SIZE(x) (sizeof(x)/sizeof((x)[0]))
#define WRITE_ONCE(x,v) ((x)=(v))
enum power_supply_property {POWER_SUPPLY_PROP_PRESENT,POWER_SUPPLY_PROP_HEALTH,
 POWER_SUPPLY_PROP_CAPACITY,POWER_SUPPLY_PROP_VOLTAGE_NOW,POWER_SUPPLY_PROP_TEMP};
enum {POWER_SUPPLY_HEALTH_GOOD=1,POWER_SUPPLY_USB_TYPE_PD=3};
union power_supply_propval {int intval;};
static struct power_supply supplier;
static void foreign(void){if(depth)errors++;}
static struct power_supply *power_supply_get_by_name(const char *n){
 foreign();if(strcmp(n,"sm5714-battery"))errors++;return scenario==28?NULL:&supplier;}
static void power_supply_put(struct power_supply *s){(void)s;foreign();}
static int power_supply_get_property(struct power_supply *p,enum power_supply_property prop,
 union power_supply_propval *v){
 (void)p;foreign();pack_calls++;
 int values[]={1,POWER_SUPPLY_HEALTH_GOOD,35,4000000,300};
 if(scenario==5)values[4]=380;if(scenario==6)values[0]=0;
 if(scenario==7)values[2]=80;if(scenario==8)values[3]=4300000;
 if(scenario==9)return -EIO;
 if(scenario==26 && current->context.phase==8)values[3]=INT_MIN;
 if(scenario==23 && current->context.phase==3 && prop==POWER_SUPPLY_PROP_TEMP)clock_ms+=450;
 if(scenario==24 && current->context.phase==6 && prop==POWER_SUPPLY_PROP_TEMP)clock_ms+=450;
 if(scenario==27)clock_ms+=110;
 v->intval=values[prop];return 0;}
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *s){
 foreign();source_calls++;memset(s,0,sizeof(*s));
 if(scenario==29)return -ENODATA;
 s->instance=1;s->source_generation=1;s->budget_generation=1;
 s->started_ms=s->completed_ms=clock_ms;s->budget_mv=9000;s->budget_ma=1500;
 s->online=1;s->usb_type=POWER_SUPPLY_USB_TYPE_PD;
 s->voltage_uv=9000000;s->current_ua=1500000;s->charge_requested=true;
 if(scenario==1){s->budget_mv=5000;s->voltage_uv=5000000;}
 if(scenario==2)s->pps_contract=true;
 if(scenario==3)s->started_ms-=501;
 if(scenario==15 && current->context.phase==6)s->source_generation++;
 if(scenario==16 && current->context.phase==6)s->online=0;
 if(scenario==17 && current->context.phase==6)current->stopped=true;
 if(scenario==19 && current->context.phase==7)s->budget_generation++;
 if(scenario==20 && current->context.phase==7)regs[SM5440_STATUS1+2]|=2;
 if(scenario==25 && current->context.phase==7)clock_ms+=450;
 return 0;}
int sm5714_battery_switching_acquire(u64 *l){
 foreign();acquires++;*l=scenario==13||scenario==31?0:99;
 return scenario==13||scenario==14?-EIO:0;}
int sm5714_battery_switching_check(u64 l){
 foreign();checks++;if(l!=99)errors++;return scenario==18?-ESTALE:0;}
'''
        code += re.sub(r'^#include[^\n]*\n', '', (ROOT/'kernel/drivers/sm5440-control.c').read_text(), flags=re.M)
        for name in ['static void sm5440_startup_gauge(',
                     'static void sm5440_context_publish(', 'static int sm5440_context_source(',
                     'static int sm5440_context_pack(', 'static int sm5440_context_observe(',
                     'static bool sm5440_context_physical(', 'static bool sm5440_context_inactive(',
                     'static int sm5440_context_restore_settings(', 'static int sm5440_fixed_context_cycle(']:
            code += function(source, name)+'\n'
        code += r'''
int context_case(int scen,int failure,int second,long long *out){
 struct sm5440_direct sm={0};struct sm5440_sample sample={0};struct regmap map={0};
 sm.regmap=&map;current=&sm;scenario=scen;
 depth=errors=calls=waits=started=writes=never_ready=stop_wait=wrong_read=0;
 source_calls=pack_calls=acquires=checks=0;clock_ms=1000;fail=failure;fail2=second;
 memset(regs,0,sizeof(regs));
 regs[SM5440_DEVICEID]=0x21;regs[SM5440_CNTL5]=1;regs[SM5440_CNTL6]=0x89;
 regs[SM5440_ADCCNTL1]=12;regs[SM5440_CNTL2]=0xf2;
 regs[SM5440_VBUSCNTL]=0xe7;regs[SM5440_VBATCNTL]=0x37;regs[SM5440_PRTNCNTL]=0xfe;
 regs[0x16]=0xc1;regs[0x12]=0xf0;
 unsigned int vbat=(4000000-2048000)/500,vbus=(9000000-4096000)/1000;
 if(scenario==4)vbus=(5000000-4096000)/1000;
 regs[SM5440_ADC_VBUS]=vbus>>5;regs[SM5440_ADC_VBUS+1]=(vbus&31)<<3;
 regs[SM5440_ADC_VBUS+8]=7;regs[SM5440_ADC_VBUS+9]=vbat>>5;
 regs[SM5440_ADC_VBUS+10]=(vbat&31)<<3;regs[SM5440_STATUS1+2]=32;
 if(scenario==10)regs[SM5440_ADC_VBUS+5]=8;
 if(scenario==11||scenario==12)regs[SM5440_INT1+2]=2;
 if(scenario==22)regs[SM5440_STATUS1+2]|=2;
 if(scenario==30)regs[SM5440_STATUS1+2]|=64;
 int ret=sm5440_fixed_context_cycle(&sm,&sample);
 struct sm5440_context *c=&sm.context;
 out[0]=calls;out[1]=errors;out[2]=depth;out[3]=ret;out[4]=c->phase;
 out[5]=c->error;out[6]=c->cleanup_error;out[7]=c->lease;out[8]=c->lease_retained;
 out[9]=acquires;out[10]=checks;out[11]=source_calls;out[12]=pack_calls;
 out[13]=sm.context_attempted;out[14]=sm.condition_attempted;out[15]=sm.enhiz_restore_pending;
 out[16]=c->controls.pending;out[17]=c->controls.state;out[18]=c->controls.operation_error;
 out[19]=c->controls.restore_error;out[20]=regs[SM5440_CNTL5]&SM5440_MODE_MASK;
 out[21]=regs[SM5440_ADCCNTL1]&1;out[22]=regs[SM5440_CNTL6];
 out[23]=regs[0x16];out[24]=regs[SM5440_VBATCNTL];out[25]=regs[0x12];
 out[26]=sample.pre_status_valid;out[27]=sample.pre_status[2];out[28]=sample.faults;
 out[29]=c->initial.faults;out[30]=c->confirmation.faults;out[31]=c->before.faults;
 out[32]=c->inactive_revblk;out[33]=c->confirmation.acquisition_seq;out[34]=c->before.acquisition_seq;
 out[35]=c->handoff.acquisition_seq;out[36]=sample.acquisition_seq;
 out[37]=sample.gauge_uv;out[38]=sample.vbat_uv;out[39]=clock_ms;out[40]=writes;
 out[41]=c->controls.before[0];out[42]=c->controls.before[1];out[43]=c->controls.before[2];
 out[44]=sample.condition_error;out[45]=sample.restore_error;out[46]=sample.valid;
 for(int i=0;i<writes;i++){
  unsigned int r=write_regs[i],mask=write_masks[i],v=write_values[i];
  if(r==SM5440_CNTL6){if(mask!=SM5440_ENHIZ||(v&~SM5440_ENHIZ))out[1]++;}
  else if(r==SM5440_CNTL5){if(mask!=SM5440_MODE_MASK || (v&SM5440_MODE_MASK))out[1]++;}
  else if(r==SM5440_ADCCNTL1){if(mask&~(SM5440_ADC_ENABLE|SM5440_ADC_RATE|SM5440_ADC_AVG32))out[1]++;}
  else if(r==SM5440_ADCCNTL2){if(v!=SM5440_ADC_CHANNELS)out[1]++;}
  else if(r==0x16){if(mask!=0x7f)out[1]++;}
  else if(r==SM5440_VBATCNTL){if(mask!=0x3f)out[1]++;}
  else if(r==0x12){if(mask!=0x1f)out[1]++;}
  else out[1]++;
 }
 return ret;}
'''
        c = Path(cls.tmp.name)/'context.c';c.write_text(code)
        lib=c.with_suffix('.so')
        subprocess.run(['cc','-shared','-fPIC','-Wall','-Werror','-Wno-misleading-indentation',str(c),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib))
        cls.lib.context_case.argtypes=[ctypes.c_int]*3+[ctypes.POINTER(ctypes.c_longlong)]

    def run_case(self, scenario=0, failure=0, second=0):
        out=(ctypes.c_longlong*47)()
        ret=self.lib.context_case(scenario,failure,second,out)
        self.assertEqual(list(out[1:3]),[0,0],'locks and actual register write scope')
        self.assertEqual(out[20],0,'never pump ON')
        return ret,list(out)

    def test_actual_fixed9_handoff_condition_and_original_settings_restored(self):
        ret,r=self.run_case()
        self.assertEqual(ret,0);self.assertEqual(r[4:9],[10,0,0,99,1])
        self.assertEqual(r[9],1);self.assertGreater(r[10],0)
        self.assertEqual(r[13:20],[1,1,0,0,2,0,0])
        self.assertEqual(r[21:29],[0,0x89,0xc1,0x37,0xf0,1,32,0])
        self.assertEqual(r[35:39],[2,3,4000000,4000000])
        self.assertEqual(r[41:44],[0xc1,0x37,0xf0])

    def test_valid_five_volts_pps_and_stale_source_no_converter_or_handoff(self):
        for scenario in [1,2,3]:
            with self.subTest(scenario=scenario):
                ret,r=self.run_case(scenario);self.assertLess(ret,0)
                self.assertEqual([r[0],r[9],r[14],r[40]],[0,0,0,0])

    def test_pack_fault_presence_soc_vbat_thermal_or_missing_sensor_before_bus(self):
        for scenario in [5,6,7,8,9,27,28]:
            with self.subTest(scenario=scenario):
                ret,r=self.run_case(scenario);self.assertLess(ret,0)
                self.assertEqual([r[0],r[9],r[14],r[40]],[0,0,0,0])

    def test_logical_nine_is_not_physical_vbus_current_live_fault_or_uvlo_proof(self):
        for scenario in [4,10,22,30]:
            with self.subTest(scenario=scenario):
                ret,r=self.run_case(scenario);self.assertLess(ret,0)
                self.assertEqual([r[9],r[14],r[21]],[0,0,0])

    def test_original_inactive_revblk_retained_and_two_new_confirmations(self):
        ret,r=self.run_case(11);self.assertEqual(ret,0)
        self.assertEqual(r[29:35],[128,0,0,1,2,3])
        self.assertEqual(r[35:37],[4,5]);self.assertEqual(r[8],1)

    def test_repeated_revblk_refused_before_switching_lease(self):
        ret,r=self.run_case(12);self.assertEqual(ret,-errno.EIO)
        self.assertEqual(r[29:31],[128,128]);self.assertEqual(r[9],0)
        self.assertEqual(r[32],0)

    def test_acquire_error_nonzero_lease_is_retained_but_no_authorization(self):
        for scenario,lease in [(13,0),(14,99),(31,0)]:
            ret,r=self.run_case(scenario);self.assertEqual(ret,-errno.EIO)
            self.assertEqual(r[7:9],[lease,int(bool(lease))]);self.assertEqual(r[14],0)

    def test_source_change_detach_pm_and_lease_revocation_after_handoff(self):
        for scenario in [15,16,17,18]:
            with self.subTest(scenario=scenario):
                ret,r=self.run_case(scenario);self.assertLess(ret,0)
                self.assertEqual(r[7:9],[99,1]);self.assertEqual(r[14],0)

    def test_epoch_change_after_settings_restores_without_enhiz_clear(self):
        ret,r=self.run_case(19);self.assertEqual(ret,-errno.ESTALE)
        self.assertEqual(r[14:20],[0,0,0,2,0,0]);self.assertEqual(r[23:26],[0xc1,0x37,0xf0])

    def test_live_pre_status_captured_before_enhiz_mutation(self):
        ret,r=self.run_case(20);self.assertLess(ret,0)
        self.assertEqual(r[26:28],[1,34]);self.assertEqual(r[22],0x89)
        self.assertEqual(r[16],0);self.assertEqual(r[23:26],[0xc1,0x37,0xf0])

    def test_new_live_fault_after_clear_is_preserved_and_exact_restore(self):
        ret,r=self.run_case(21);self.assertLess(ret,0)
        self.assertEqual(r[26:29],[1,32,128]);self.assertEqual(r[22],0x89)
        self.assertEqual(r[23:26],[0xc1,0x37,0xf0]);self.assertEqual(r[8],1)

    def test_oldest_adc_age_rechecked_after_pack_and_source_latency(self):
        for scenario in [23,24,25]:
            with self.subTest(scenario=scenario):
                ret,r=self.run_case(scenario);self.assertEqual(ret,-errno.ESTALE)
                self.assertEqual(r[14],0)
                self.assertEqual(r[9],0 if scenario==23 else 1)
                self.assertEqual(r[16],0)

    def test_malformed_gauge_integer_refused_before_delta_subtraction(self):
        ret,r=self.run_case(26);self.assertEqual(ret,-errno.ERANGE)
        self.assertEqual(r[37],-(2**31));self.assertEqual(r[22],0x89)

    def test_not_ready_source_bounded_and_no_mutation(self):
        ret,r=self.run_case(29);self.assertEqual(ret,-errno.ENODATA)
        self.assertEqual([r[0],r[9],r[11],r[39],r[40]],[0,0,40,5000,0])

    def test_each_real_bus_failure_stops_preserving_first_error(self):
        _,clean=self.run_case()
        for fail in range(1,clean[0]+1):
            with self.subTest(bus_step=fail):
                ret,r=self.run_case(failure=fail);self.assertEqual(ret,-errno.EIO)
                self.assertEqual(r[5],-errno.EIO)
                if r[7]:self.assertEqual(r[8],1)
                if not r[15]:self.assertEqual(r[22],0x89)
                if not r[16]:self.assertEqual(r[23:26],[0xc1,0x37,0xf0])

    def test_failed_cleanup_pending_not_retried_or_granted(self):
        _,clean=self.run_case()
        found=[]
        for fail in range(1,clean[0]+1):
            ret,r=self.run_case(failure=fail)
            if r[15] or r[16]:found.append(fail);self.assertLess(r[6],0)
        self.assertTrue(found,'exercise real restoration uncertainty')

    def test_no_protocol_setter_release_or_activation_in_actual_coordinator(self):
        source=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        body=function(source,'static int sm5440_fixed_context_cycle(')
        for forbidden in ['sm5714_pd_request_pps','sm5714_pd_restore_fixed','sm5714_pd_release_fixed',
                          'sm5714_battery_switching_release','SM5440_MODE_ON']:
            self.assertNotIn(forbidden,body)
        self.assertIn('sample->pre_status',function(source,'static int sm5440_condition_begin('))
