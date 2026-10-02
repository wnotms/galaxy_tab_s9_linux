"""Execute actual runtime/provider functions with real mutexes and teardown."""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_sm5714_policy import function
ROOT=Path(__file__).resolve().parents[1]

class RuntimeSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory();cls.addClassCleanup(cls.tmp.cleanup)
        cls.source=(ROOT/'kernel/drivers/sm5714_usbpd.c').read_text()
        header=(ROOT/'kernel/drivers/sm5714-stage2.h').read_text()
        code=r'''
#include <stdint.h>
#include <stdbool.h>
#include <string.h>
#include <errno.h>
#include <stddef.h>
#include <pthread.h>
#include <stdatomic.h>
#include <unistd.h>
typedef uint32_t u32;typedef uint64_t u64;typedef atomic_int atomic_t;
#define current get_current() /* Kernel macro must not become a parameter. */
#define U64_MAX UINT64_MAX
#define PD_MAX_PAYLOAD 7
#define SM5714_SOURCE_PDO_MAX 7
#define ARRAY_SIZE(x) (sizeof(x)/sizeof(*(x)))
#define READ_ONCE(x) __atomic_load_n(&(x),__ATOMIC_SEQ_CST)
#define WRITE_ONCE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_SEQ_CST)
#define atomic_read(p) atomic_load(p)
#define atomic_inc(p) atomic_fetch_add(p,1)
#define atomic_dec_and_test(p) (atomic_fetch_sub(p,1)==1)
struct mutex {pthread_mutex_t m;int registry;};
struct wait_queue {pthread_mutex_t m;pthread_cond_t c;};typedef struct wait_queue wait_queue_head_t;
struct device {int unused;};struct regmap {int unused;};struct tcpc_dev {int unused;};
struct tcpm_port {int unused;};struct fwnode_handle {int unused;};struct delayed_work {int unused;};
struct dentry {int unused;};struct power_supply {int unused;};
static _Thread_local int registry_held,transport_held;
static int errors,force_busy;
static void mutex_lock(struct mutex *m){
 pthread_mutex_lock(&m->m);
 if(m->registry){if(transport_held)errors++;registry_held++;}else transport_held++;}
static void mutex_unlock(struct mutex *m){
 if(m->registry)registry_held--;else transport_held--;pthread_mutex_unlock(&m->m);}
static int mutex_trylock(struct mutex *m){
 if(force_busy||pthread_mutex_trylock(&m->m))return 0;transport_held++;return 1;}
#define lockdep_assert_held(m) do {if(!transport_held)errors++;}while(0)
static atomic_int draining,unpublished;
static void wake_up_all(wait_queue_head_t *q){
 pthread_mutex_lock(&q->m);pthread_cond_broadcast(&q->c);pthread_mutex_unlock(&q->m);}
#define wait_event(q,condition) do { \
 if(registry_held||transport_held)errors++;atomic_store(&draining,1); \
 pthread_mutex_lock(&(q).m);while(!(condition))pthread_cond_wait(&(q).c,&(q).m); \
 pthread_mutex_unlock(&(q).m); }while(0)
static u64 clock_ms=1000;static int scenario,calls,fail_at;
static u64 ktime_get_boottime(void){return clock_ms*1000000ULL;}
#define ktime_to_ms(x) ((x)/1000000ULL)
enum power_supply_property {POWER_SUPPLY_PROP_ONLINE,POWER_SUPPLY_PROP_USB_TYPE,
 POWER_SUPPLY_PROP_VOLTAGE_NOW,POWER_SUPPLY_PROP_CURRENT_NOW};
#define POWER_SUPPLY_USB_TYPE_PD 2
union power_supply_propval {int intval;};
'''
        code+=function(header,'struct sm5714_pd_snapshot {')+';\n'
        code+=function(cls.source,'struct sm5714_usbpd {')+';\n'
        code+=r'''
static struct mutex sm5714_port_registry_lock={PTHREAD_MUTEX_INITIALIZER,1};
static struct sm5714_usbpd *sm5714_port_provider,*port_under_test;static u64 sm5714_port_issuer;
static struct power_supply supply;static int values[]={1,2,5000000,1800000};
static pthread_mutex_t control=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t event=PTHREAD_COND_INITIALIZER;static bool entered,released;
'''
        for marker in ['static void sm5714_forget_source(', 'static void sm5714_budget_tick_locked(',
                       'static void sm5714_budget_begin(', 'static void sm5714_budget_end(',
                       'static int sm5714_port_publish(', 'static void sm5714_port_unpublish(',
                       'static int sm5714_snapshot_locked(']:
            code+=function(cls.source,marker)+'\n'
        code+=r'''
static int power_supply_get_property(struct power_supply *p,enum power_supply_property prop,
 union power_supply_propval *v){
 if(registry_held||transport_held||p!=&supply)errors++;calls++;
 if(calls==fail_at)return -EIO;
 if(scenario==17&&calls==1){
  pthread_mutex_lock(&control);entered=true;pthread_cond_broadcast(&event);
  while(!released)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);}
 if(scenario==9&&calls==2){mutex_lock(&port_under_test->lock);sm5714_forget_source(port_under_test);mutex_unlock(&port_under_test->lock);}
 if(scenario==10&&calls==2){sm5714_budget_begin(port_under_test);sm5714_budget_end(port_under_test,0,true,9000,1500,false);}
 if(scenario==11&&calls==5)values[2]=9000000;
 if(scenario==13)clock_ms=900;else clock_ms++;
 v->intval=values[prop];return 0;}
'''
        code+=function(cls.source,'static int sm5714_snapshot_properties(')+'\n'
        code+=function(cls.source,'int sm5714_pd_read_snapshot(')+'\n'
        code+=r'''
static void initialize(struct sm5714_usbpd *s){
 memset(s,0,sizeof(*s));pthread_mutex_init(&s->lock.m,0);
 pthread_mutex_init(&s->snapshot_wait.m,0);pthread_cond_init(&s->snapshot_wait.c,0);
 atomic_init(&s->snapshot_users,0);s->tcp_supply=&supply;s->source_generation=2;
 s->nr_source_pdos=2;s->source_pdos[0]=0x019191f4;s->source_pdos[1]=0x0002d12c;
 s->budget_generation=4;s->budget_mv=5000;s->budget_ma=1800;s->charge_requested=true;}
static void destroy(struct sm5714_usbpd *s){
 pthread_mutex_destroy(&s->lock.m);pthread_mutex_destroy(&s->snapshot_wait.m);
 pthread_cond_destroy(&s->snapshot_wait.c);}
static struct sm5714_pd_snapshot result;static int reader_ret;
static void *reader(void *unused){(void)unused;reader_ret=sm5714_pd_read_snapshot(&result);return 0;}
static void *unpublisher(void *s){sm5714_port_unpublish(s);atomic_store(&unpublished,1);return 0;}
int exercise(int mode,int failure,long long *out){
 struct sm5714_usbpd s,other;initialize(&s);initialize(&other);port_under_test=&s;
 scenario=mode;errors=calls=force_busy=0;clock_ms=1000;fail_at=failure;
 values[0]=1;values[1]=2;values[2]=5000000;values[3]=1800000;
 entered=released=false;atomic_store(&draining,0);atomic_store(&unpublished,0);
 sm5714_port_provider=0;sm5714_port_issuer=0;
 int pub=sm5714_port_publish(&s),ret;
 if(pub)errors++;
 if(mode==1)sm5714_port_provider=0;
 if(mode==2)force_busy=1;
 if(mode==3)s.fault=true;
 if(mode==4)s.removing=true;
 if(mode==5)s.nr_source_pdos=0;
 if(mode==6)s.budget_pending=1;
 if(mode==7)s.observation_exhausted=true;
 if(mode==14)values[1]=3;
 if(mode==15)values[3]=1500000;
 if(mode==18){s.source_generation=UINT64_MAX;mutex_lock(&s.lock);sm5714_forget_source(&s);mutex_unlock(&s.lock);}
 if(mode==19){s.budget_generation=UINT64_MAX;sm5714_budget_begin(&s);sm5714_budget_end(&s,0,true,5000,1800,false);}
 if(mode==20){ret=sm5714_port_publish(&other);out[0]=sm5714_port_issuer;out[1]=s.port_instance;out[2]=errors;goto done;}
 if(mode==21){ret=sm5714_pd_read_snapshot(0);out[0]=calls;out[1]=atomic_read(&s.snapshot_users);out[2]=errors;goto done;}
 if(mode==22){sm5714_port_unpublish(&s);ret=sm5714_port_publish(&other);out[0]=s.port_instance;out[1]=other.port_instance;out[2]=errors;goto done;}
 if(mode==23){sm5714_port_unpublish(&s);sm5714_port_issuer=UINT64_MAX;ret=sm5714_port_publish(&other);out[0]=sm5714_port_provider!=0;out[1]=other.port_instance;out[2]=errors;goto done;}
 if(mode==24){sm5714_port_unpublish(&s);other.tcp_supply=0;ret=sm5714_port_publish(&other);out[0]=sm5714_port_provider!=0;out[1]=other.port_instance;out[2]=errors;goto done;}
 memset(&result,0xff,sizeof(result));
 if(mode==17){
  pthread_t a,b;pthread_create(&a,0,reader,0);
  pthread_mutex_lock(&control);while(!entered)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);
  pthread_create(&b,0,unpublisher,&s);int loops=0;
  while(!atomic_load(&draining)&&loops++<2000)usleep(1000);
  if(!atomic_load(&draining)||atomic_load(&unpublished)||atomic_read(&s.snapshot_users)!=1)errors++;
  pthread_mutex_lock(&control);released=true;pthread_cond_broadcast(&event);pthread_mutex_unlock(&control);
  pthread_join(a,0);pthread_join(b,0);if(!atomic_load(&unpublished))errors++;ret=reader_ret;
 }else ret=sm5714_pd_read_snapshot(&result);
 out[0]=calls;out[1]=atomic_read(&s.snapshot_users);out[2]=errors;
 unsigned char *bytes=(void *)&result;int nonzero=0;for(unsigned int i=0;i<sizeof(result);i++)nonzero+=!!bytes[i];
 out[3]=nonzero;out[4]=result.instance;out[5]=result.source_generation;out[6]=result.budget_generation;
 out[7]=result.voltage_uv;out[8]=result.current_ua;out[9]=result.nr_source_pdos;
 out[10]=result.started_ms;out[11]=result.completed_ms;
 done:sm5714_port_provider=0;destroy(&s);destroy(&other);return ret;}
'''
        c=Path(cls.tmp.name)/'runtime.c';c.write_text(code);lib=c.with_suffix('.so')
        subprocess.run(['cc','-shared','-fPIC','-pthread','-Wall','-Werror','-Wno-misleading-indentation',str(c),'-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.exercise.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_longlong)]
    def case(self,mode=0,failure=0):
        out=(ctypes.c_longlong*12)();ret=self.lib.exercise(mode,failure,out);self.assertEqual(out[2],0)
        if mode<20:self.assertEqual(out[1],0)
        if ret and mode<20:self.assertEqual(out[3],0)
        return ret,list(out)
    def test_live_standard_snapshot(self):
        ret,r=self.case();self.assertEqual(ret,0);self.assertEqual(r[0],8);self.assertEqual(r[4:10],[1,2,4,5000000,1800000,2]);self.assertEqual(r[10:],[1000,1008])
    def test_missing_provider(self):self.assertEqual(self.case(1)[0],-errno.ENODEV)
    def test_no_registry_wait_on_busy_transport(self):self.assertEqual(self.case(2)[0],-errno.EBUSY)
    def test_fault(self):self.assertEqual(self.case(3)[0],-errno.EIO)
    def test_removal(self):self.assertEqual(self.case(4)[0],-errno.ESHUTDOWN)
    def test_missing_source(self):self.assertEqual(self.case(5)[0],-errno.ENODATA)
    def test_pending_budget(self):self.assertEqual(self.case(6)[0],-errno.EAGAIN)
    def test_exhausted_evidence(self):self.assertEqual(self.case(7)[0],-errno.EOVERFLOW)
    def test_all_eight_property_errors_zero_output_and_unpin(self):
        for failure in range(1,9):
            ret,r=self.case(failure=failure);self.assertEqual(ret,-errno.EIO);self.assertEqual(r[0],failure)
    def test_source_withdrawal_during_properties(self):self.assertEqual(self.case(9)[0],-errno.ENODATA)
    def test_callback_budget_change(self):self.assertEqual(self.case(10)[0],-errno.EAGAIN)
    def test_lockless_property_publication_mismatch(self):self.assertEqual(self.case(11)[0],-errno.EAGAIN)
    def test_clock_regression(self):self.assertEqual(self.case(13)[0],-errno.EAGAIN)
    def test_unexpected_pps_not_a_fixed_grant(self):self.assertEqual(self.case(14)[0],-errno.EAGAIN)
    def test_mirror_budget_must_match(self):self.assertEqual(self.case(15)[0],-errno.EAGAIN)
    def test_unpublish_drains_read_before_resources(self):self.assertEqual(self.case(17)[0],-errno.ESHUTDOWN)
    def test_source_generation_cannot_wrap(self):self.assertEqual(self.case(18)[0],-errno.EOVERFLOW)
    def test_budget_generation_cannot_wrap(self):self.assertEqual(self.case(19)[0],-errno.EOVERFLOW)
    def test_duplicate_provider(self):
        ret,r=self.case(20);self.assertEqual(ret,-errno.EBUSY);self.assertEqual(r[:2],[1,1])
    def test_null_output(self):self.assertEqual(self.case(21)[0],-errno.EINVAL)
    def test_rebind_uses_unique_instance(self):
        ret,r=self.case(22);self.assertEqual(ret,0);self.assertEqual(r[:2],[1,2])
    def test_instance_cannot_wrap(self):self.assertEqual(self.case(23)[0],-errno.EOVERFLOW)
    def test_provider_requires_supply_reference(self):self.assertEqual(self.case(24)[0],-errno.ENODEV)
    def test_actual_teardown_put_after_drain_before_tcpm(self):
        for marker in ['static void sm5714_usbpd_remove(', 'static void sm5714_usbpd_shutdown(']:
            body=function(self.source,marker);self.assertLess(body.index('sm5714_port_unpublish'),body.index('power_supply_put'));self.assertLess(body.index('power_supply_put'),body.index('tcpm_unregister_port'))
    def test_request_guard_still_fixed_only(self):
        self.assertIn('rdo, false)',function(self.source,'static bool sm5714_request_allowed('))
        body=function(self.source,'static void sm5714_snapshot_debug_init(')
        self.assertIn('0400',body);self.assertNotIn('set_property',self.source)
