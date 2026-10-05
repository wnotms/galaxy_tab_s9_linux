/* Kernel scheduling shim for actual controller fault tests, not a hardware model. */

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
#define msecs_to_jiffies(ms) (100)
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
#define NOTIFY_BAD 2
struct notifier_block {int (*notifier_call)(struct notifier_block *,unsigned long,void *);int priority;};
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
static void flush_work(struct work_struct *job){(void)job;atomic_store(&cancel_started,1);
 pthread_mutex_lock(&wq_lock);while(pending||running)pthread_cond_wait(&wq_cond,&wq_lock);pthread_mutex_unlock(&wq_lock);
}
static void usleep_range(unsigned int low,unsigned int high){(void)high;atomic_fetch_add(&clock_ms,low/1000);}
static void destroy_workqueue(struct workqueue_struct *q){
 pthread_mutex_lock(&wq_lock);quit=true;pthread_cond_broadcast(&wq_cond);pthread_mutex_unlock(&wq_lock);
 pthread_join(q->thread,NULL);free(q);
}
