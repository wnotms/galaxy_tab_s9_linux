"""Execute the actual sleepable API, with threaded unpublish and worker mocks."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class FreshRequestTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        header = (ROOT / 'kernel/drivers/sm5440-hw.h').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <time.h>
typedef uint8_t u8;typedef uint32_t u32;typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define READ_ONCE(x) __atomic_load_n(&(x),__ATOMIC_SEQ_CST)
#define WRITE_ONCE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_SEQ_CST)
typedef atomic_int atomic_t;
#define atomic_read(p) atomic_load(p)
#define atomic_inc(p) atomic_fetch_add(p,1)
#define atomic_set(p,v) atomic_store(p,v)
#define atomic_dec_and_test(p) (atomic_fetch_sub(p,1)==1)
static int atomic_cmpxchg(atomic_t *p,int old,int value) {
 atomic_compare_exchange_strong(p,&old,value);return old;
}
struct mutex {pthread_mutex_t value;int registry;};
struct wait_queue_head {pthread_mutex_t mutex;pthread_cond_t cond;};
typedef struct wait_queue_head wait_queue_head_t;
struct device {int unused;};struct regmap {int unused;};
struct delayed_work {int unused;};struct power_supply {int unused;};
struct dentry {int unused;};static void *system_wq;
static _Thread_local int registry_held,io_held;
static int errors,scenario,queued,drained,recursive_result;
static bool io_busy;static atomic_ullong clock_ms;
static u64 ktime_get_boottime(void) {return atomic_load(&clock_ms)*1000000ULL;}
#define ktime_to_ms(n) ((n)/1000000ULL)
#define msecs_to_jiffies(n) (n)
#define lockdep_assert_held(p) ((void)(p))
static void mutex_lock(struct mutex *m) {
 pthread_mutex_lock(&m->value);
 if(m->registry){if(io_held)errors++;registry_held++;}
 else io_held++;
}
static void mutex_unlock(struct mutex *m) {
 if(m->registry)registry_held--;else io_held--;
 pthread_mutex_unlock(&m->value);
}
static int mutex_trylock(struct mutex *m) {
 if(io_busy || pthread_mutex_trylock(&m->value))return 0;
 if(m->registry)registry_held++;else io_held++;return 1;
}
static void wake_up_all(wait_queue_head_t *q) {
 pthread_mutex_lock(&q->mutex);pthread_cond_broadcast(&q->cond);
 pthread_mutex_unlock(&q->mutex);
}
static void prepare_wait(void);
static void release_delay(void);
#define wait_event_timeout(q,condition,timeout) ({ \
 if(registry_held||io_held)errors++; \
 prepare_wait();long answer=0; \
 if(scenario!=12){ \
 struct timespec ts;clock_gettime(CLOCK_REALTIME,&ts);ts.tv_sec++; \
 pthread_mutex_lock(&(q).mutex); \
 while(!(condition)){ \
  if(pthread_cond_timedwait(&(q).cond,&(q).mutex,&ts)==ETIMEDOUT)break; \
 } \
 answer=(condition)?1:0;pthread_mutex_unlock(&(q).mutex); \
 } else atomic_fetch_add(&clock_ms,(timeout));answer; })
#define wait_event(q,condition) do { \
 if(registry_held||io_held)errors++;drained++; \
 pthread_mutex_lock(&(q).mutex); \
 while(!(condition))pthread_cond_wait(&(q).cond,&(q).mutex); \
 pthread_mutex_unlock(&(q).mutex); \
} while(0)
static void mod_delayed_work(void *wq,struct delayed_work *w,int delay) {
 (void)wq;(void)w;(void)delay;if(registry_held||!io_held)errors++;queued++;
}
''' + '#include "' + str(ROOT / 'kernel/drivers/sm5440-hw.h') + '"\n'
        for text, marker in ((header, 'struct sm5440_passive_measurement {'),
                             (src, 'struct sm5440_sample {'),
                             (src, 'struct sm5440_direct {')):
            code += function(text, marker) + ';\n'
        code += r'''
static struct mutex sm5440_companion_lock={PTHREAD_MUTEX_INITIALIZER,1};
static struct sm5440_direct *sm5440_companion,*current;
static pthread_t teardown;static bool teardown_started;
'''
        for marker in ('static int sm5440_publish(', 'static void sm5440_unpublish(',
                       'static int sm5440_sample_ready_locked(',
                       'static int sm5440_copy_sample_locked(',
                       'int sm5440_passive_request_fresh('):
            code += function(src, marker) + '\n'
        # Extend the real atomic-user decrement hook, without altering the API.
        code = code.replace('if (atomic_dec_and_test(&sm->request_users))',
                            'release_delay();\n\tif (atomic_dec_and_test(&sm->request_users))')
        code += r'''
static void *unbind(void *data) {sm5440_unpublish(data);return NULL;}
static void release_delay(void) {if(scenario==28)atomic_store(&clock_ms,1120);}
static void prepare_wait(void) {
 if(scenario==19){
  teardown_started=true;pthread_create(&teardown,NULL,unbind,current);return;
 }
 if(scenario==11){
  struct sm5440_passive_measurement other;
  recursive_result=sm5440_passive_request_fresh(&other);
 }
 if(scenario==12)return;
 mutex_lock(&current->io_lock);
 current->sample_seq++;current->sample.acquisition_seq=6;
 current->sample.acquired_ms=1005;atomic_store(&clock_ms,1080);
 current->sample.vbus_uv=9000000;current->sample.vbat_uv=4000000;
 current->sample.ibus_ua=625;current->sample.die_decic=300;
 if(scenario==13)atomic_store(&clock_ms,1101);
 if(scenario==14)current->sample.acquired_ms=999;
 if(scenario==15){current->sample.acquisition_seq=5;current->sample.acquired_ms=1000;}
 if(scenario==16)current->sample.acquired_ms=1081;
 if(scenario==17)current->stopped=true;
 if(scenario==18){current->request_epoch++;current->stopped=false;}
 if(scenario==21)current->last_sample_error=-EIO;
 if(scenario==22)current->sample.mode_after=4;
 if(scenario==23)current->sample.online=false;
 if(scenario==25)atomic_store(&clock_ms,999);
 if(scenario==26)current->sample_seq--;
 if(scenario==27)atomic_store(&clock_ms,1100);
 if(scenario==29)current->startup_confirmations=1;
 mutex_unlock(&current->io_lock);wake_up_all(&current->request_wait);
 if(scenario==20)io_busy=true;
}
static void init_queue(wait_queue_head_t *q) {
 pthread_mutex_init(&q->mutex,NULL);pthread_cond_init(&q->cond,NULL);
}
static void destroy_queue(wait_queue_head_t *q) {
 pthread_cond_destroy(&q->cond);pthread_mutex_destroy(&q->mutex);
}
int fresh_case(int kind,u64 *out) {
 struct sm5440_direct sm={0};struct sm5440_passive_measurement value={0};
 current=&sm;scenario=kind;errors=queued=drained=recursive_result=0;
 registry_held=io_held=0;io_busy=false;teardown_started=false;
 pthread_mutex_init(&sm.io_lock.value,NULL);init_queue(&sm.request_wait);
 init_queue(&sm.users_wait);sm5440_companion=NULL;
 atomic_init(&sm.request_users,0);atomic_init(&sm.request_busy,0);
 atomic_store(&clock_ms,1000);
 sm.sample.valid=sm.initial_sample_done=true;sm.sample.acquired_ms=1;
 sm.sample.online=true;sm.sample.mode_before=sm.sample.mode_after=1;
 sm.sample_seq=10;sm.conversion_seq=5;
 if(kind!=1)sm5440_publish(&sm);
 if(kind==3)sm.stopped=true;
 if(kind==4)sm.fault=true;
 if(kind==5)sm.sample.faults=1;
 if(kind==6)sm.last_sample_error=-EIO;
 if(kind==7)sm.startup_confirmations=1;
 if(kind==8)sm.sample.valid=false;
 if(kind==9)sm.sample.mode_before=4;
 if(kind==10)io_busy=true;
 if(kind==24){ /* simulate registry contention consuming initial deadline */
  atomic_store(&clock_ms,1100);
 }
 memset(&value,0xa5,sizeof(value));
 /* Inject start-time delay through the BOOTTIME primitive only for case24. */
 int ret=sm5440_passive_request_fresh(kind==2?NULL:&value);
 if(teardown_started)pthread_join(teardown,NULL);
 out[0]=value.observed_ms;out[1]=value.vbus_uv;out[2]=value.vbat_uv;
 out[3]=value.ibus_ua;out[4]=value.die_decic;out[5]=value.online;
 struct sm5440_passive_measurement zero={0};out[6]=!memcmp(&value,&zero,sizeof(value));
 out[7]=queued;out[8]=atomic_read(&sm.request_users);out[9]=atomic_read(&sm.request_busy);
 out[10]=errors+registry_held+io_held;out[11]=recursive_result;
 out[12]=teardown_started;out[13]=drained;
 io_busy=false;sm5440_unpublish(&sm);
 destroy_queue(&sm.request_wait);destroy_queue(&sm.users_wait);
 pthread_mutex_destroy(&sm.io_lock.value);return ret;
}
'''
        # Real request takes start before registry; inject contention at acquisition.
        code = code.replace('if(m->registry){if(io_held)errors++;registry_held++;}',
                            'if(m->registry){if(io_held)errors++;registry_held++;'
                            'if(scenario==24)atomic_fetch_add(&clock_ms,100);}')
        path = Path(cls.tmp.name) / 'fresh.c'
        path.write_text(code)
        binary = path.with_suffix('.so')
        proc = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                               '-Wno-misleading-indentation', '-pthread', '-shared',
                               '-fPIC', str(path), '-o', str(binary)],
                              capture_output=True, text=True)
        if proc.returncode:
            raise AssertionError(proc.stderr)
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.fresh_case.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]

    def read(self, kind=0):
        values = (ctypes.c_uint64 * 14)()
        ret = self.lib.fresh_case(kind, values)
        self.assertEqual(list(values)[8:11], [0, 0, 0])
        return ret, list(values)

    def refused(self, kind, code):
        ret, values = self.read(kind)
        self.assertEqual(ret, -code)
        self.assertEqual(values[6], 1, 'error must clear old destination')
        return values

    def test_new_conversion_preserves_units_and_acquisition_start(self):
        ret, values = self.read()
        self.assertEqual(ret, 0)
        self.assertEqual(values[:6], [1005, 9000000, 4000000, 625, 300, 1])
        self.assertEqual(values[7], 1)

    def test_absent_provider(self):
        self.assertEqual(self.refused(1, errno.ENODEV)[7], 0)

    def test_null_destination(self):
        ret, values = self.read(2)
        self.assertEqual(ret, -errno.EINVAL)
        self.assertEqual(values[7], 0)

    def test_stopped_provider_never_queues(self):
        self.assertEqual(self.refused(3, errno.ESHUTDOWN)[7], 0)

    def test_faults_and_i2c_error_never_queue(self):
        for kind in (4, 5, 6):
            with self.subTest(kind=kind):
                self.assertEqual(self.refused(kind, errno.EIO)[7], 0)

    def test_startup_pending_and_invalid_sample_never_queue(self):
        for kind in (7, 8):
            self.assertEqual(self.refused(kind, errno.EAGAIN)[7], 0)

    def test_active_mode_is_refused(self):
        self.assertEqual(self.refused(9, errno.EBUSY)[7], 0)

    def test_busy_io_is_refused_without_wait(self):
        self.assertEqual(self.refused(10, errno.EBUSY)[7], 0)

    def test_only_one_request_reserved(self):
        ret, values = self.read(11)
        self.assertEqual(ret, 0)
        self.assertEqual(ctypes.c_int64(values[11]).value, -errno.EBUSY)
        self.assertEqual(values[7], 1)

    def test_timeout_cannot_return_old_cache(self):
        self.refused(12, errno.ETIMEDOUT)

    def test_late_delivery_rejected(self):
        self.refused(13, errno.ETIMEDOUT)

    def test_older_acquisition_rejected(self):
        self.refused(14, errno.ESTALE)

    def test_old_inflight_conversion_in_same_millisecond_rejected(self):
        self.refused(15, errno.ESTALE)

    def test_future_timestamp_rejected(self):
        self.refused(16, errno.ESTALE)

    def test_suspend_wakes_and_refuses(self):
        self.refused(17, errno.ESHUTDOWN)

    def test_suspend_resume_cannot_restore_old_request_epoch(self):
        self.refused(18, errno.ESHUTDOWN)

    def test_concurrent_unpublish_drains_reference_before_free(self):
        values = self.refused(19, errno.ENODEV)
        self.assertEqual(values[12:14], [1, 1])

    def test_worker_busy_at_delivery_refused(self):
        self.refused(20, errno.EBUSY)

    def test_i2c_error_at_completion_refused(self):
        self.refused(21, errno.EIO)

    def test_mode_changed_during_conversion_refused(self):
        self.refused(22, errno.EBUSY)

    def test_detach_is_not_fabricated_online(self):
        ret, values = self.read(23)
        self.assertEqual(ret, 0)
        self.assertEqual(values[5], 0)

    def test_initial_registry_delay_consumes_budget(self):
        self.assertEqual(self.refused(24, errno.ETIMEDOUT)[7], 0)

    def test_clock_reversal_refused(self):
        self.refused(25, errno.ETIMEDOUT)

    def test_spurious_wake_without_new_completion_cannot_pass(self):
        self.refused(26, errno.ETIMEDOUT)

    def test_exact_total_delivery_boundary(self):
        self.assertEqual(self.read(27)[0], 0)

    def test_final_release_delay_consumes_budget(self):
        self.refused(28, errno.ETIMEDOUT)

    def test_startup_pending_at_completion_refused(self):
        self.refused(29, errno.EAGAIN)

    def test_hardware_sequence_and_user_interfaces_not_expanded(self):
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        api = function(src, 'int sm5440_passive_request_fresh(')
        self.assertNotIn('regmap_', api)
        self.assertNotIn('sm5440_off(', api)
        self.assertNotIn('cancel_delayed_work', api)
        self.assertNotIn('pps', api.lower())
        pm = function(src, 'static int sm5440_quiesce(')
        self.assertLess(pm.index('sm->stopped, true'), pm.index('cancel_delayed_work_sync'))
        self.assertLess(pm.index('mutex_unlock'), pm.index('cancel_delayed_work_sync'))
        converter = function(src, 'static int sm5440_sample_once(')
        self.assertIn('i < 12', converter)
        self.assertIn('msleep(25)', converter)
        self.assertIn('sample->acquisition_seq = ++sm->conversion_seq', converter)


if __name__ == '__main__':
    unittest.main()
