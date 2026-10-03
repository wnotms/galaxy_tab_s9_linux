"""Actual mode/settings/watchdog/core C on an injected bus; no hardware caller."""
import ctypes
import errno
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_sm5714_policy import function

ROOT=Path(__file__).resolve().parents[1]

class ActuatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();p=Path(cls.tmp.name);(p/'linux/usb').mkdir(parents=True)
        pd=(ROOT/'.work/linux-mainline/include/linux/usb/pd.h').read_text()
        pp='#include <linux/types.h>\n#include <linux/bitops.h>\n#define min(x,y) ((x)<(y)?(x):(y))\n'
        pp+=function(pd,'enum pd_pdo_type {')+';\n'
        # Use the actual pinned Linux protocol macros/helpers, not a parallel RDO encoder.
        names=['PD_MAX_PAYLOAD','PDO_TYPE_SHIFT','PDO_TYPE_MASK','PDO_FIXED_VOLT_SHIFT',
               'PDO_VOLT_MASK','PDO_VAR_MAX_CURR_SHIFT','PDO_CURR_MASK','RDO_OBJ_POS_SHIFT',
               'RDO_OBJ_POS_MASK','RDO_CAP_MISMATCH','RDO_CURR_MASK','RDO_FIXED_OP_CURR_SHIFT',
               'RDO_FIXED_MAX_CURR_SHIFT','RDO_PROG_VOLT_MASK','RDO_PROG_CURR_MASK',
               'RDO_PROG_VOLT_SHIFT','RDO_PROG_CURR_SHIFT','RDO_PROG_VOLT_MV_STEP','RDO_PROG_CURR_MA_STEP',
               'RDO_OBJ','PDO_PROG_OUT_VOLT','PDO_PROG_OP_CURR','RDO_PROG']
        lines=pd.splitlines()
        for name in names:
            index=next(i for i,l in enumerate(lines) if re.match(r'^#define '+name+r'(?:\s|\()',l))
            while True:
                pp+=lines[index]+'\n'
                if not lines[index].endswith('\\'):break
                index+=1
        for name in ('pdo_type','pdo_fixed_voltage','pdo_max_current','rdo_index','rdo_op_current','rdo_max_current'):
            pp+=function(pd,'static inline '+('enum pd_pdo_type ' if name=='pdo_type' else 'unsigned int ')+name+'(')+'\n'
        ps=(ROOT/'.work/linux-mainline/include/linux/power_supply.h').read_text()
        headers={
            'types.h':'#ifndef MOCK_TYPES\n#define MOCK_TYPES\n#include <stdint.h>\n#include <stdbool.h>\n#include <stddef.h>\ntypedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;\n#endif\n',
            'bitops.h':'#define BIT(n) (1U << (n))\n#define GENMASK(h,l) (((~0U) >> (31-(h))) & ((~0U) << (l)))\n',
            'errno.h':''.join('#define '+name+' '+str(code)+'\n' for code,name in errno.errorcode.items()),
            'compiler.h':'#define READ_ONCE(x) (x)\n',
            'ktime.h':'#include <stdint.h>\nextern uint64_t fake_clock;\nstatic inline uint64_t ktime_get_boottime(void){return fake_clock;}\n#define ktime_to_ms(v) (v)\n',
            'module.h':'#define MODULE_DESCRIPTION(x)\n#define MODULE_LICENSE(x)\n',
            'power_supply.h':function(ps,'enum power_supply_usb_type {')+';\n',
            'usb/pd.h':pp,
            'regmap.h':'struct regmap;\nint regmap_read(struct regmap *,unsigned int,unsigned int *);\nint regmap_write(struct regmap *,unsigned int,unsigned int);\nint regmap_bulk_read(struct regmap *,unsigned int,void *,unsigned int);\nint regmap_update_bits(struct regmap *,unsigned int,unsigned int,unsigned int);\n'}
        for name,data in headers.items():(p/'linux'/name).write_text(data)
        harness=r'''
#include <string.h>
#include "sm5440-actuator.h"
#include "sm5440-hw.h"
uint64_t fake_clock;
static u64 generation;
struct regmap {u8 reg[256],original[256];int calls,writes,on,unsafe,fail,persistent,uncertain,drop,step,inject;};
static int bad(struct regmap *m){m->calls++;fake_clock+=m->step;
 return m->fail&&(m->calls==m->fail||(m->persistent&&m->calls>=m->fail));}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v){
 if(bad(m))return -5;*v=m->reg[r];return 0;}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n){
 if(r!=8||n!=4)m->unsafe++;if(bad(m))return -5;memcpy(v,m->reg+r,n);return 0;}
static void written(struct regmap *m,unsigned int r,unsigned int value){
 m->writes++;
 if(r==0x0c){if((value&1) || (!(value&128)&&(m->reg[0x10]&12)))m->unsafe++;}
 else if(r==0x10){if((value&12)==4)m->on++;else if(value&12)m->unsafe++;}
 else if(r!=0x11&&r!=0x16&&r!=0x14&&r!=0x12)m->unsafe++;
 if(m->calls!=m->drop)m->reg[r]=value;
 if(r==0x11 && !(value&128) && m->inject==1)generation++;
 if(r==0x10 && value&4){
  if(m->inject==2)generation++;
  if(m->inject==3)m->reg[0x0a]|=2;
  if(m->inject==4)m->reg[0x10]=1;
 }
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int value){
 int b=bad(m);if(!b||m->uncertain)written(m,r,value);return b?-5:0;}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int value){
 int b=bad(m);unsigned int next=(m->reg[r]&~mask)|(value&mask);
 if((!b||m->uncertain)&&next!=m->reg[r])written(m,r,next);return b?-5:0;}
void exercise(int scenario,int fail,int persistent,int uncertain,int drop,int step,int *o){
 struct regmap m={0};struct sm5440_actuator a={0};struct x710_charge_facts f={0};
 struct x710_physical_sample physical={0};struct sm5714_pd_snapshot source={0};
 fake_clock=100;generation=1;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x42;
 m.reg[0x0d]=0xf2;m.reg[0x0e]=0xb8;m.reg[0x0f]=0xff;m.reg[0x11]=0x89;
 m.reg[0x13]=0xe7;m.reg[0x15]=0x3f;m.reg[0x19]=0xfe;m.reg[0x1a]=0x0c;
 m.reg[0x16]=0x41;m.reg[0x14]=0x37;m.reg[0x12]=12;memcpy(m.original,m.reg,256);
 a.enabled=true;a.switching_inhibited=true;a.generation=&generation;a.epoch=1;
 a.instance=7;a.source_generation=2;a.budget_generation=3;a.lease=99;
 o[0]=sm5440_control_prepare(&m,1500,&a.controls);
 o[1]=sm5440_watchdog_arm_off(&m,&a.watchdog,1,100);
 f.epoch=1;f.observed_ms=100;f.capacity=30;f.pack_decic=310;f.die_decic=300;f.vbat_mv=3800;
 f.fixed_mv=9000;f.apdo_min_mv=3300;f.apdo_max_mv=11000;f.apdo_ma=1800;
 f.attached=f.battery_present=f.healthy=f.pack_valid=f.voltage_valid=f.soc_valid=true;
 f.die_valid=f.adc_valid=f.fixed_healthy=f.apdo=f.thermal_normal=f.software_ocp_verified=true;
 physical.observed_ms=100;physical.vbus_mv=9000;physical.vbat_mv=3800;
 physical.valid=physical.online=true;
 source.instance=7;source.source_generation=2;source.budget_generation=3;
 source.started_ms=source.completed_ms=100;source.budget_mv=9000;source.budget_ma=1500;
 source.online=2;source.usb_type=8;source.voltage_uv=9000000;source.current_ua=1500000;
 source.charge_requested=source.pps_contract=true;source.nr_source_pdos=1;
 source.source_pdos[0]=0xc0000000U|(110U<<17)|(33U<<8)|36;
 if(scenario==1)a.enabled=false;
 if(scenario==2)f.software_ocp_verified=false;
 if(scenario==3)a.switching_inhibited=false;
 if(scenario==4)generation=2;
 if(scenario==5)physical.observed_ms=1; /* starts100, before I/O age99 */
 if(scenario==6)f.pack_decic=420;
 if(scenario==7)physical.ibus_ua=625;
 if(scenario==8)m.reg[0x14]^=1;
 if(scenario==9)m.reg[0x0d]^=1;
 if(scenario==10)m.reg[0x0a]|=2;
 if(scenario==11)a.watchdog.owned=false;
 if(scenario==12)physical.vbus_mv=10501;
 if(scenario==13)f.observed_ms=101;
 if(scenario==14)a.watchdog.serviced_ms=1;
 if(scenario==15)m.reg[0x11]=0x88;
 if(scenario>=16&&scenario<=19)m.inject=scenario-15;
 if(scenario==20)source.online=1;
 if(scenario==21)source.pps_contract=false;
 if(scenario==22)source.current_ua=1800000;
 if(scenario==23)source.instance=8;
 if(scenario==24)source.source_generation=3;
 if(scenario==25)source.budget_generation=4;
 if(scenario==26)source.source_pdos[0]=0x0002d12c; /* fixedPDO only */
 if(scenario==27)source.source_pdos[0]|=1U<<28; /* AVS */
 if(scenario==28)source.source_pdos[0]|=1U<<25; /* reserved APDO bit */
 if(scenario==29)source.nr_source_pdos=0;
 if(scenario==30)f.fault=true;
 if(scenario==31){physical.valid=false;physical.observed_ms=0;}
 if(scenario==32)a.lease=0;
 if(scenario==34){sm5440_actuator_stop(&m,&a);a.enabled=true;}
 m.calls=m.writes=m.on=0;m.fail=fail;m.persistent=persistent;
 m.uncertain=uncertain;m.drop=drop;m.step=step;fake_clock=100;
 if(scenario==14)fake_clock=1102;
 o[2]=sm5440_actuator_start(&m,&a,&f,&physical,&source,9000,1500);
 o[3]=m.calls;o[4]=m.on;o[5]=m.reg[0x10];o[6]=m.reg[0x11];
 o[7]=a.operation_error;o[8]=a.cleanup_error;o[9]=a.mode_possible;o[10]=a.off_verified;
 o[11]=a.enhiz_owned;o[12]=a.watchdog.owned;o[13]=a.controls.pending;
 o[14]=sm5440_actuator_start(&m,&a,&f,&physical,&source,9000,1500);o[15]=m.calls;
 if(scenario==33){m.fail=m.calls+1;m.persistent=1;}
 o[16]=sm5440_actuator_stop(&m,&a);
 o[17]=m.reg[0x10];o[18]=m.reg[0x11];o[19]=m.reg[0x0c];o[20]=a.mode_possible;
 o[21]=a.off_verified;o[22]=a.watchdog.owned;o[23]=a.controls.pending;o[24]=a.cleanup_error;
 o[25]=m.calls;o[26]=m.on;o[27]=m.unsafe;
 o[28]=0;for(int i=0;i<256;i++)if(m.reg[i]!=m.original[i])o[28]++;
 o[29]=a.operation_error;
 o[30]=sm5440_actuator_stop(&m,&a);o[31]=m.calls;
}
'''
        (p/'mock.c').write_text(harness)
        names=['sm5440-actuator.c','sm5440-control.c','sm5440-watchdog.c','x710-charging-policy.c']
        cls.sources=names
        cmd=['cc','-shared','-fPIC','-std=c11','-D__KERNEL__','-Wall','-Wextra','-Werror',
             '-Wno-misleading-indentation','-I'+str(p),'-I'+str(ROOT/'kernel/drivers')]
        cmd += [str(ROOT/'kernel/drivers'/n) for n in names]+[str(p/'mock.c'),'-o',str(p/'actuator.so')]
        result=subprocess.run(cmd,capture_output=True,text=True)
        if result.returncode:raise AssertionError(result.stdout+result.stderr)
        cls.lib=ctypes.CDLL(str(p/'actuator.so'));cls.lib.exercise.argtypes=[ctypes.c_int]*6+[ctypes.POINTER(ctypes.c_int)]

    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()

    def case(self,scenario=0,fail=0,persistent=0,uncertain=0,drop=0,step=0):
        out=(ctypes.c_int*32)();self.lib.exercise(scenario,fail,persistent,uncertain,drop,step,out)
        self.assertEqual(out[0:2],[0,0]);self.assertEqual(out[27],0,'unsafe field/reset/early WDT disable')
        self.assertEqual(out[14],-114);self.assertEqual(out[3],out[15],'no repeated start I/O')
        return list(out)

    def test_actual_helpers_start_then_restore_all_original_bytes(self):
        o=self.case();self.assertEqual(o[2],0);self.assertEqual(o[4:7],[1,5,9])
        self.assertEqual(o[9],1);self.assertEqual(o[16:24],[0,1,137,66,0,1,0,0])
        self.assertEqual(o[28],0);self.assertEqual(o[29],0)

    def test_default_off_no_ocp_or_switching_lease_cannot_energize(self):
        for scenario in (1,2,3,4,6,7,11,12,13,14,30,31,32):
            with self.subTest(scenario=scenario):
                o=self.case(scenario);self.assertLess(o[2],0);self.assertEqual(o[4],0);self.assertEqual(o[5]&12,0)

    def test_freshness_expires_during_register_checks_before_on(self):
        o=self.case(5,step=1);self.assertEqual(o[2],-116);self.assertEqual(o[4],0)
        o=self.case(step=5);self.assertEqual(o[2],-116);self.assertEqual(o[4],0)

    def test_prepared_fields_witnesses_live_fault_or_invalid_hiz_refused(self):
        for scenario in (8,9,10,15):
            o=self.case(scenario);self.assertLess(o[2],0);self.assertEqual(o[4],0)

    def test_source_mode_mirror_epochs_and_real_pps_offer_are_mandatory(self):
        for scenario in range(20,30):
            with self.subTest(scenario=scenario):
                o=self.case(scenario);self.assertLess(o[2],0);self.assertEqual(o[4],0)

    def test_generation_change_before_on_aborts_and_restores(self):
        o=self.case(16);self.assertEqual(o[2],-125);self.assertEqual(o[4],0);self.assertEqual(o[8],0)
        self.assertEqual(o[28],0)

    def test_post_on_epoch_fault_or_mode_loss_forces_checked_off(self):
        for scenario in (17,18,19):
            o=self.case(scenario);self.assertLess(o[2],0);self.assertEqual(o[4],1)
            self.assertEqual(o[5]&12,0);self.assertTrue(o[10]);self.assertEqual(o[9],0)

    def test_every_start_io_error_and_uncertain_write_preserves_first_error(self):
        total=self.case()[3]
        for fail in range(1,total+1):
            for uncertain in (0,1):
                with self.subTest(fail=fail,uncertain=uncertain):
                    o=self.case(fail=fail,uncertain=uncertain)
                    self.assertEqual(o[2],-5);self.assertEqual(o[7],-5);self.assertEqual(o[29],-5)
                    self.assertEqual(o[5]&12,0);self.assertTrue(o[10])

    def test_unproven_off_keeps_watchdog_and_settings_owned(self):
        o=self.case(33);self.assertEqual(o[2],0);self.assertEqual(o[16],-5)
        self.assertEqual(o[17]&12,4);self.assertEqual(o[20],1);self.assertFalse(o[21])
        self.assertTrue(o[22]);self.assertTrue(o[23]);self.assertEqual(o[19]&128,128)

    def test_persistent_start_bus_loss_never_claims_off_or_disables_wdt(self):
        for fail in range(1,self.case()[3]+1):
            with self.subTest(fail=fail):
                o=self.case(fail=fail,persistent=1,uncertain=1)
                self.assertEqual(o[2],-5);self.assertEqual(o[8],-5);self.assertFalse(o[10])
                self.assertTrue(o[12]);self.assertTrue(o[13]);self.assertEqual(o[19]&128,128)

    def test_each_ignored_start_write_is_detected_or_has_no_write_effect(self):
        refused=0
        for drop in range(1,self.case()[3]+1):
            o=self.case(drop=drop)
            if o[2]:
                refused+=1;self.assertEqual(o[2],-5);self.assertEqual(o[5]&12,0);self.assertTrue(o[10])
            else:self.assertEqual(o[5]&12,4);self.assertEqual(o[6],9)
        self.assertGreaterEqual(refused,2) # both ENHIZ and CHG_ON are checked

    def test_each_cleanup_error_is_visible_without_reenabling_pump(self):
        clean=self.case()
        for fail in range(clean[3]+1,clean[25]+1):
            with self.subTest(fail=fail):
                o=self.case(fail=fail)
                self.assertEqual(o[2],0);self.assertEqual(o[16],-5);self.assertEqual(o[24],-5)
                self.assertEqual(o[26],1,'cleanup must not issue another ON')

    def test_cleanup_is_single_attempt_even_after_error(self):
        for scenario in (0,16,17,18,33):
            o=self.case(scenario);self.assertEqual(o[30],o[24]);self.assertEqual(o[31],o[25])

    def test_stop_cannot_be_followed_by_manual_rearm(self):
        o=self.case(34);self.assertEqual(o[2],-114);self.assertEqual(o[3],0);self.assertEqual(o[4],0)

if __name__=='__main__':unittest.main()
