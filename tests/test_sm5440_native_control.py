"""Run the real bound-driver ownership/API/PM and actual hardware helpers."""
import ctypes
import errno
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

import test_sm5440_actuator as fixture
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class NativeControlTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        p = Path(cls.tmp.name)
        fixture.ActuatorTests.setUpClass()
        try:
            shutil.copytree(Path(fixture.ActuatorTests.tmp.name) / 'linux', p / 'linux')
        finally:
            fixture.ActuatorTests.tearDownClass()
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        prefix = r'''
#include <pthread.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>
#include <unistd.h>
#include <linux/errno.h>
#include <linux/power_supply.h>
#include "sm5440-native.h"
#include "sm5440-hw.h"
#define CONFIG_X710_NATIVE_CONTROL 1
#define READ_ONCE(x) __atomic_load_n(&(x),__ATOMIC_SEQ_CST)
#define WRITE_ONCE(x,v) __atomic_store_n(&(x),(v),__ATOMIC_SEQ_CST)
typedef int atomic_t;
#define atomic_inc(p) __atomic_fetch_add(p,1,__ATOMIC_SEQ_CST)
#define atomic_set(p,v) __atomic_store_n(p,v,__ATOMIC_SEQ_CST)
#define atomic_read(p) __atomic_load_n(p,__ATOMIC_SEQ_CST)
#define atomic_dec_and_test(p) (__atomic_sub_fetch(p,1,__ATOMIC_SEQ_CST)==0)
static int atomic_cmpxchg(atomic_t *p,int old,int next) {
 __atomic_compare_exchange_n(p,&old,next,0,__ATOMIC_SEQ_CST,__ATOMIC_SEQ_CST);return old;
}
struct mutex {pthread_mutex_t m;bool registry;};
static _Thread_local int registry_held,io_held;
static int violations,scenario,queued,drained;
static void mutex_lock(struct mutex *m){pthread_mutex_lock(&m->m);
 if(m->registry){if(io_held)violations++;registry_held++;}else io_held++;}
static void mutex_unlock(struct mutex *m){
 if(m->registry)registry_held--;else io_held--;pthread_mutex_unlock(&m->m);}
static bool mutex_trylock(struct mutex *m){if(pthread_mutex_trylock(&m->m))return false;
 if(m->registry)registry_held++;else io_held++;return true;}
#define lockdep_assert_held(p) do {if(!io_held)violations++;} while(0)
typedef int wait_queue_head_t;
static void wake_up_all(int *p){(void)p;}
#define wait_event(q,condition) do {if(io_held||registry_held)violations++; while(!(condition))usleep(500);} while(0)
#define dev_err(...) ((void)0)
#define EXPORT_SYMBOL_GPL(x)
struct device {struct sm5440_direct *sm;};
struct delayed_work {int unused;};struct power_supply {int unused;};struct dentry {int unused;};
struct regmap {u8 reg[256],original[256];int calls,fail,persistent,uncertain,on,off;
 u64 enabled_ms;bool ready_sent;};
uint64_t fake_clock;
#define ktime_get_boottime() (fake_clock)
#define ktime_to_ms(n) (n)
static pthread_mutex_t bus_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t bus_cond=PTHREAD_COND_INITIALIZER;
static bool bus_block,bus_entered;static int unpublish_done;
static int bad(struct regmap *m){if(!io_held||registry_held)violations++;
 pthread_mutex_lock(&bus_lock);
 if(bus_block){bus_entered=true;pthread_cond_broadcast(&bus_cond);
  while(bus_block)pthread_cond_wait(&bus_cond,&bus_lock);}
 pthread_mutex_unlock(&bus_lock);
 m->calls++;return m->fail&&(m->calls==m->fail||(m->persistent&&m->calls>=m->fail));}
int regmap_read(struct regmap *m,unsigned int r,unsigned int *v){
 if(bad(m))return -EIO;*v=m->reg[r];if(r<=3)m->reg[r]=0;return 0;}
int regmap_bulk_read(struct regmap *m,unsigned int r,void *v,unsigned int n){
 if(bad(m))return -EIO;
 if(r==0&&m->enabled_ms&&!m->ready_sent&&fake_clock>=m->enabled_ms+30&&scenario!=12){
  m->reg[3]|=1;m->ready_sent=true;
 }
 memcpy(v,m->reg+r,n);if(r==0)memset(m->reg,0,n);return 0;}
static void written(struct regmap *m,unsigned int r,unsigned int value){
 if(r==0x10){if(value&12)m->on++;else m->off++;}
 if(r==0x1c){if(value&1){m->enabled_ms=fake_clock;m->ready_sent=false;}else m->enabled_ms=0;}
 m->reg[r]=value;
}
int regmap_write(struct regmap *m,unsigned int r,unsigned int v){
 int b=bad(m);if(!b||m->uncertain)written(m,r,v);return b?-EIO:0;}
int regmap_update_bits(struct regmap *m,unsigned int r,unsigned int mask,unsigned int v){
 int b=bad(m);unsigned int next=(m->reg[r]&~mask)|(v&mask);
 if((!b||m->uncertain)&&next!=m->reg[r])written(m,r,next);return b?-EIO:0;}
'''
        for marker in ('struct sm5440_sample {', 'struct sm5440_native_context {',
                       'struct sm5440_direct {'):
            prefix += function(src, marker) + ';\n'
        prefix += r'''
static struct mutex sm5440_companion_lock={PTHREAD_MUTEX_INITIALIZER,true};
static struct sm5440_direct *sm5440_companion;
static struct sm5440_direct *dev_get_drvdata(struct device *d){return d->sm;}
static int sm5440_quiesce(struct sm5440_direct *sm);
static int sm5440_native_quiesce(struct sm5440_direct *sm);
static void cancel_delayed_work_sync(struct delayed_work *w){
 (void)w;drained++;if(io_held||registry_held)violations++;
 if(scenario==8){scenario=0;sm5440_native_quiesce(sm5440_companion);}
 if(scenario==9)sm5440_companion->fault=true;
 if(scenario==20)sm5440_companion->sample.valid=true;
}
static int schedule_delayed_work(struct delayed_work *w,int delay){
 (void)w;(void)delay;queued++;return 1;
}
'''
        prefix += r'''
static struct sm5714_pd_snapshot supplied_source;
static int source_failure,lease_failure,source_calls;
int sm5714_pd_read_owned_snapshot(u64 instance,u64 gen,u64 lease,struct sm5714_pd_snapshot *s){
 if(io_held||registry_held)violations++;source_calls++;
 if(source_failure)return source_failure;
 if(instance!=11||gen!=12||lease!=99)return -ESTALE;
 *s=supplied_source;
 if(scenario==25)sm5440_companion->native.generation++;
 return 0;
}
int sm5714_battery_switching_check(u64 lease){
 if(io_held||registry_held)violations++;return lease_failure?lease_failure:lease==99?0:-ESTALE;
}
'''
        for marker in ('static void sm5440_unpublish(', 'static int sm5440_sample_ready_locked(', 'static int sm5440_off(',
                       'static void sm5440_native_result_locked(',
                       'static int sm5440_native_cleanup_locked(',
                       'static bool sm5440_native_bound(',
                       'static int sm5440_native_bind(',
                       'static int sm5440_native_operation_locked(',
                       'int sm5440_native_control(', 'static int sm5440_quiesce(',
                       'static int sm5440_native_quiesce(', 'static int sm5440_resume('):
            prefix += function(src, marker) + '\n'
        prefix += r'''
static void inject(struct regmap *m,int phase,int selected,int fail,int persistent,int uncertain){
 m->calls=0;m->fail=phase==selected?fail:0;m->persistent=persistent;m->uncertain=uncertain;}
static void raw13(u8 *p,unsigned int raw){p[0]=raw>>5;p[1]=(raw&31)<<3;}
void exercise(int sc,int phase,int fail,int persistent,int uncertain,int *o){
 struct regmap m={0};struct sm5440_direct sm={0};struct sm5440_native_result r={0};
 struct sm5440_native_owner owner={0};struct sm5440_native_input in={.ma=1500};
 struct device dev={.sm=&sm};int ret=0;
 scenario=sc;fake_clock=1000;violations=queued=drained=0;bus_block=false;
 pthread_mutex_init(&sm.io_lock.m,NULL);sm5440_companion=&sm;sm.regmap=&m;
 sm.native.instance=7;sm.initial_sample_done=sm.sample.valid=true;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x42;
 m.reg[0x0d]=0xf2;m.reg[0x0e]=0xb8;m.reg[0x0f]=0xff;m.reg[0x11]=0x89;
 m.reg[0x13]=0xe7;m.reg[0x15]=0x3f;m.reg[0x19]=0xfe;m.reg[0x1a]=0x0c;
 m.reg[0x16]=0x41;m.reg[0x14]=0x37;m.reg[0x12]=12;
 m.reg[0x1c]=0x82;m.reg[0x1d]=0x55;
 raw13(m.reg+0x1e,4904);raw13(m.reg+0x22,0);m.reg[0x26]=15;raw13(m.reg+0x27,3504);
 memcpy(m.original,m.reg,256);
 if(sc==1)sm.native.owned=true;
 if(sc==2)sm.request_busy=1;
 if(sc==3)sm.stopped=true;
 if(sc==4)sm.fault=true;
 if(sc==5)sm.sample.valid=false;
 if(sc==6)sm5440_companion=NULL;
 if(sc==7)sm.native.generation=~0ULL;
 inject(&m,1,phase,fail,persistent,uncertain);
 o[0]=sm5440_native_control(SM5440_NATIVE_CLAIM,NULL,NULL,&r);o[1]=m.calls;
 o[2]=r.owned;o[3]=r.draining;owner=r.owner;
 o[32]=sm.native.generation;o[34]=sm.sample.valid;
 if(!o[0]){
  if(sc==10){struct sm5440_native_owner stale=owner;stale.instance++;
   m.calls=0;o[29]=sm5440_native_control(SM5440_NATIVE_PREPARE,&stale,&in,&r);o[30]=m.calls;}
  if(sc==11){struct sm5440_native_owner stale=owner;stale.generation++;
   m.calls=0;o[29]=sm5440_native_control(SM5440_NATIVE_RELEASE,&stale,NULL,&r);o[30]=m.calls;}
  if(sc==14){m.calls=0;o[29]=sm5440_native_control(SM5440_NATIVE_START,&owner,&in,&r);o[30]=m.calls;}
  if(sc==15){m.calls=0;o[29]=sm5440_native_control(SM5440_NATIVE_RESUME,&owner,&in,&r);o[30]=m.calls;}
  if(sc==16){m.calls=0;o[29]=sm5440_native_control(SM5440_NATIVE_MONITOR_BEGIN,&owner,&in,&r);o[30]=m.calls;}
  if(sc==17){m.calls=0;o[29]=sm5440_native_control(SM5440_NATIVE_ADC_ADVANCE,&owner,NULL,&r);o[30]=m.calls;}
  if(sc==18){m.calls=0;o[29]=sm5440_native_control((enum sm5440_native_operation)99,&owner,NULL,&r);o[30]=m.calls;}
  if(sc==19){mutex_lock(&sm.io_lock);o[29]=sm5440_sample_ready_locked(&sm);mutex_unlock(&sm.io_lock);}
  inject(&m,2,phase,fail,persistent,uncertain);
  o[4]=sm5440_native_control(SM5440_NATIVE_PREPARE,&owner,&in,&r);o[5]=m.calls;
  if(!o[4]){
   inject(&m,3,phase,fail,persistent,uncertain);
   o[6]=sm5440_native_control(SM5440_NATIVE_ADC_BEGIN,&owner,NULL,&r);
   if(sc==13){o[26]=sm5440_native_quiesce(&sm);o[27]=sm5440_resume(&dev);}
   else if(!o[6]||o[6]==-EINPROGRESS){
    for(int j=0;j<25;j++){fake_clock+=5;
     ret=sm5440_native_control(SM5440_NATIVE_ADC_ADVANCE,&owner,NULL,&r);
     if(ret!=-EINPROGRESS)break;
    }
    o[7]=ret;o[8]=r.physical.valid;o[9]=r.physical.observed_ms;o[31]=m.calls;
    o[35]=r.die_valid;o[36]=r.die_decic;o[37]=r.vbus_uv;
   }
  }
 }
 inject(&m,4,phase,fail,persistent,uncertain);
 o[10]=sm5440_native_control(SM5440_NATIVE_RELEASE,&owner,NULL,&r);o[11]=m.calls;
 o[12]=r.hardware_quiesced;o[13]=r.owned;o[14]=sm.fault;o[15]=m.on;
 o[16]=m.reg[0x1c];o[17]=m.reg[0x0c];
 o[18]=m.reg[0x16]==m.original[0x16]&&m.reg[0x14]==m.original[0x14]&&m.reg[0x12]==m.original[0x12];
 o[19]=r.operation_error;o[20]=r.cleanup_error;o[28]=queued;
 m.calls=0;o[21]=sm5440_native_control(SM5440_NATIVE_RELEASE,&r.owner,NULL,&r);o[22]=m.calls;
 o[23]=violations;o[24]=sm.request_users;o[25]=drained;o[33]=queued;
 pthread_mutex_destroy(&sm.io_lock.m);sm5440_companion=NULL;
}
static struct sm5440_native_owner lifetime_owner;
static int lifetime_result;
static void *lifetime_call(void *unused){
 struct sm5440_native_result out={0};struct sm5440_native_input input={.ma=1500};
 lifetime_result=sm5440_native_control(SM5440_NATIVE_PREPARE,&lifetime_owner,&input,&out);return NULL;
}
static void *lifetime_remove(void *ptr){
 sm5440_unpublish(ptr);__atomic_store_n(&unpublish_done,1,__ATOMIC_SEQ_CST);return NULL;
}
void exercise_lifetime(int *o){
 struct sm5440_direct sm={0};struct regmap m={0};struct sm5440_native_result out={0};
 pthread_t call,remove;
 fake_clock=1000;scenario=0;violations=queued=drained=0;
 pthread_mutex_init(&sm.io_lock.m,NULL);sm5440_companion=&sm;sm.regmap=&m;
 sm.native.instance=7;sm.initial_sample_done=sm.sample.valid=true;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x42;
 m.reg[0x0d]=0xf2;m.reg[0x0e]=0xb8;m.reg[0x0f]=0xff;m.reg[0x11]=0x89;
 m.reg[0x13]=0xe7;m.reg[0x15]=0x3f;m.reg[0x19]=0xfe;m.reg[0x1a]=0x0c;
 m.reg[0x16]=0x41;m.reg[0x14]=0x37;m.reg[0x12]=12;m.reg[0x1c]=0x82;
 o[0]=sm5440_native_control(SM5440_NATIVE_CLAIM,NULL,NULL,&out);lifetime_owner=out.owner;
 bus_block=true;bus_entered=false;unpublish_done=0;
 pthread_create(&call,NULL,lifetime_call,NULL);
 pthread_mutex_lock(&bus_lock);while(!bus_entered)pthread_cond_wait(&bus_cond,&bus_lock);
 pthread_mutex_unlock(&bus_lock);pthread_create(&remove,NULL,lifetime_remove,&sm);
 for(int n=0;n<100&&!READ_ONCE(sm.dying);n++)usleep(500);
 o[1]=READ_ONCE(sm.dying);o[2]=READ_ONCE(unpublish_done);
 pthread_mutex_lock(&bus_lock);bus_block=false;pthread_cond_broadcast(&bus_cond);
 pthread_mutex_unlock(&bus_lock);pthread_join(call,NULL);pthread_join(remove,NULL);
 o[3]=lifetime_result;o[4]=sm5440_native_quiesce(&sm);
 o[5]=sm5440_native_control(SM5440_NATIVE_RELEASE,&lifetime_owner,NULL,&out);
 o[6]=sm.request_users;o[7]=violations;o[8]=m.on;o[9]=m.reg[0x0c];
 pthread_mutex_destroy(&sm.io_lock.m);
}
'''
        prefix += r'''
void binding(int mode,int *o){
 struct regmap m={0};struct sm5440_direct sm={0};struct sm5440_native_result result={0};
 struct sm5440_native_owner owner={0};
 struct sm5714_pd_snapshot proposed={.instance=11,.source_generation=12,.budget_generation=13,
  .started_ms=1000,.completed_ms=1000,.nr_source_pdos=1,.budget_mv=9000,.budget_ma=1500,
  .voltage_uv=9000000,.current_ua=1500000,.online=2,.usb_type=POWER_SUPPLY_USB_TYPE_PD_PPS,
  .charge_requested=true,.pps_contract=true,.source_pdos={0xc0000000U|(110<<17)|(33<<8)|60}};
 struct sm5440_native_input in={.source=&proposed,.consumer_epoch=901,.switching_lease=99};
 fake_clock=1000;scenario=mode==4?25:0;violations=queued=drained=0;source_calls=0;
 source_failure=mode==1?-EIO:0;lease_failure=mode==2?-ESTALE:0;supplied_source=proposed;
 if(mode==3)supplied_source.budget_generation++;
 if(mode==6)proposed.source_pdos[0]++;
 if(mode==5)in.consumer_epoch=0;
 pthread_mutex_init(&sm.io_lock.m,NULL);sm5440_companion=&sm;sm.regmap=&m;
 sm.native.instance=7;sm.initial_sample_done=sm.sample.valid=true;
 o[0]=sm5440_native_control(SM5440_NATIVE_CLAIM,NULL,NULL,&result);owner=result.owner;
 m.calls=0;o[1]=sm5440_native_control(SM5440_NATIVE_BIND_SOURCE,&owner,&in,&result);
 o[2]=sm.native.consumer_epoch;o[3]=sm.native.actuator.lease;
 o[4]=sm.native.actuator.enabled;o[5]=source_calls;o[6]=m.calls;o[7]=violations;
 o[8]=sm5440_native_control(SM5440_NATIVE_START,&owner,&in,&result);o[9]=m.on;
 o[10]=sm5440_native_control(SM5440_NATIVE_RELEASE,&owner,NULL,&result);
 sm5440_companion=NULL;pthread_mutex_destroy(&sm.io_lock.m);
}
'''
        prefix += r'''
/* Private grants below exist only in this mocked-bus translation unit. */
static struct x710_charge_facts active_facts(u64 epoch){
 return (struct x710_charge_facts){.epoch=epoch,.observed_ms=fake_clock,.capacity=30,
 .pack_decic=300,.die_decic=300,.vbat_mv=3800,.fixed_mv=9000,
 .apdo_min_mv=8200,.apdo_max_mv=10500,.apdo_ma=1800,
 .attached=true,.battery_present=true,.healthy=true,.pack_valid=true,.voltage_valid=true,
 .soc_valid=true,.die_valid=true,.adc_valid=true,.fixed_healthy=true,.apdo=true,
 .thermal_normal=true,.software_ocp_verified=true};
}
static int native_sample(enum sm5440_native_operation op,struct sm5440_native_owner *owner,
                        struct sm5440_native_input *in,struct sm5440_native_result *out){
 int ret=sm5440_native_control(op,owner,in,out);
 for(int i=0;ret==-EINPROGRESS&&i<25;i++){
  fake_clock+=5;
  ret=sm5440_native_control(op==SM5440_NATIVE_ADC_BEGIN?SM5440_NATIVE_ADC_ADVANCE:
    SM5440_NATIVE_MONITOR_ADVANCE,owner,in,out);
 }
 return ret;
}
void native_active(int mode,int *o){
 struct regmap m={0};struct sm5440_direct sm={0};struct sm5440_native_result result={0};
 struct sm5440_native_owner owner={0};struct x710_charge_facts facts={0};
 struct x710_physical_sample physical={0};
 struct sm5440_native_input in={.source=&supplied_source,.consumer_epoch=901,
   .switching_lease=99,.ma=1500,.mv=9000,.facts=&facts,.physical=&physical};
 fake_clock=1000;scenario=0;violations=queued=drained=0;source_calls=0;
 source_failure=lease_failure=0;
 supplied_source=(struct sm5714_pd_snapshot){.instance=11,.source_generation=12,.budget_generation=13,
  .started_ms=1000,.completed_ms=1000,.nr_source_pdos=1,.budget_mv=9000,.budget_ma=1500,
  .voltage_uv=9000000,.current_ua=1500000,.online=2,.usb_type=POWER_SUPPLY_USB_TYPE_PD_PPS,
  .charge_requested=true,.pps_contract=true,.source_pdos={0xc0000000U|(110<<17)|(33<<8)|60}};
 pthread_mutex_init(&sm.io_lock.m,NULL);sm5440_companion=&sm;sm.regmap=&m;
 sm.native.instance=7;sm.initial_sample_done=sm.sample.valid=true;
 m.reg[0x2b]=0x21;m.reg[0x10]=1;m.reg[0x0a]=32;m.reg[0x0c]=0x42;
 m.reg[0x0d]=0xf2;m.reg[0x0e]=0xb8;m.reg[0x0f]=0xff;m.reg[0x11]=0x89;
 m.reg[0x13]=0xe7;m.reg[0x15]=0x3f;m.reg[0x19]=0xfe;m.reg[0x1a]=0x0c;
 m.reg[0x16]=0x41;m.reg[0x14]=0x37;m.reg[0x12]=12;m.reg[0x1c]=0x82;m.reg[0x1d]=0x55;
 raw13(m.reg+0x1e,4904);raw13(m.reg+0x22,0);m.reg[0x26]=15;raw13(m.reg+0x27,3504);
 memcpy(m.original,m.reg,256);
 o[0]=sm5440_native_control(SM5440_NATIVE_CLAIM,NULL,NULL,&result);owner=result.owner;
 o[1]=sm5440_native_control(SM5440_NATIVE_PREPARE,&owner,&in,&result);
 o[2]=native_sample(SM5440_NATIVE_ADC_BEGIN,&owner,&in,&result);physical=result.physical;
 facts=active_facts(901);
 o[3]=sm5440_native_control(SM5440_NATIVE_BIND_SOURCE,&owner,&in,&result);
 sm.native.actuator.enabled=true;
 if(mode==1)facts.epoch++;
 if(mode==2)source_failure=-EIO;
 if(mode==3)facts.pack_decic=450;
 o[4]=sm5440_native_control(SM5440_NATIVE_START,&owner,&in,&result);
 o[5]=m.on;o[6]=sm.native.actuator.epoch;o[7]=sm.native.consumer_epoch;
 if(!o[4]){
  raw13(m.reg+0x22,mode==4?2401:1920);facts=active_facts(901);
  o[8]=native_sample(SM5440_NATIVE_MONITOR_BEGIN,&owner,&in,&result);
  o[9]=result.physical.valid;o[10]=result.die_decic;o[11]=result.vbus_uv;
  o[12]=result.physical.ibus_ua;
  if(!o[8]){
   o[13]=sm5440_native_control(SM5440_NATIVE_PAUSE,&owner,NULL,&result);
   o[14]=result.owned;o[15]=sm.native.actuator.controls.pending;
   o[16]=sm.native.actuator.watchdog.owned;o[17]=sm.native.actuator.paused;
   fake_clock+=5;supplied_source.budget_generation++;
   supplied_source.started_ms=supplied_source.completed_ms=fake_clock;
   raw13(m.reg+0x22,0);
   if(mode==6){o[18]=sm5440_native_control(SM5440_NATIVE_ADC_BEGIN,&owner,&in,&result);
    goto final_release;}
   o[18]=native_sample(SM5440_NATIVE_ADC_BEGIN,&owner,&in,&result);physical=result.physical;
   facts=active_facts(901);
   if(mode==5)supplied_source.source_generation++;
   o[19]=sm5440_native_control(SM5440_NATIVE_RESUME,&owner,&in,&result);
   if(!o[19]){raw13(m.reg+0x22,1920);facts=active_facts(901);
    o[20]=native_sample(SM5440_NATIVE_MONITOR_BEGIN,&owner,&in,&result);o[21]=result.physical.valid;}
  }
 }
final_release:
 source_failure=0;
 o[22]=sm5440_native_control(SM5440_NATIVE_RELEASE,&owner,NULL,&result);
 o[23]=result.hardware_quiesced;o[24]=result.owned;o[25]=m.on;o[26]=violations;
 o[27]=(m.reg[0x10]&12);o[28]=m.reg[0x11];o[29]=m.reg[0x0c];
 o[30]=m.reg[0x16]==m.original[0x16]&&m.reg[0x14]==m.original[0x14]&&m.reg[0x12]==m.original[0x12];
 o[31]=m.reg[0x1c]==m.original[0x1c]&&m.reg[0x1d]==m.original[0x1d];
 sm5440_companion=NULL;pthread_mutex_destroy(&sm.io_lock.m);
}
'''
        (p / 'mock.c').write_text(prefix)
        names = ['sm5440-control.c', 'sm5440-watchdog.c', 'sm5440-actuator.c',
                 'sm5440-conversion.c', 'sm5440-supervisor.c', 'x710-charging-policy.c']
        subprocess.run(['cc', '-shared', '-fPIC', '-pthread', '-D__KERNEL__',
                        '-I' + str(p), '-I' + str(ROOT / 'kernel/drivers'),
                        *[str(ROOT / 'kernel/drivers' / n) for n in names],
                        str(p / 'mock.c'), '-o', str(p / 'native.so')], check=True,
                       capture_output=True, text=True)
        cls.lib = ctypes.CDLL(str(p / 'native.so'))
        cls.lib.exercise.argtypes = [ctypes.c_int] * 5 + [ctypes.POINTER(ctypes.c_int)]

    def case(self, scenario=0, phase=0, fail=0, persistent=0, uncertain=0):
        out = (ctypes.c_int * 40)()
        self.lib.exercise(scenario, phase, fail, persistent, uncertain, out)
        self.assertEqual(out[23], 0, 'I2C under registry, unlocked I/O or locked drain')
        self.assertEqual(out[24], 0, 'Provider lifetime pin leaked')
        self.assertEqual(out[15], 0, 'Native activation remains disabled')
        return list(out)

    def test_unpublish_drains_actual_inflight_control_before_teardown(self):
        out = (ctypes.c_int * 12)()
        self.lib.exercise_lifetime(out)
        self.assertEqual(list(out[:3]), [0, 1, 0])
        self.assertEqual(list(out[3:9]), [0, 0, -errno.ENODEV, 0, 0, 0])
        self.assertEqual(out[9], 0x42)

    def test_drained_old_sample_is_invalidated_again_before_return(self):
        o = self.case(20)
        self.assertEqual(o[0], 0); self.assertFalse(o[34])

    def test_real_claim_prepare_converter_release_restore(self):
        o = self.case()
        self.assertEqual(o[0], 0); self.assertEqual(o[2:4], [1, 0])
        self.assertEqual(o[4], 0); self.assertEqual(o[6], -errno.EINPROGRESS)
        self.assertEqual(o[7], 0); self.assertEqual(o[8], 1)
        self.assertGreaterEqual(o[9], 1020)
        self.assertEqual(o[10], 0); self.assertEqual(o[12:15], [1, 0, 0])
        self.assertEqual(o[16:19], [0x82, 0x42, 1])

    def test_completed_native_adc_exports_actual_die_and_unrounded_vbus(self):
        o = self.case()
        self.assertEqual(o[35:38], [1, 300, 9000000])
        o = self.case(12)
        self.assertEqual(o[35:38], [0, 0, 0])

    def test_refused_claim_cannot_touch_registers(self):
        for scenario in range(1, 8):
            with self.subTest(scenario=scenario):
                o = self.case(scenario)
                self.assertLess(o[0], 0); self.assertEqual(o[1], 0)

    def test_old_instance_and_generation_cannot_control_other_owner(self):
        for scenario in (10, 11):
            o = self.case(scenario)
            self.assertEqual(o[29], -errno.ESTALE); self.assertEqual(o[30], 0)
            self.assertEqual(o[10], 0)

    def test_start_resume_monitor_have_no_native_activation_grant(self):
        for scenario in (14, 15, 16):
            o = self.case(scenario)
            self.assertEqual(o[29], -errno.EPERM); self.assertEqual(o[30], 0)

    def test_unstarted_converter_unknown_operation_and_passive_reader_refused(self):
        for scenario, expected in ((17, -errno.EALREADY), (18, -errno.EINVAL),
                                   (19, -errno.EBUSY)):
            self.assertEqual(self.case(scenario)[29], expected)

    def test_pm_during_claim_drain_invalidates_and_cleans_before_publication(self):
        o = self.case(8)
        self.assertEqual(o[0], -errno.ESHUTDOWN)
        self.assertEqual(o[10], 0); self.assertTrue(o[12]); self.assertFalse(o[13])
        self.assertEqual(o[16] & 1, 0)

    def test_old_poller_fault_wins_over_claim(self):
        o = self.case(9)
        self.assertEqual(o[0], -errno.EIO); self.assertTrue(o[14])
        self.assertEqual(o[15], 0); self.assertEqual(o[28], 0)

    def test_pm_cancels_real_conversion_restores_and_resume_never_energizes(self):
        o = self.case(13)
        self.assertEqual(o[26:28], [0, 0])
        self.assertEqual(o[10], 0); self.assertEqual(o[12:14], [1, 0])
        self.assertEqual(o[16:19], [0x82, 0x42, 1])

    def test_timeout_preserves_first_error_with_terminal_cleanup(self):
        o = self.case(12)
        self.assertEqual(o[7], -errno.ETIMEDOUT)
        self.assertFalse(o[8]); self.assertEqual(o[19], -errno.ETIMEDOUT)
        self.assertEqual(o[10], 0); self.assertTrue(o[12])

    def test_release_is_idempotent_and_output_owner_can_be_input(self):
        o = self.case()
        self.assertEqual(o[21:23], [0, 0]); self.assertEqual(o[28], o[33])

    def test_each_claim_prepare_conversion_io_failure_is_reported_no_on(self):
        counts = self.case()
        for phase, total in ((1, counts[1]), (2, counts[5]), (3, counts[31])):
            for fail in range(1, total + 1):
                for uncertain in (0, 1):
                    with self.subTest(phase=phase, fail=fail, uncertain=uncertain):
                        o = self.case(phase=phase, fail=fail, uncertain=uncertain)
                        self.assertEqual(o[19], -errno.EIO)
                        self.assertFalse(o[8]); self.assertEqual(o[15], 0)

    def test_each_release_bus_failure_never_retries_terminal_cleanup(self):
        for fail in range(1, self.case()[11] + 1):
            o = self.case(phase=4, fail=fail, persistent=1, uncertain=1)
            self.assertEqual(o[10], -errno.EIO)
            self.assertFalse(o[12]); self.assertTrue(o[13])
            self.assertEqual(o[20], -errno.EIO); self.assertEqual(o[21:23], [-errno.EIO, 0])
            self.assertEqual(o[28], 0)

    def test_actual_source_binding_checks_suppliers_outside_io_and_never_grants_on(self):
        for mode, expected in ((0, 0), (1, -errno.EIO), (2, -errno.ESTALE),
                               (3, -errno.ESTALE), (4, -errno.ECANCELED),
                               (5, -errno.EINVAL), (6, -errno.ESTALE)):
            out = (ctypes.c_int * 12)()
            self.lib.binding(mode, out)
            self.assertEqual(out[0], 0)
            self.assertEqual(out[1], expected)
            self.assertEqual(list(out[2:4]), [901, 99] if not expected else [0, 0])
            self.assertEqual(out[4], 0)
            self.assertEqual(list(out[6:8]), [0, 0])
            self.assertNotEqual(out[8], 0)
            self.assertEqual(out[9], 0)
            self.assertEqual(out[10], 0)

    def native_active_case(self, mode=0):
        out = (ctypes.c_int * 32)()
        self.lib.native_active(mode, out)
        self.assertEqual(list(out[:4]), [0, 0, 0, 0])
        self.assertEqual(out[26], 0, 'supplier called under I/O or registry lock')
        self.assertEqual(out[27], 0, 'terminal cleanup left mocked pump running')
        return list(out)

    def test_mock_native_grant_maps_consumer_epoch_and_preserves_pause_settings(self):
        o = self.native_active_case()
        self.assertEqual(o[4], 0)
        self.assertEqual(o[6:8], [1, 901])
        self.assertEqual(o[8:13], [0, 1, 300, 9000000, 1200000])
        self.assertEqual(o[13:18], [0, 1, 1, 1, 1])
        self.assertEqual(o[18:26], [0, 0, 0, 1, 0, 1, 0, 2])
        self.assertEqual(o[28:31], [0x89, 0x42, 1])

    def test_native_mock_grant_rejects_epoch_source_failure_and_unsafe_temperature(self):
        for mode, expected in ((1, -errno.ESTALE), (2, -errno.EIO), (3, -errno.EPERM)):
            o = self.native_active_case(mode)
            self.assertEqual(o[4], expected)
            self.assertEqual(o[5], 0)
            self.assertEqual(o[22:25], [0, 1, 0])

    def test_actual_native_supervisor_overcurrent_and_new_source_stop_without_resume(self):
        o = self.native_active_case(4)
        self.assertEqual(o[8], -errno.ERANGE)
        self.assertEqual(o[25], 1)
        self.assertEqual(o[22:25], [0, 1, 0])
        o = self.native_active_case(5)
        self.assertEqual(o[19], -errno.ESTALE)
        self.assertEqual(o[25], 1)
        self.assertEqual(o[22:25], [0, 1, 0])

    def test_terminal_cleanup_cancels_pending_off_adc_after_running_monitor(self):
        o = self.native_active_case(6)
        self.assertEqual(o[8], 0)
        self.assertEqual(o[13:18], [0, 1, 1, 1, 1])
        self.assertEqual(o[18], -errno.EINPROGRESS)
        self.assertEqual(o[22:25], [0, 1, 0])
        self.assertEqual(o[28:32], [0x89, 0x42, 1, 1])

    def test_native_profile_gate_cannot_be_smuggled_into_old_profile(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location('native_gate', ROOT / 'scripts/verify-x710-charging-profile.py')
        gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)
        baseline = gate.BASE.read_text() + '\nCONFIG_CHARGER_SM5440_DIRECT=y\nCONFIG_X710_CHARGING_POLICY=y\n'
        candidate = baseline + '\nCONFIG_X710_NATIVE_CONTROL=y\n'
        self.assertTrue(gate.verify(candidate, profile='sm5440-native-control')['valid'])
        for profile in ('sm5440-policy-offline', 'sm5440-passive'):
            self.assertFalse(gate.verify(candidate, baseline=candidate, profile=profile)['valid'])
        self.assertFalse(gate.verify(baseline, profile='sm5440-native-control')['valid'])

    def test_policy_only_kbuild_and_real_provider_boundary(self):
        patch = (ROOT / 'kernel/patches/0020-power-supply-hook-sm5440-native-control.patch').read_text()
        for name in ('watchdog', 'actuator', 'conversion', 'supervisor'):
            self.assertIn('sm5440-' + name + '.o', patch)
        source = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        body = function(source, 'int sm5440_native_control(')
        self.assertIn('cancel_delayed_work_sync(&sm->work)', body)
        self.assertIn('atomic_inc(&sm->request_users)', body)
        self.assertNotIn('.enabled = true', body)
        self.assertIn('REGCACHE_NONE', source)
