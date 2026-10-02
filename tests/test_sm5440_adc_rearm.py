"""Actual vendor-backed preamble: no pump/ADC enable, lock-free20ms, PM/I2C errors."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_sm5714_policy import function
ROOT=Path(__file__).resolve().parents[1]
class RearmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        cls.source=(ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        code='''
#include <stdint.h>
#include <stdbool.h>
#include <errno.h>
struct sm5440_direct {int io_lock;void *regmap;bool stopped;};
#define SM5440_CNTL5 0x10
#define SM5440_MODE_MASK 0x0c
#define SM5440_ADCCNTL1 0x1c
#define SM5440_ADC_ENABLE 1
#define READ_ONCE(x) (x)
static int held,calls,fail,mode,adc,waits,errors,stop_in_wait;
static struct sm5440_direct *current;
static void mutex_lock(int *p){(void)p;held++;}
static void mutex_unlock(int *p){(void)p;held--;}
static int regmap_read(void *map,unsigned int reg,unsigned int *value){
 (void)map;if(!held||reg!=SM5440_CNTL5)errors++;calls++;
 if(calls==fail)return -EIO;*value=mode;return 0;}
static int regmap_update_bits(void *map,unsigned int reg,unsigned int mask,unsigned int value){
 (void)map;if(!held||reg!=SM5440_ADCCNTL1||mask!=1||value)errors++;
 calls++;if(calls==fail)return -EIO;adc&=~mask;return 0;}
static void msleep(unsigned int ms){
 if(held||ms!=20||(adc&1))errors++;waits++;
 if(stop_in_wait)current->stopped=true;}
'''+function(cls.source,'static int sm5440_adc_rearm(')+'''
int exercise(int failure,int initial_mode,int initial_stop,int cancel,int *out){
 struct sm5440_direct sm={0};current=&sm;sm.stopped=initial_stop;
 fail=failure;mode=initial_mode;adc=0xb;stop_in_wait=cancel;
 held=calls=waits=errors=0;int ret=sm5440_adc_rearm(&sm);
 out[0]=calls;out[1]=waits;out[2]=errors;out[3]=held;out[4]=adc;return ret;}
'''
        c=Path(cls.tmp.name)/'rearm.c';c.write_text(code);lib=c.with_suffix('.so')
        subprocess.run(['cc','-shared','-fPIC','-Wall','-Werror','-Wno-misleading-indentation',str(c),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.exercise.argtypes=[ctypes.c_int]*4+[ctypes.POINTER(ctypes.c_int)]
    def case(self,fail=0,mode=1,stopped=0,cancel=0):
        out=(ctypes.c_int*5)();ret=self.lib.exercise(fail,mode,stopped,cancel,out)
        self.assertEqual(out[2:4],[0,0]);return ret,list(out)
    def test_wait_after_verified_disable_without_lock(self):
        ret,r=self.case();self.assertEqual(ret,0);self.assertEqual(r,[2,1,0,0,10])
    def test_read_failure_does_not_write_or_wait(self):
        ret,r=self.case(fail=1);self.assertEqual(ret,-errno.EIO);self.assertEqual(r[:2],[1,0]);self.assertEqual(r[4],11)
    def test_disable_failure_does_not_wait(self):
        ret,r=self.case(fail=2);self.assertEqual(ret,-errno.EIO);self.assertEqual(r[:2],[2,0]);self.assertEqual(r[4],11)
    def test_active_or_reverse_mode_refused(self):
        for mode in [4,8,12,5,9,13]:
            ret,r=self.case(mode=mode);self.assertEqual(ret,-errno.EBUSY);self.assertEqual(r[:2],[1,0])
    def test_stopped_before_start_has_no_i2c(self):
        ret,r=self.case(stopped=1);self.assertEqual(ret,-errno.ESHUTDOWN);self.assertEqual(r[:2],[0,0])
    def test_pm_cancel_during_wait_keeps_adc_off(self):
        ret,r=self.case(cancel=1);self.assertEqual(ret,-errno.ESHUTDOWN);self.assertEqual(r[4]&1,0)
    def test_preamble_failure_cannot_start_converter(self):
        poll=function(self.source,'static void sm5440_poll(')
        self.assertIn('ret = sm5440_adc_rearm(sm);\n\tif (!ret)\n\t\tret = sm5440_sample_once(sm, &sample);',poll)
    def test_no_changes_to_frozen_converter_and_admission(self):
        old=subprocess.check_output(['git','show','f19377f6:kernel/drivers/sm5440-direct.c'],cwd=ROOT,text=True)
        for name in ['static int sm5440_sample_once(', 'static bool sm5440_startup_matches(',
                     'int sm5440_passive_request_fresh(', 'int sm5440_passive_observe(', 'static int sm5440_quiesce(']:
            self.assertEqual(function(self.source,name),function(old,name))
