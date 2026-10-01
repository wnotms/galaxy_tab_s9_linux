"""Execute the actual copy-only companion functions; no I2C mock exists."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class CachedConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(); cls.addClassCleanup(cls.tmp.cleanup)
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        header = (ROOT / 'kernel/drivers/sm5440-hw.h').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define lockdep_assert_held(x) ((void)(x))
typedef int atomic_t; typedef int wait_queue_head_t;
#define atomic_read(p) (*(p))
#define wake_up_all(p) ((void)(p))
#define wait_event(q,c) ((void)(q), (void)(c))
struct mutex {int registry;};struct device {int unused;};
struct regmap {int unused;};struct delayed_work {int unused;};
struct power_supply {int unused;};struct dentry {int unused;};
static u64 clock_ms;static int depth,order_error,registry_reads,io_reads;
static bool io_busy;
static u64 ktime_get_boottime(void) {return clock_ms*1000000ULL;}
#define ktime_to_ms(n) ((n)/1000000ULL)
static void mutex_lock(struct mutex *m) {
 if((m->registry && depth!=0)||(!m->registry && depth!=1))order_error++;
 depth++;if(m->registry)registry_reads++;else io_reads++;
}
static void mutex_unlock(struct mutex *m) {
 if((m->registry && depth!=1)||(!m->registry && depth!=2))order_error++;
 depth--;
}
static int mutex_trylock(struct mutex *m) {
 if(io_busy)return 0;
 mutex_lock(m);return 1;
}
''' + '#include "' + str(ROOT / 'kernel/drivers/sm5440-hw.h') + '"\n'
        for text, marker in ((header, 'struct sm5440_passive_measurement {'),
                             (src, 'struct sm5440_sample {'),
                             (src, 'struct sm5440_direct {')):
            code += function(text, marker) + ';\n'
        code += 'static struct mutex sm5440_companion_lock={.registry=1};\n'
        code += 'static struct sm5440_direct *sm5440_companion;\n'
        for marker in ('static int sm5440_publish(', 'static void sm5440_unpublish(',
                       'static int sm5440_sample_ready_locked(',
                       'static int sm5440_copy_sample_locked(',
                       'int sm5440_passive_read_cached('):
            code += function(src, marker) + '\n'
        code += r'''
int read_case(int kind,u64 stamp,u64 now,u64 *out) {
 struct sm5440_direct sm={0};struct sm5440_passive_measurement value;
 sm.initial_sample_done=sm.sample.valid=true;sm.sample.acquired_ms=stamp;
 sm.sample.vbus_uv=9000000;sm.sample.vbat_uv=4000000;
 sm.sample.ibus_ua=625;sm.sample.die_decic=300;sm.sample.online=true;
 clock_ms=now;sm5440_companion=NULL;depth=order_error=registry_reads=io_reads=0;
 io_busy=kind==13;
 if(kind!=1)sm5440_publish(&sm);
 if(kind==2)sm.stopped=true;
 if(kind==3)sm.fault=true;
 if(kind==4)sm.sample.faults=1;
 if(kind==5)sm.last_sample_error=-EIO;
 if(kind==6)sm.initial_sample_done=false;
 if(kind==7)sm.sample.valid=false;
 if(kind==8)sm.startup_confirmations=1;
 if(kind==9)sm.sample.mode_before=4;
 if(kind==10)sm.sample.mode_after=8;
 if(kind==11)sm.sample.online=false;
 memset(&value,0xa5,sizeof(value));registry_reads=io_reads=0;
 int ret=sm5440_passive_read_cached(kind==12?NULL:&value);
 out[0]=value.observed_ms;out[1]=value.vbus_uv;out[2]=value.vbat_uv;
 out[3]=value.ibus_ua;out[4]=value.die_decic;out[5]=value.online;
 struct sm5440_passive_measurement zero={0};out[6]=!memcmp(&value,&zero,sizeof(value));
 out[7]=registry_reads;out[8]=io_reads;out[9]=order_error;out[10]=depth;
 sm5440_unpublish(&sm);return ret;
}
int lifetime_case(int wrong) {
 struct sm5440_direct one={0},two={0};sm5440_companion=NULL;
 depth=order_error=registry_reads=io_reads=0;
 if(sm5440_publish(&one))return 1;
 if(sm5440_publish(&two)!=-EBUSY || sm5440_companion!=&one)return 2;
 sm5440_unpublish(wrong?&two:&one);
 if(sm5440_companion!=(wrong?&one:NULL))return 3;
 sm5440_unpublish(&one);return order_error || depth || sm5440_companion!=NULL;
}
'''
        path = Path(cls.tmp.name) / 'consumer.c'; path.write_text(code)
        binary = path.with_suffix('.so')
        result = subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                                 '-shared', '-fPIC', str(path), '-o', str(binary)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.read_case.argtypes = [ctypes.c_int, ctypes.c_uint64, ctypes.c_uint64,
                                     ctypes.POINTER(ctypes.c_uint64)]

    def read(self, kind=0, stamp=900, now=1000):
        out = (ctypes.c_uint64 * 11)()
        ret = self.lib.read_case(kind, stamp, now, out)
        self.assertEqual(list(out)[9:], [0, 0])
        return ret, list(out)

    def test_coherent_values_units_and_original_acquisition_time(self):
        ret, out = self.read()
        self.assertEqual(ret, 0)
        self.assertEqual(out[:6], [900, 9000000, 4000000, 625, 300, 1])
        self.assertEqual(out[7:9], [1, 1])

    def test_exact_age_boundary_and_zero_age(self):
        for stamp in (900, 999, 1000):
            self.assertEqual(self.read(stamp=stamp)[0], 0)
        ret, out = self.read(stamp=899)
        self.assertLess(ret, 0); self.assertEqual(out[6], 1)

    def test_zero_future_and_large_age_clear_previous_destination(self):
        for stamp, now in ((0, 1000), (1001, 1000), (1, 2**63), (1, 0)):
            ret, out = self.read(stamp=stamp, now=now)
            self.assertLess(ret, 0); self.assertEqual(out[6], 1)

    def test_fault_pending_unavailable_stopped_or_active_cannot_publish(self):
        for kind in range(1, 11):
            ret, out = self.read(kind=kind)
            self.assertLess(ret, 0); self.assertEqual(out[6], 1)
            self.assertEqual(out[8], 0 if kind == 1 else 1)

    def test_offline_is_a_fact_not_fabricated_online(self):
        ret, out = self.read(kind=11)
        self.assertEqual(ret, 0); self.assertEqual(out[5], 0)

    def test_null_destination_refused_before_locks(self):
        ret, out = self.read(kind=12)
        self.assertLess(ret, 0); self.assertEqual(out[7:9], [0, 0])

    def test_busy_worker_io_refused_without_wait_under_registry(self):
        ret, out = self.read(kind=13)
        self.assertLess(ret, 0)
        self.assertEqual(out[6:9], [1, 1, 0])

    def test_publish_duplicate_and_unpublish_identity_lifetime(self):
        for wrong in (0, 1):
            self.assertEqual(self.lib.lifetime_case(wrong), 0)

    def test_teardown_unpublishes_before_debugfs_worker_memory(self):
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        probe = function(src, 'static int sm5440_probe(')
        self.assertLess(probe.index('sm5440_debugfs_init(sm)'),
                        probe.index('sm5440_unpublish, sm'))
        self.assertLess(probe.index('sm5440_unpublish, sm'),
                        probe.index('sm5440_publish(sm)'))
        self.assertLess(probe.index('sm5440_publish(sm)'),
                        probe.index('schedule_delayed_work'))


if __name__ == '__main__':
    unittest.main()
