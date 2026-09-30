"""Execute actual cached-copy/seq/debugfs helpers without any I2C adapter."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class SnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
struct mutex { int unused; };
struct device { const char *name; };
struct regmap { int unused; };
struct power_supply { int unused; };
struct delayed_work { int unused; };
struct dentry { int unused; };
static unsigned long fake_jiffies;
#define jiffies fake_jiffies
#define msecs_to_jiffies(n) (n)
#define time_after(a,b) ((long)((b)-(a))<0)
#define time_before(a,b) time_after(b,a)
static u64 jiffies64_to_msecs(u64 n) { return n; }
static int locks,lock_depth,format_locked,mutate,once_reads;
#define READ_ONCE(x) (once_reads++,(x))
static void mutex_lock(struct mutex *m) { (void)m;locks++;lock_depth++; }
''' + function(src, 'struct sm5440_sample {') + ';\n'
        code += function(src, 'struct sm5440_direct {') + ';\n'
        code += function(src, 'struct sm5440_snapshot {') + ';\n'
        code += r'''
static struct sm5440_direct *current;
static void mutex_unlock(struct mutex *m) {
 (void)m;lock_depth--;
 if(mutate){current->sample.vbus_uv=999;current->fault=true;}
}
struct seq_file { void *private; char *buffer; size_t size; };
static void seq_puts(struct seq_file *s,const char *text) {
 if(lock_depth)format_locked++;
 size_t n=strlen(s->buffer);snprintf(s->buffer+n,s->size-n,"%s",text);
}
/* Kernel %*ph is not libc printf. Implement precisely that conversion while
 * the real driver's format/function bodies remain unmodified.
 */
static void seq_printf(struct seq_file *s,const char *fmt,...) {
 char buffer[2048];va_list args;va_start(args,fmt);
 if(strstr(fmt,"%*ph")) {
  char *out=buffer;const char *p=fmt;
  while(*p) {
   if(!strncmp(p,"%s",2)){const char *v=va_arg(args,const char *);out+=sprintf(out,"%s",v);p+=2;}
   else if(!strncmp(p,"%*ph",4)){
    int n=va_arg(args,int);const u8 *v=va_arg(args,const u8 *);
    for(int i=0;i<n;i++){out+=sprintf(out,"%s%02x",i?" ":"",v[i]);}
    p+=4;
   } else {*out++=*p++;}
  }
  *out=0;
 } else {vsnprintf(buffer,sizeof(buffer),fmt,args);}
 va_end(args);seq_puts(s,buffer);
}
static const int sm5440_snapshot_fops;
static int setup_failure,removed,permissions,registered;
static struct dentry directory,file;
static void (*cleanup)(void *);static void *cleanup_data;
#define IS_ERR_OR_NULL(p) (!(p) || (intptr_t)(p)<0)
static const char *dev_name(struct device *d) { return d->name; }
static struct dentry *debugfs_create_dir(const char *name,struct dentry *parent) {
 (void)name;(void)parent;
 if(setup_failure==1)return (void *)(intptr_t)-ENODEV;
 if(setup_failure==4)return NULL;
 return &directory;
}
static struct dentry *debugfs_create_file(const char *name,unsigned int mode,
 struct dentry *parent,void *data,const void *fops) {
 (void)name;(void)parent;(void)data;(void)fops;permissions=mode;
 return setup_failure==2?NULL:&file;
}
static void debugfs_remove(struct dentry *d) {if(d)removed++;}
static int devm_add_action_or_reset(struct device *d,void (*fn)(void *),void *data) {
 (void)d;if(setup_failure==3){fn(data);return -ENOMEM;}
 registered++;cleanup=fn;cleanup_data=data;return 0;
}
#define dev_dbg(...) ((void)0)
'''
        for marker in ['static void sm5440_snapshot_capture(',
                       'static void sm5440_snapshot_sample_show(',
                       'static int sm5440_snapshot_show(',
                       'static void sm5440_debugfs_remove(',
                       'static void sm5440_debugfs_init(']:
            code += function(src, marker) + '\n'
        code += r'''
void snapshot(int scenario,char *buffer) {
 struct sm5440_direct sm={0};current=&sm;locks=lock_depth=format_locked=0;
 mutate=once_reads=0;
 sm.initial_sample_done=true;fake_jiffies=120;
 sm.sample.valid=true;sm.sample.stamp=100;sm.sample.vbus_uv=9000000;
 sm.sample.vbat_uv=4000000;sm.sample.ibus_ua=0;sm.sample.die_decic=300;
 sm.sample.int4_wait=1;sm.sample.mode_before=sm.sample.mode_after=1;
 sm.sample.cntl2=0xf2;sm.sample.vbuscntl=0xe7;sm.sample.vbatcntl=0x37;sm.sample.prtncntl=0xfe;
 for(int i=0;i<11;i++)sm.sample.adc[i]=i+1;
 sm.startup_sample=sm.sample;sm.startup_sample.faults=0x80;
 sm.startup_sample.adc[0]=0x99;sm.startup_stamp=90;
 if(scenario==1)sm.initial_sample_done=false;
 if(scenario==2)sm.startup_confirmations=2;
 if(scenario==3)sm.fault=true;
 if(scenario==4)sm.stopped=true;
 if(scenario==5)fake_jiffies=2600;
 if(scenario==6)fake_jiffies=2601;
 if(scenario==7){sm.sample.valid=false;sm.last_sample_error=-EIO;}
 if(scenario==8)sm.sample.faults=2;
 if(scenario==9)fake_jiffies=(1UL<<32)+500;
 if(scenario==10)sm.sample.stamp=121;
 if(scenario==11)mutate=1;
 struct seq_file seq={.private=&sm,.buffer=buffer,.size=8192};buffer[0]=0;
 sm5440_snapshot_show(&seq,NULL);
}
int lock_stats(int index){return index==0?locks:index==1?lock_depth:index==2?format_locked:once_reads;}
void setup(int failure,int *output) {
 struct device dev={.name="0-0063"};struct sm5440_direct sm={.dev=&dev};
 setup_failure=failure;removed=permissions=registered=0;cleanup=NULL;
 sm5440_debugfs_init(&sm);
 output[0]=removed;output[1]=permissions;output[2]=registered;
 output[3]=sm.debug_root!=NULL;
 if(cleanup)cleanup(cleanup_data);
 output[4]=removed;output[5]=sm.debug_root!=NULL;
}
'''
        path = Path(cls.temp.name) / 'snapshot.c'
        path.write_text(code)
        binary = path.with_suffix('.so')
        try:
            subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                            '-shared', '-fPIC', str(path), '-o', str(binary)],
                           check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as exc:
            raise AssertionError(exc.stderr) from exc
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.snapshot.argtypes = [ctypes.c_int, ctypes.c_char_p]
        cls.lib.setup.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]

    def read(self, scenario=0):
        buffer = ctypes.create_string_buffer(8192)
        self.lib.snapshot(scenario, buffer)
        return dict(x.split('=', 1) for x in buffer.value.decode().splitlines())

    def test_cached_raw_and_explicit_units_preserved(self):
        value = self.read()
        self.assertEqual(value['sample_fresh'], '1')
        self.assertEqual(value['sample_age_ms'], '20')
        self.assertEqual(value['sample_vbus_uv'], '9000000')
        self.assertEqual(value['sample_vbat_uv'], '4000000')
        self.assertEqual(value['sample_adc'], '01 02 03 04 05 06 07 08 09 0a 0b')
        self.assertEqual(value['sample_cntl2'], '0xf2')

    def test_retained_startup_is_distinct_from_current(self):
        value = self.read()
        self.assertEqual(value['startup_retained'], '1')
        self.assertEqual(value['startup_capture_jiffies'], '90')
        self.assertEqual(value['startup_faults'], '0x80')
        self.assertTrue(value['startup_adc'].startswith('99 '))
        self.assertEqual(value['sample_faults'], '0x0')

    def test_no_sample_never_looks_fresh(self):
        value = self.read(1)
        self.assertEqual(value['sample_present'], '0')
        self.assertEqual(value['sample_fresh'], '0')

    def test_pending_fault_stopped_invalid_and_live_fault_are_unavailable(self):
        for case in (2, 3, 4, 7, 8):
            with self.subTest(case=case):
                self.assertEqual(self.read(case)['sample_fresh'], '0')
        self.assertEqual(self.read(2)['startup_pending'], '2')
        self.assertEqual(self.read(7)['last_sample_error'], '-5')

    def test_existing_passive_freshness_boundary(self):
        self.assertEqual(self.read(5)['sample_fresh'], '1')
        self.assertEqual(self.read(5)['sample_age_ms'], '2500')
        self.assertEqual(self.read(6)['sample_fresh'], '0')

    def test_long_fault_cache_age_does_not_truncate(self):
        value = self.read(9)
        self.assertEqual(int(value['sample_age_ms']), 2**32 + 400)
        self.assertEqual(value['sample_fresh'], '0')

    def test_future_timestamp_cannot_be_fresh(self):
        self.assertEqual(self.read(10)['sample_fresh'], '0')

    def test_one_coherent_copy_and_format_outside_lock(self):
        value = self.read(11)
        self.assertEqual(value['sample_vbus_uv'], '9000000')
        self.assertEqual(value['fault'], '0')
        self.assertEqual([self.lib.lock_stats(i) for i in range(3)], [1, 0, 0])
        self.assertEqual(self.lib.lock_stats(3), 1)

    def test_no_calibration_or_activation_claim(self):
        value = self.read()
        self.assertEqual(value['registers_are_cached'], '1')
        self.assertEqual(value['independently_calibrated'], '0')
        self.assertEqual(value['pump_enable_supported'], '0')

    def test_read_only_file_and_cleanup_registered(self):
        result = (ctypes.c_int * 6)()
        self.lib.setup(0, result)
        self.assertEqual(list(result), [0, 0o400, 1, 1, 1, 0])

    def test_absent_debugfs_and_partial_setup_leave_no_directory(self):
        for failure in (1, 2, 3, 4):
            with self.subTest(failure=failure):
                result = (ctypes.c_int * 6)()
                self.lib.setup(failure, result)
                self.assertEqual(result[3], 0)
                self.assertEqual(result[5], 0)
                self.assertEqual(result[4], 1 if failure in (2, 3) else 0)


if __name__ == '__main__':
    unittest.main()
