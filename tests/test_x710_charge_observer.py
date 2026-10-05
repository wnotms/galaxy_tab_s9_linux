"""Run the linked observer C, substituting native suppliers and kernel scheduling.

Threaded tests cover timeout/drain, PM cancellation and publication races. They
do not establish physical ADC calibration, cutoff latency or charging readiness.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        d = Path(cls.tmp.name)
        (d / 'linux').mkdir()
        for name in ('types', 'bitops', 'completion', 'errno', 'ktime', 'module',
                     'mutex', 'power_supply', 'string', 'suspend', 'workqueue'):
            (d / 'linux' / (name + '.h')).write_text('/* kernel ABI mock */\n')
        (d / 'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        code = r'''
#define _POSIX_C_SOURCE 200809L
#define __KERNEL__
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <pthread.h>
#include <stdatomic.h>
#include <stdlib.h>
#include <time.h>
typedef uint8_t u8; typedef uint32_t u32; typedef uint64_t u64;
/* Catch kernel namespace collisions that plain userspace types conceal. */
void *kernel_current_task(void);
#define current kernel_current_task()
#define U64_MAX UINT64_MAX
#define BIT(n) (1U << (n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define min(a,b) ((a)<(b)?(a):(b))
struct mutex {pthread_mutex_t native;};
#define DEFINE_MUTEX(n) struct mutex n={PTHREAD_MUTEX_INITIALIZER}
static void mutex_lock(struct mutex *m){pthread_mutex_lock(&m->native);}
static void mutex_unlock(struct mutex *m){pthread_mutex_unlock(&m->native);}
static bool mutex_trylock(struct mutex *m){return !pthread_mutex_trylock(&m->native);}
struct completion {pthread_mutex_t lock; pthread_cond_t cond; bool done;};
#define DECLARE_COMPLETION(n) struct completion n={PTHREAD_MUTEX_INITIALIZER,PTHREAD_COND_INITIALIZER,false}
static void reinit_completion(struct completion *c){pthread_mutex_lock(&c->lock);c->done=false;pthread_mutex_unlock(&c->lock);}
static void complete_all(struct completion *c){pthread_mutex_lock(&c->lock);c->done=true;pthread_cond_broadcast(&c->cond);pthread_mutex_unlock(&c->lock);}
static int wait_for_completion_timeout(struct completion *c,unsigned int ms){
 struct timespec deadline;clock_gettime(CLOCK_REALTIME,&deadline);
 deadline.tv_sec+=ms/1000;deadline.tv_nsec+=(ms%1000)*1000000L;
 if(deadline.tv_nsec>=1000000000L){deadline.tv_sec++;deadline.tv_nsec-=1000000000L;}
 pthread_mutex_lock(&c->lock);int ret=0;
 while(!c->done&&!ret)ret=pthread_cond_timedwait(&c->cond,&c->lock,&deadline);
 int done=c->done;pthread_mutex_unlock(&c->lock);return done;
}
#define msecs_to_jiffies(ms) (ms)
static atomic_uint_fast64_t clock_ms;
static u64 ktime_get_boottime(void){return atomic_load(&clock_ms)*1000000;}
#define ktime_to_ms(n) ((n)/1000000)
#define POWER_SUPPLY_HEALTH_GOOD 1
#define POWER_SUPPLY_USB_TYPE_PD_PPS 3
#define POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS 4
#define __init
#define device_initcall(x)
#define EXPORT_SYMBOL_GPL(x)
#define MODULE_DESCRIPTION(x)
#define MODULE_LICENSE(x)
#define PM_SUSPEND_PREPARE 1
#define PM_HIBERNATION_PREPARE 2
#define PM_RESTORE_PREPARE 3
#define PM_POST_SUSPEND 4
#define PM_POST_HIBERNATION 5
#define PM_POST_RESTORE 6
#define NOTIFY_OK 1
#define NOTIFY_DONE 0
struct notifier_block {int (*notifier_call)(struct notifier_block *,unsigned long,void *);};
static int notifier_error;
static int register_pm_notifier(struct notifier_block *nb){(void)nb;return notifier_error;}
struct work_struct {void (*func)(struct work_struct *);};
#define DECLARE_WORK(n,f) struct work_struct n={f}
struct workqueue_struct {pthread_t thread;};
static pthread_mutex_t wq_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t wq_cond=PTHREAD_COND_INITIALIZER;
static struct work_struct *pending;
static bool running,quit,queue_fail,defer_work;
static atomic_int cancel_started;
static void *wq_loop(void *unused){(void)unused;pthread_mutex_lock(&wq_lock);
 while(!quit){while((!pending||defer_work)&&!quit)pthread_cond_wait(&wq_cond,&wq_lock);
  if(quit)break;struct work_struct *job=pending;pending=NULL;running=true;
  pthread_mutex_unlock(&wq_lock);job->func(job);pthread_mutex_lock(&wq_lock);
  running=false;pthread_cond_broadcast(&wq_cond);
 }pthread_mutex_unlock(&wq_lock);return NULL;
}
#define WQ_MEM_RECLAIM 1
static bool allocation_fail;
static struct workqueue_struct *alloc_ordered_workqueue(const char *name,int flags){
 (void)name;(void)flags;if(allocation_fail)return NULL;
 struct workqueue_struct *q=calloc(1,sizeof(*q));quit=false;defer_work=false;
 pthread_create(&q->thread,NULL,wq_loop,NULL);return q;
}
static bool queue_work(struct workqueue_struct *q,struct work_struct *job){
 (void)q;pthread_mutex_lock(&wq_lock);bool ok=!pending&&!queue_fail;
 if(ok){pending=job;pthread_cond_broadcast(&wq_cond);}pthread_mutex_unlock(&wq_lock);return ok;
}
static void cancel_work_sync(struct work_struct *job){(void)job;atomic_store(&cancel_started,1);
 pthread_mutex_lock(&wq_lock);pending=NULL;
 while(running)pthread_cond_wait(&wq_cond,&wq_lock);pthread_mutex_unlock(&wq_lock);
}
static void destroy_workqueue(struct workqueue_struct *q){
 pthread_mutex_lock(&wq_lock);quit=true;pthread_cond_broadcast(&wq_cond);pthread_mutex_unlock(&wq_lock);
 pthread_join(q->thread,NULL);free(q);
}
'''
        code += '#include "' + str(ROOT / 'kernel/drivers/x710-charge-observer.c') + '"\n'
        code += r'''
static atomic_int events,sources,packs,adcs,lock_errors;
static int scenario,fail_event,block_event;
static pthread_mutex_t barrier_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t barrier_cond=PTHREAD_COND_INITIALIZER;
static bool blocked,released;
static int event(void){
 if(!pthread_mutex_trylock(&x710_observer_lock.native))pthread_mutex_unlock(&x710_observer_lock.native);
 else atomic_fetch_add(&lock_errors,1);
 int n=atomic_fetch_add(&events,1)+1;
 if(n==block_event){pthread_mutex_lock(&barrier_lock);blocked=true;pthread_cond_broadcast(&barrier_cond);
  while(!released)pthread_cond_wait(&barrier_cond,&barrier_lock);pthread_mutex_unlock(&barrier_lock);}
 atomic_fetch_add(&clock_ms,1);
 if(scenario==19&&n==2){mutex_lock(&x710_observer_lock);x710_observer_generation++;mutex_unlock(&x710_observer_lock);}
 return n==fail_event?-EIO:0;
}
static bool owned_mode(void){return scenario==1||scenario==22;}
static unsigned int mv(void){return owned_mode()?8800:(scenario==26||scenario==27)?5000:9000;}
static unsigned int ma(void){return owned_mode()?1800:scenario==26?1800:scenario==27?1850:1500;}
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *out){
 int ret=event();if(ret)return ret;int n=atomic_fetch_add(&sources,1)+1;
 *out=(struct sm5714_pd_snapshot){.instance=11,.source_generation=12,.budget_generation=13,
  .started_ms=atomic_load(&clock_ms)-1,.completed_ms=atomic_load(&clock_ms),
  .nr_source_pdos=2,.budget_mv=mv(),.budget_ma=ma(),.online=owned_mode()?2:1,
  .usb_type=3,.voltage_uv=(int)(mv()*1000),.current_ua=(int)(ma()*1000),
  .charge_requested=true,.pps_contract=owned_mode(),.source_pdos={0x1234,0x5678}};
 if(n==2){if(scenario==2)out->instance++;if(scenario==3)out->source_generation++;
  if(scenario==4)out->budget_generation++;if(scenario==5)out->source_pdos[1]++;
  if(scenario==20)atomic_store(&clock_ms,500);}
 if(scenario==13&&n==1)out->started_ms=1;
 if(scenario==21){out->budget_ma=2000;out->current_ua=2000000;}
 if(scenario==22){out->budget_mv=8801;out->voltage_uv=8801000;}
 return 0;
}
int sm5714_pd_read_owned_snapshot(u64 instance,u64 gen,u64 lease,struct sm5714_pd_snapshot *out){
 if(instance!=11||gen!=12||lease!=99)return -ESTALE;
 return sm5714_pd_read_snapshot(out);
}
int sm5714_battery_read_pack(u64 lease,struct sm5714_pack_snapshot *out){
 int ret=event();if(ret)return ret;int n=atomic_fetch_add(&packs,1)+1;
 *out=(struct sm5714_pack_snapshot){.instance=21,.state_generation=22,.switching_lease=lease,
  .started_ms=atomic_load(&clock_ms)-1,.completed_ms=atomic_load(&clock_ms),
  .typec_mv=mv(),.typec_ma=ma(),.capacity=30,.voltage_uv=3800000,.current_ua=-300000,
  .pack_decic=300,.health=POWER_SUPPLY_HEALTH_GOOD,.battery_present=true,.attached=true,
  .thermal_normal=true,.typec_owned=true,.typec_charge=true,.pps_contract=owned_mode()};
 if(n==2){if(scenario==6)out->instance++;if(scenario==7)out->state_generation++;}
 if((scenario==8&&n==1)||(scenario==9&&n==2))out->pack_decic=450;
 if(scenario==17)out->voltage_uv=4440000;
 if(scenario==18)out->switching_lease++;
 if(scenario==21)out->typec_ma=2000;
 if(scenario==22)out->typec_mv=8801;
 if(scenario==24)out->health=2;
 return 0;
}
int sm5440_passive_request_fresh(struct sm5440_passive_measurement *out){
 int ret=event();if(ret)return ret;atomic_fetch_add(&adcs,1);
 *out=(struct sm5440_passive_measurement){.observed_ms=atomic_load(&clock_ms)-1,
  .vbus_uv=mv()*1000,.vbat_uv=3800000,.ibus_ua=0,.die_decic=300,.online=true};
 if(scenario==11)atomic_fetch_add(&clock_ms,101);
 if(scenario==12)out->observed_ms+=1000;
 if(scenario==14)out->ibus_ua=625;
 if(scenario==15)out->die_decic=420;
 if(scenario==16)out->vbus_uv+=150000;
 if(scenario==23)out->vbat_uv=4300000;
 return 0;
}
static void reset(int mode,int failure){
 if(!x710_observer_wq){notifier_error=0;allocation_fail=false;x710_observer_init();}
 cancel_work_sync(&x710_observer_job);mutex_lock(&x710_observer_lock);
 x710_observer_inflight=false;x710_observer_quiescing=false;x710_observer_generation=1;
 x710_observer_result=(struct x710_charge_observation){};mutex_unlock(&x710_observer_lock);
 atomic_store(&clock_ms,1000);atomic_store(&events,0);atomic_store(&sources,0);
 atomic_store(&packs,0);atomic_store(&adcs,0);atomic_store(&lock_errors,0);
 atomic_store(&cancel_started,0);scenario=mode;fail_event=failure;block_event=0;
 blocked=released=false;queue_fail=false;defer_work=false;
}
static struct x710_observer_owner owner(void){
 return owned_mode()?(struct x710_observer_owner){11,12,99}:(struct x710_observer_owner){};
}
static void output(int ret,const struct x710_charge_observation *result,int64_t *out){
 out[0]=ret;out[1]=atomic_load(&events);out[2]=atomic_load(&adcs);out[3]=atomic_load(&lock_errors);
 out[4]=result->generation;out[5]=result->oldest_ms;out[6]=result->completed_ms;
 out[7]=result->source.started_ms;out[8]=result->physical.observed_ms;
 out[9]=result->pack.started_ms;out[10]=result->pack.switching_lease;
 out[11]=result->source.budget_mv;out[12]=x710_observer_inflight;
 out[13]=x710_observer_result.generation;out[14]=x710_observer_error;
}
void run(int mode,int failure,int64_t *out){
 reset(mode,failure);struct x710_observer_owner o=owner();struct x710_charge_observation result;
 memset(&result,0xff,sizeof(result));int ret=x710_charge_request_observation(&o,&result);
 cancel_work_sync(&x710_observer_job);output(ret,&result,out);
}
struct request {int ret;struct x710_charge_observation result;};
static void *request_thread(void *ptr){struct request *r=ptr;struct x710_observer_owner o=owner();
 r->ret=x710_charge_request_observation(&o,&r->result);return NULL;}
static void *pm_thread(void *unused){(void)unused;x710_observer_pm(NULL,PM_SUSPEND_PREPARE,NULL);return NULL;}
static void wait_blocked(void){pthread_mutex_lock(&barrier_lock);
 while(!blocked)pthread_cond_wait(&barrier_cond,&barrier_lock);pthread_mutex_unlock(&barrier_lock);}
static void release_provider(void){pthread_mutex_lock(&barrier_lock);released=true;
 pthread_cond_broadcast(&barrier_cond);pthread_mutex_unlock(&barrier_lock);}
void race(int mode,int64_t *out){
 reset(0,0);block_event=mode==1?3:1;struct request first={};pthread_t t,pm;
 if(mode==3){ /* timeout while still queued: job must keep its original generation */
  block_event=0;pthread_mutex_lock(&wq_lock);defer_work=true;pthread_mutex_unlock(&wq_lock);
  pthread_create(&t,NULL,request_thread,&first);pthread_join(t,NULL);
  struct x710_observer_owner o=owner();struct x710_charge_observation second={};
  int ret=x710_charge_request_observation(&o,&second);
  pthread_mutex_lock(&wq_lock);defer_work=false;pthread_cond_broadcast(&wq_cond);
  while(pending||running)pthread_cond_wait(&wq_cond,&wq_lock);pthread_mutex_unlock(&wq_lock);
  output(first.ret,&first.result,out);out[15]=ret;return;
 }
 pthread_create(&t,NULL,request_thread,&first);wait_blocked();
 struct x710_observer_owner o=owner();struct x710_charge_observation second={};int ret;
 if(mode==0){ /* concurrent request, consumer lock is occupied */
  ret=x710_charge_request_observation(&o,&second);release_provider();pthread_join(t,NULL);
 }else if(mode==1){ /* PM waits for actual supplier drain */
  pthread_create(&pm,NULL,pm_thread,NULL);
  while(!atomic_load(&cancel_started)){struct timespec pause={0,1000000};nanosleep(&pause,NULL);}
  ret=x710_charge_request_observation(&o,&second);release_provider();
  pthread_join(pm,NULL);pthread_join(t,NULL);
 }else{ /* timed-out waiter returns; second request must not start an ADC */
  pthread_join(t,NULL);ret=x710_charge_request_observation(&o,&second);
  release_provider();
 }
 cancel_work_sync(&x710_observer_job);output(first.ret,&first.result,out);out[15]=ret;
 if(mode==1){int before=atomic_load(&events);x710_observer_pm(NULL,PM_POST_SUSPEND,NULL);
  out[16]=atomic_load(&events)-before;out[17]=x710_observer_quiescing;}
}
void invalid(int mode,int64_t *out){
 reset(0,0);struct x710_observer_owner o={};struct x710_charge_observation r;
 if(mode==0)o.instance=11;if(mode==1)o.lease=99;
 if(mode==2){o.instance=11;o.lease=99;}
 if(mode==3)x710_observer_quiescing=true;
 if(mode==4)x710_observer_generation=U64_MAX;
 if(mode==5)queue_fail=true;
 memset(&r,0xff,sizeof(r));int ret=x710_charge_request_observation(&o,&r);
 output(ret,&r,out);
}
int init_failure(int mode){
 if(x710_observer_wq){cancel_work_sync(&x710_observer_job);destroy_workqueue(x710_observer_wq);x710_observer_wq=NULL;}
 x710_observer_quiescing=true;allocation_fail=mode==0;notifier_error=mode==1?-EIO:0;
 int ret=x710_observer_init();int wrong=x710_observer_wq!=NULL||!x710_observer_quiescing;
 allocation_fail=false;notifier_error=0;return wrong?1234:ret;
}
void shutdown(void){
 if(x710_observer_wq){x710_observer_pm(NULL,PM_SUSPEND_PREPARE,NULL);
  destroy_workqueue(x710_observer_wq);x710_observer_wq=NULL;}
}
'''
        (d / 'observer.c').write_text(code)
        so = d / 'observer.so'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-unused-parameter', '-Wno-misleading-indentation',
                        '-shared', '-fPIC', '-pthread', '-I', str(d),
                        str(d / 'observer.c'), '-o', str(so)], check=True,
                       capture_output=True, text=True)
        cls.lib = ctypes.CDLL(str(so))
        cls.addClassCleanup(cls.lib.shutdown)
        ptr = ctypes.POINTER(ctypes.c_int64)
        cls.lib.run.argtypes = [ctypes.c_int, ctypes.c_int, ptr]
        cls.lib.race.argtypes = [ctypes.c_int, ptr]
        cls.lib.invalid.argtypes = [ctypes.c_int, ptr]

    def run_case(self, scenario=0, fail=0):
        out = (ctypes.c_int64 * 18)()
        self.lib.run(scenario, fail, out)
        self.assertEqual(out[3], 0, 'supplier called with publication lock held')
        return list(out)

    def test_fixed_and_owned_native_timestamps_are_preserved(self):
        for mode in (0, 1):
            out = self.run_case(mode)
            self.assertEqual(out[:4], [0, 5, 1, 0])
            self.assertEqual(out[5], out[7])
            self.assertLess(out[5], out[8])
            self.assertLess(out[8], out[9])
            self.assertLess(out[9], out[6])
            self.assertEqual(out[10], 99 if mode else 0)
            self.assertEqual(out[11], 8800 if mode else 9000)

    def test_every_supplier_failure_zeroes_bundle_without_retry(self):
        for event in range(1, 6):
            out = self.run_case(fail=event)
            self.assertEqual(out[0], -errno.EIO)
            self.assertEqual(out[1], event)
            self.assertEqual(out[4:12], [0] * 8)

    def test_source_rebind_reset_budget_and_offer_changes_refuse(self):
        for mode in (2, 3, 4, 5):
            self.assertEqual(self.run_case(mode)[0], -errno.ESTALE)

    def test_pack_rebind_or_state_change_during_adc_refuses(self):
        for mode in (6, 7):
            self.assertEqual(self.run_case(mode)[0], -errno.ESTALE)

    def test_thermal_voltage_health_and_lease_refusals(self):
        for mode in (8, 9, 17, 18, 24):
            out = self.run_case(mode)
            self.assertEqual(out[0], -errno.EPERM)
            self.assertEqual(out[4:12], [0] * 8)

    def test_old_future_adc_old_facts_and_clock_reversal_refuse(self):
        for mode in (11, 12, 13, 20):
            self.assertEqual(self.run_case(mode)[0], -errno.ESTALE)

    def test_nonzero_off_current_die_voltage_and_adc_vbat_refuse(self):
        for mode in (14, 15, 16, 23):
            self.assertEqual(self.run_case(mode)[0], -errno.ERANGE)

    def test_generation_cancel_stops_before_converter_request(self):
        out = self.run_case(19)
        self.assertEqual(out[0], -errno.ECANCELED)
        self.assertEqual(out[2], 0)
        self.assertEqual(out[4:12], [0] * 8)

    def test_fixed_limit_not_expanded(self):
        self.assertEqual(self.run_case(21)[0], -errno.EPERM)
        self.assertEqual(self.run_case(26)[0], 0)
        out = self.run_case(27)
        self.assertEqual(out[0], -errno.EPERM)
        self.assertEqual(out[2], 0)

    def test_owned_pps_step_encoding_refuses_before_adc(self):
        out = self.run_case(22)
        self.assertEqual(out[0], -errno.EPERM)
        self.assertEqual(out[2], 0)

    def test_partial_owner_shutdown_overflow_and_queue_failure(self):
        for mode, expected in ((0, errno.EINVAL), (1, errno.EINVAL),
                               (2, errno.EINVAL), (3, errno.ESHUTDOWN),
                               (4, errno.EOVERFLOW), (5, errno.EBUSY)):
            out = (ctypes.c_int64 * 18)()
            self.lib.invalid(mode, out)
            self.assertEqual(out[0], -expected)
            self.assertEqual(out[1], 0)
            self.assertEqual(list(out[4:12]), [0] * 8)
            self.assertEqual(out[12], 0)

    def test_single_worker_contention_and_timeout_late_publication(self):
        for mode in (0, 2, 3):
            out = (ctypes.c_int64 * 18)()
            self.lib.race(mode, out)
            self.assertEqual(out[15], -errno.EBUSY)
            self.assertEqual(out[3], 0)
            if mode == 0:
                self.assertEqual(out[0], 0)
                self.assertEqual(out[2], 1)
            else:
                self.assertEqual(out[0], -errno.ETIMEDOUT)
                self.assertEqual(out[2], 0)
                self.assertEqual(out[13], 0, 'late worker published cancelled result')

    def test_pm_drains_inflight_adc_and_resume_never_restarts(self):
        out = (ctypes.c_int64 * 18)()
        self.lib.race(1, out)
        self.assertIn(out[0], (-errno.ECANCELED, -errno.ESHUTDOWN))
        self.assertEqual(list(out[4:12]), [0] * 8)
        self.assertEqual(out[1], 3, 'cancelled worker read more providers')
        self.assertEqual(out[12:14], [0, 0])
        self.assertEqual(out[16:18], [0, 0])

    def test_init_failure_cleans_queue_and_remains_quiesced(self):
        self.assertEqual(self.lib.init_failure(0), -errno.ENOMEM)
        self.assertEqual(self.lib.init_failure(1), -errno.EIO)

    def test_actual_kbuild_and_default_inactive_api(self):
        prepare = (ROOT / 'scripts/prepare-kernel.sh').read_text()
        patch = (ROOT / 'kernel/patches/0019-power-supply-hook-x710-native-observer.patch').read_text()
        self.assertIn('x710-charge-observer.c) dest="$tree/drivers/power/supply"', prepare)
        self.assertIn('obj-$(CONFIG_X710_CHARGING_POLICY) += x710-charge-observer.o', patch)
        source = (ROOT / 'kernel/drivers/x710-charge-observer.c').read_text()
        for forbidden in ('sm5714_pd_request_pps(', 'sm5714_pd_restore_fixed(',
                          'sm5714_battery_switching_acquire(', 'regmap_write(',
                          'regmap_update_bits(', 'module_param(', 'schedule_delayed_work('):
            self.assertNotIn(forbidden, source)
        self.assertNotIn('sm5440_passive_observe(', source)
        self.assertIn('sm5440_passive_request_fresh(', source)


if __name__ == '__main__':
    unittest.main()
