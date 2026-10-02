"""Execute the actual startup diagnostic; it never participates in admission."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_sm5714_policy import function
ROOT=Path(__file__).resolve().parents[1]

class StartupGaugeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        cls.source=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        code='''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;
struct power_supply {int unused;};union power_supply_propval {int intval;};
enum power_supply_property {POWER_SUPPLY_PROP_VOLTAGE_NOW};
static struct power_supply supply;static int absent,rc,voltage,gets,reads,puts,bad;
static u64 clock_ms;
#define ktime_to_ms(x) ((x)/1000000ULL)
static u64 ktime_get_boottime(void){return clock_ms*1000000ULL;}
static struct power_supply *power_supply_get_by_name(const char *name){
 gets++;if(strcmp(name,"sm5714-battery"))bad++;clock_ms+=2;return absent?0:&supply;}
static int power_supply_get_property(struct power_supply *p,
 enum power_supply_property prop,union power_supply_propval *value){
 reads++;if(p!=&supply||prop!=POWER_SUPPLY_PROP_VOLTAGE_NOW)bad++;
 clock_ms+=7;value->intval=voltage;return rc;}
static void power_supply_put(struct power_supply *p){puts++;if(p!=&supply)bad++;clock_ms++;}
'''
        code+=function(cls.source,'struct sm5440_sample {')+';\n'
        code+=function(cls.source,'static void sm5440_startup_gauge(')+'\n'
        code+='''
void exercise(int missing,int error,int uv,long long *out){
 struct sm5440_sample sample={.vbat_uv=3498500,.faults=128,.acquired_ms=925,
 .acquisition_seq=3,.mode_before=0,.mode_after=0};
 absent=missing;rc=error;voltage=uv;gets=reads=puts=bad=0;clock_ms=1000;
 sm5440_startup_gauge(&sample);
 out[0]=sample.gauge_attempted;out[1]=sample.gauge_ret;out[2]=sample.gauge_uv;
 out[3]=sample.adc_read_completed_ms;out[4]=sample.gauge_started_ms;
 out[5]=sample.gauge_completed_ms;out[6]=gets;out[7]=reads;out[8]=puts;out[9]=bad;
 out[10]=sample.vbat_uv;out[11]=sample.faults;out[12]=sample.acquired_ms;
 out[13]=sample.acquisition_seq;out[14]=sample.mode_before|sample.mode_after;}
'''
        c=Path(cls.tmp.name)/'diag.c';c.write_text(code);lib=c.with_suffix('.so')
        subprocess.run(['cc','-shared','-fPIC','-Wall','-Werror',str(c),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.exercise.argtypes=[ctypes.c_int]*3+[ctypes.POINTER(ctypes.c_longlong)]

    def run_case(self,missing=0,error=0,uv=3879000):
        out=(ctypes.c_longlong*15)();self.lib.exercise(missing,error,uv,out)
        self.assertEqual(out[9],0);self.assertEqual(list(out[10:]),[3498500,128,925,3,0])
        return list(out)
    def test_successful_pair_and_reference_release(self):
        self.assertEqual(self.run_case()[:9],[1,0,3879000,1000,1000,1010,1,1,1])
    def test_absent_supplier_is_unknown_without_retry(self):
        r=self.run_case(missing=1);self.assertEqual(r[1:3],[-errno.ENODEV,0]);self.assertEqual(r[6:9],[1,0,0])
    def test_io_error_preserved_and_reference_released(self):
        r=self.run_case(error=-errno.EIO);self.assertEqual(r[1:3],[-errno.EIO,0]);self.assertEqual(r[6:9],[1,1,1])
    def test_again_not_retried(self):
        r=self.run_case(error=-errno.EAGAIN);self.assertEqual(r[1],-errno.EAGAIN);self.assertEqual(r[7],1)
    def test_no_voltage_fabrication(self):
        for uv in [0,-1,5000000]:
            self.assertEqual(self.run_case(uv=uv)[2],uv)
    def test_distinct_acquisition_read_and_publication_times(self):
        r=self.run_case();self.assertLess(r[12],r[3]);self.assertLessEqual(r[3],r[4]);self.assertLess(r[4],r[5])
    def test_supplier_read_outside_io_lock_and_startup_only(self):
        poll=function(self.source,'static void sm5440_poll(')
        self.assertIn('if (!ret && (!sm->initial_sample_done || sm->startup_confirmations))',poll)
        self.assertLess(poll.index('sm5440_startup_gauge(&sample)'),poll.index('mutex_lock(&sm->io_lock)'))
        helper=function(self.source,'static void sm5440_startup_gauge(')
        self.assertNotIn('mutex_lock',helper);self.assertNotIn('regmap_',helper)
    def test_diagnostic_not_used_in_safety_predicates(self):
        for marker in ['static bool sm5440_passive_pc_sample(', 'static bool sm5440_startup_revblk(',
                       'static bool sm5440_startup_matches(', 'static int sm5440_sample_ready_locked(']:
            self.assertNotIn('gauge_',function(self.source,marker))
    def test_frozen_converter_and_freshness_unchanged(self):
        baseline=subprocess.check_output(['git','show','81f749a2:kernel/drivers/sm5440-direct.c'],cwd=ROOT,text=True)
        for marker in ['static int sm5440_sample_once(', 'int sm5440_passive_request_fresh(',
                       'int sm5440_passive_observe(', 'static int sm5440_quiesce(']:
            self.assertEqual(function(self.source,marker),function(baseline,marker))
    def test_voltage_supplier_reads_live_sram(self):
        source=(ROOT/'kernel/drivers/sm5714-battery.c').read_text()
        self.assertIn('sm5714_get_voltage(sm, SM5714_FG_SRAM_VBAT, &val->intval)',function(source,'static int sm5714_bat_get_property('))
        self.assertIn('sm5714_fg_read_sram',function(source,'static int sm5714_get_voltage('))
