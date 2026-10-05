"""Execute the linked coordinator and real transaction core on mocked suppliers.

Physical ADC timing/calibration/OCP and native activation are not established.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeControllerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        d = Path(cls.tmp.name)
        (d / 'linux/usb').mkdir(parents=True)
        for name in ('types', 'bitops', 'completion', 'delay', 'errno', 'ktime',
                     'module', 'mutex', 'power_supply', 'string', 'suspend',
                     'workqueue', 'usb/pd'):
            (d / 'linux' / (name + '.h')).write_text('/* kernel ABI shim */\n')
        (d / 'linux/errno.h').write_text('#include_next <linux/errno.h>\n')
        code = '#include "' + str(ROOT / 'tests/x710_controller_kernel_mock.h') + '"\n'
        code += r'''
#define PD_MAX_PAYLOAD 7
#define PDO_TYPE_FIXED 0
#define RDO_CAP_MISMATCH BIT(26)
#define RDO_USB_COMM BIT(25)
#define RDO_NO_SUSPEND BIT(24)
#define RDO_PROG(i,v,c,f) (((u32)(i)<<28)|(((v)/20)<<9)|((c)/50)|(f))
static unsigned int rdo_index(u32 p){return (p>>28)&7;}
static unsigned int pdo_type(u32 p){return p>>30;}
static unsigned int pdo_fixed_voltage(u32 p){return ((p>>10)&1023)*50;}
static unsigned int pdo_max_current(u32 p){return (p&1023)*10;}
static unsigned int rdo_op_current(u32 p){return ((p>>10)&1023)*10;}
static unsigned int rdo_max_current(u32 p){return (p&1023)*10;}
'''
        code += '#include "' + str(ROOT / 'kernel/drivers/x710-charging-policy.c') + '"\n'
        code += '#include "' + str(ROOT / 'kernel/drivers/x710-charge-controller.c') + '"\n'
        code += r'''
static int scenario,fail_event,block_event,event_count,lock_errors;
static int pps_count,restore_count,release_count,hardware_release,adc_count,sources,packs;
static bool hardware_owned,hardware_off=true,pps_mode;
static unsigned int pps_mv=8800,pps_ma=1800;
static int on_count,pause_count,resume_count,prepare_count,monitor_count;
static u64 lease;
static char trace[4096];static unsigned int trace_n;
static pthread_mutex_t barrier_lock=PTHREAD_MUTEX_INITIALIZER;
static pthread_cond_t barrier_cond=PTHREAD_COND_INITIALIZER;
static bool blocked,released;
static int event(char type){
 if(!pthread_mutex_trylock(&x710_controller_lock.native))pthread_mutex_unlock(&x710_controller_lock.native);
 else lock_errors++;
 trace[trace_n++]=type;trace[trace_n]=0;int n=++event_count;
 if(n==block_event){pthread_mutex_lock(&barrier_lock);blocked=true;pthread_cond_broadcast(&barrier_cond);
  while(!released)pthread_cond_wait(&barrier_cond,&barrier_lock);pthread_mutex_unlock(&barrier_lock);}
 atomic_fetch_add(&clock_ms,1);return n==fail_event?-EIO:0;
}
static void source(struct sm5714_pd_snapshot *s){
 unsigned int mv=pps_mode?pps_mv:9000,ma=pps_mode?pps_ma:1500;
 *s=(struct sm5714_pd_snapshot){.instance=11,.source_generation=12,.budget_generation=pps_mode?13+pps_count:13,
  .started_ms=atomic_load(&clock_ms)-1,.completed_ms=atomic_load(&clock_ms),
  .source_pdos={(9000/50<<10)|300,0xc0000000U|(110<<17)|(33<<8)|60},
  .nr_source_pdos=2,.budget_mv=mv,.budget_ma=ma,.online=pps_mode?2:1,
  .usb_type=pps_mode?3:2,.voltage_uv=(int)(mv*1000),.current_ua=(int)(ma*1000),
  .charge_requested=true,.pps_contract=pps_mode};
}
int x710_charge_request_observation(const struct x710_observer_owner *owner,
                                   struct x710_charge_observation *o){
 (void)owner;int ret=event('O');if(ret||scenario==19)return ret?ret:-ESTALE;
 memset(o,0,sizeof(*o));source(&o->source);o->pack.instance=21;
 if(scenario==17)o->source.source_pdos[1]=0;
 if(scenario==18)o->source.budget_mv=5000;
 if(scenario==25)o->source.nr_source_pdos=8;
 return 0;
}
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *s){
 int ret=event('S');if(ret)return ret;
 if(scenario==10&&pps_count)return -EIO;
 source(s);sources++;if(scenario==1&&sources==2)s->source_generation++;
 if(scenario==23&&sources==2)s->budget_generation++;
 return 0;
}
int sm5714_pd_read_owned_snapshot(u64 instance,u64 gen,u64 l,struct sm5714_pd_snapshot *s){
 if(instance!=11||gen!=12||l!=99)return -ESTALE;
 if(scenario==15)return -ENODEV;
 return sm5714_pd_read_snapshot(s);
}
int sm5714_battery_read_pack(u64 l,struct sm5714_pack_snapshot *p){
 int ret=event('B');if(ret)return ret;packs++;
 *p=(struct sm5714_pack_snapshot){.instance=21,.state_generation=22,.switching_lease=l,
  .started_ms=atomic_load(&clock_ms)-1,.completed_ms=atomic_load(&clock_ms),
  .typec_mv=pps_mode?pps_mv:9000,.typec_ma=pps_mode?pps_ma:1500,
  .capacity=30,.voltage_uv=3800000,.current_ua=-300000,.pack_decic=300,
  .health=1,.battery_present=true,.attached=true,.thermal_normal=true,
  .typec_owned=true,.typec_charge=true,.pps_contract=pps_mode};
 if(scenario==2&&packs==2)p->state_generation++;
 if(scenario==3)p->pack_decic=450;
 if(scenario==21)p->voltage_uv=4305500;
 if(scenario==26)p->instance++;
 if(scenario==27 && packs%2==1)p->current_ua=3600001;
 if(scenario==28 && packs%2==0)p->current_ua=3600001;
 if(scenario==29)p->current_ua=-3600001;
 if(scenario==30)return -EIO;
 if(scenario==31)p->current_ua=3600000;
 if(scenario==32)p->current_ua=-3600000;
 if(scenario==33)p->current_ua=0;
 return 0;
}
int sm5714_battery_switching_acquire(u64 *l){
 int ret=event('L');*l=lease=99;return ret;
}
int sm5714_pd_request_pps(u64 instance,u64 gen,u64 l,unsigned int mv,unsigned int ma,
                         struct sm5714_pd_snapshot *s){
 int ret=event('P');pps_count++;
 if(instance!=11||gen!=12||l!=99||!hardware_off)return -EPERM;
 if(scenario==16)x710_charge_controller_cancel();
 if(ret||scenario==9||scenario==10){pps_mode=false;return ret?ret:-EIO;}
 pps_mv=mv;pps_ma=ma;pps_mode=true;source(s);if(scenario==8)s->instance++;return 0;
}
int sm5714_pd_restore_fixed(u64 instance,u64 gen,u64 l,struct sm5714_pd_snapshot *s){
 int ret=event('F');restore_count++;
 if(instance!=11||gen!=12||l!=99||!hardware_off||hardware_owned)return -EPERM;
 if(ret||scenario==12)return ret?ret:-EIO;
 pps_mode=false;source(s);return 0;
}
int sm5714_pd_release_fixed(u64 instance,u64 gen,u64 l,const struct sm5714_fixed_proof *p){
 int ret=event('R');release_count++;
 if(instance!=11||gen!=12||l!=99||!p->pump_off||p->ibus_ua||pps_mode||hardware_owned)
  return -EPERM;
 if(ret||scenario==13)return ret?ret:-EIO;
 lease=0;return 0;
}
int sm5440_native_control(enum sm5440_native_operation op,const struct sm5440_native_owner *owner,
                         const struct sm5440_native_input *in,struct sm5440_native_result *out){
 (void)in;memset(out,0,sizeof(*out));int ret;
 if(op==SM5440_NATIVE_CLAIM){ret=event('C');out->owner=(struct sm5440_native_owner){31,32};
  out->owned=hardware_owned=true;out->hardware_quiesced=true;
  return ret?ret:scenario==20?-EIO:0;}
 if(!owner||owner->instance!=31||owner->generation!=32)return -ESTALE;
 if(op==SM5440_NATIVE_RELEASE){ret=event('Q');hardware_release++;
  out->owned=hardware_owned;out->owner=*owner;
  if(ret||scenario==11){hardware_off=false;return ret?ret:-EIO;}
  out->hardware_quiesced=true;out->owned=hardware_owned=false;hardware_off=true;return 0;}
 if(op==SM5440_NATIVE_CHECK_OFF){ret=event('c');return ret?ret:hardware_off?0:-EBUSY;}
 if(op==SM5440_NATIVE_PREPARE){ret=event('K');prepare_count++;return ret;}
 if(op==SM5440_NATIVE_BIND_SOURCE){ret=event('D');
  if(!in||in->switching_lease!=99||in->consumer_epoch!=x710_controller_generation)return -ESTALE;
  return ret;}
 if(op==SM5440_NATIVE_START||op==SM5440_NATIVE_RESUME){ret=event(op==SM5440_NATIVE_START?'N':'n');
  if(!x710_controller_activation_qualified)return -EPERM;
  if(ret)return ret;hardware_off=false;if(op==SM5440_NATIVE_START)on_count++;else resume_count++;return 0;}
 if(op==SM5440_NATIVE_PAUSE){ret=event('H');pause_count++;if(!ret)hardware_off=true;return ret;}
 if(op==SM5440_NATIVE_ADC_BEGIN||op==SM5440_NATIVE_MONITOR_BEGIN){
  ret=event(op==SM5440_NATIVE_ADC_BEGIN?'A':'U');adc_count++;
  if(op==SM5440_NATIVE_MONITOR_BEGIN)monitor_count++;return ret?ret:-EINPROGRESS;}

 if(op==SM5440_NATIVE_ADC_ADVANCE||op==SM5440_NATIVE_MONITOR_ADVANCE){
  ret=event(op==SM5440_NATIVE_ADC_ADVANCE?'a':'u');if(ret)return ret;
  if(scenario==14)return -EINPROGRESS;
  unsigned int mv=pps_mode?pps_mv:9000;
  out->physical=(struct x710_physical_sample){.observed_ms=atomic_load(&clock_ms)-1,
    .vbus_mv=mv,.vbat_mv=3800,.online=true,.valid=true,.pump_on=!hardware_off,
    .ibus_ua=hardware_off?0:1500000};
  out->vbus_uv=mv*1000;out->die_valid=true;out->die_decic=300;
  if(scenario==4)out->die_decic=420;
  if(scenario==5)out->vbus_uv+=100001;
  if(scenario==6)out->die_valid=false;
  if(scenario==7)out->physical.observed_ms-=101;
  if(scenario==24)out->physical.ibus_ua=625;
  return 0;}
 event('!');return -EPERM;
}
int sm5440_passive_request_fresh(struct sm5440_passive_measurement *p){
 int ret=event('M');if(ret||scenario==22)return ret?ret:-EBUSY;
 *p=(struct sm5440_passive_measurement){.observed_ms=atomic_load(&clock_ms)-1,
  .vbus_uv=9000000,.vbat_uv=3800000,.ibus_ua=0,.die_decic=300,.online=true};return 0;
}
static void reset(int mode,int failure){
 if(!x710_controller_wq)x710_controller_init();cancel_delayed_work_sync(&x710_controller_periodic);flush_work(&x710_controller_job);
 mutex_lock(&x710_controller_lock);x710_controller_quiescing=false;x710_controller_inflight=false;
 x710_controller_cancelled=false;x710_controller_unresolved=false;x710_controller_generation=1;
 x710_controller_active=false;x710_controller_activation_qualified=false;
 x710_controller_result=(struct x710_controller_result){};mutex_unlock(&x710_controller_lock);
 memset(&x710_controller,0,sizeof(x710_controller));scenario=mode;fail_event=failure;
 block_event=event_count=lock_errors=pps_count=restore_count=release_count=hardware_release=0;
 adc_count=sources=packs=0;on_count=pause_count=resume_count=prepare_count=monitor_count=0;
 pps_mv=8800;pps_ma=1800;hardware_owned=false;hardware_off=true;pps_mode=false;lease=0;
 trace_n=0;trace[0]=0;blocked=released=false;queue_fail=false;defer_work=false;
 atomic_store(&clock_ms,1000);atomic_store(&cancel_started,0);
}
static void output(int ret,const struct x710_controller_result *r,int64_t *o){
 o[0]=ret;o[1]=event_count;o[2]=lock_errors;o[3]=pps_count;o[4]=restore_count;o[5]=release_count;
 o[6]=hardware_release;o[7]=adc_count;o[8]=r->error;o[9]=r->cleanup_error;o[10]=r->unresolved;
 o[11]=r->hardware_quiesced;o[12]=r->pps_observed;o[13]=r->fixed_observed;
 o[14]=r->switching_released;o[15]=r->inflight;o[16]=r->cancelled;o[17]=r->lease;
 o[18]=r->generation;o[19]=x710_controller_unresolved;
 o[23]=r->pack_current_valid;o[24]=r->pack_current_ua;
}
void run(int mode,int failure,int command,int64_t *o){
 reset(mode,failure);struct x710_controller_result r;
 int ret=x710_charge_controller_request(command,8800,1800,&r);flush_work(&x710_controller_job);
 output(ret,&r,o);
}
const char *get_trace(void){return trace;}
struct request {int ret;struct x710_controller_result result;};
static void *request_thread(void *ptr){struct request *r=ptr;
 r->ret=x710_charge_controller_request(X710_CONTROLLER_OFF_ROUNDTRIP,8800,1800,&r->result);return NULL;}
static int pm_result;
static void *pm_thread(void *unused){(void)unused;pm_result=x710_controller_pm(NULL,PM_SUSPEND_PREPARE,NULL);return NULL;}
static void wait_blocked(void){pthread_mutex_lock(&barrier_lock);
 while(!blocked)pthread_cond_wait(&barrier_cond,&barrier_lock);pthread_mutex_unlock(&barrier_lock);}
static void release_provider(void){pthread_mutex_lock(&barrier_lock);released=true;
 pthread_cond_broadcast(&barrier_cond);pthread_mutex_unlock(&barrier_lock);}
void race(int mode,int64_t *o){
 reset(0,0);block_event=mode==3?1:20;struct request r={};pthread_t thread,pm;
 pthread_create(&thread,NULL,request_thread,&r);wait_blocked();
 struct x710_controller_result denied,status;
 int second=x710_charge_controller_request(X710_CONTROLLER_START,0,0,&denied);
 if(mode==0)x710_charge_controller_cancel();
 if(mode==1){pthread_create(&pm,NULL,pm_thread,NULL);
  while(!atomic_load(&cancel_started)){};}
 if(mode==2||mode==3){pthread_join(thread,NULL);x710_charge_controller_status(&status);
  int third=x710_charge_controller_request(X710_CONTROLLER_START,0,0,&denied);o[22]=third;
  o[21]=status.inflight;}
 release_provider();if(mode!=2&&mode!=3)pthread_join(thread,NULL);
 if(mode==1)pthread_join(pm,NULL);flush_work(&x710_controller_job);
 x710_charge_controller_status(&status);output(r.ret,&status,o);o[20]=second;
 if(mode==1){o[23]=pm_result;int before=event_count;
  x710_controller_pm(NULL,PM_POST_SUSPEND,NULL);o[24]=event_count-before;}
}
void blocked_next(int mode,int64_t *o){
 run(mode,0,0,o);struct x710_controller_result r;
 o[20]=x710_charge_controller_request(X710_CONTROLLER_OFF_ROUNDTRIP,8800,1800,&r);
 o[21]=x710_controller_pm(NULL,PM_SUSPEND_PREPARE,NULL);
}
int invalid(int mode){
 reset(0,0);struct x710_controller_result r;
 if(mode==0)return x710_charge_controller_request(99,0,0,&r);
 if(mode==1)return x710_charge_controller_request(0,8801,1800,&r);
 if(mode==2)return x710_charge_controller_request(0,8800,1850,&r);
 if(mode==3)x710_controller_quiescing=true;
 if(mode==4)x710_controller_generation=U64_MAX;
 if(mode==5)queue_fail=true;
 return x710_charge_controller_request(0,8800,1800,&r);
}
void active_cycle(int stage,int failure,int64_t *o){
 reset(0,0);x710_controller_activation_qualified=true;
 struct x710_controller_result r={};
 int ret=x710_charge_controller_request(X710_CONTROLLER_START,8800,1800,&r);
 flush_work(&x710_controller_job);o[25]=ret;o[26]=r.active;o[27]=r.generation;
 if(ret){output(ret,&r,o);return;}
 int before=event_count;
 if(failure)fail_event=before+failure;
 if(stage==1)ret=x710_charge_controller_request(X710_CONTROLLER_MONITOR,0,0,&r);
 if(stage==2)ret=x710_charge_controller_request(X710_CONTROLLER_REFRESH,0,0,&r);
 if(stage==3)ret=x710_charge_controller_request(X710_CONTROLLER_RETARGET,0,0,&r);
 if(stage==4)ret=x710_charge_controller_request(X710_CONTROLLER_STOP,0,0,&r);
 if(stage==5){scenario=11;ret=x710_charge_controller_request(X710_CONTROLLER_STOP,0,0,&r);}
 if(stage==6){scenario=13;ret=x710_charge_controller_request(X710_CONTROLLER_STOP,0,0,&r);}
 if(stage==7){x710_charge_controller_cancel();flush_work(&x710_controller_periodic.work);
  x710_charge_controller_status(&r);ret=r.error;}
 if(stage==8){ret=x710_controller_pm(NULL,PM_SUSPEND_PREPARE,NULL);
  x710_charge_controller_status(&r);o[40]=ret;ret=r.error;
  int prior=event_count;x710_controller_pm(NULL,PM_POST_SUSPEND,NULL);o[41]=event_count-prior;}
 if(stage==9){atomic_fetch_add(&clock_ms,101);
  ret=x710_charge_controller_request(X710_CONTROLLER_MONITOR,0,0,&r);}
 if(stage==10||stage==11){
  cancel_delayed_work_sync(&x710_controller_periodic);
  if(stage==11)x710_controller.refreshed_ms=atomic_load(&clock_ms)-4000;
  queue_work(x710_controller_wq,&x710_controller_periodic.work);
  flush_work(&x710_controller_periodic.work);x710_charge_controller_status(&r);ret=r.error;
 }
 if(stage>=13 && stage<=16){
  scenario=stage==13?27:stage==14?28:stage==15?29:30;
  ret=x710_charge_controller_request(stage==14?X710_CONTROLLER_REFRESH:
                                      X710_CONTROLLER_MONITOR,0,0,&r);
 }
 if(stage==12){scenario=15;ret=x710_charge_controller_request(X710_CONTROLLER_MONITOR,0,0,&r);}
 output(ret,&r,o);o[28]=r.active;o[29]=r.generation;o[30]=on_count;o[31]=pause_count;
 o[32]=resume_count;o[33]=prepare_count;o[34]=monitor_count;o[35]=hardware_owned;
 o[36]=hardware_off;o[37]=x710_controller.tx.target_mv;o[38]=x710_controller.tx.target_ma;
 o[39]=event_count-before;o[42]=r.pack_current_ua;o[43]=r.pack_current_valid;
 // End each test's mock session; preserve the asserted results before cleanup.
 cancel_delayed_work_sync(&x710_controller_periodic);
 if(x710_controller_active)x710_charge_controller_request(X710_CONTROLLER_STOP,0,0,&r);
}
'''
        (d / 'harness.c').write_text(code)
        result = subprocess.run(['gcc', '-std=c11', '-shared', '-fPIC', '-pthread',
                                 '-Wall', '-Wextra', '-Werror=implicit-function-declaration',
                                 '-Wno-unused-parameter', '-Wno-unused-function',
                                 '-I', str(d), str(d / 'harness.c'), '-o', str(d / 'test.so')],
                                capture_output=True, text=True)
        if result.returncode:
            raise RuntimeError(result.stderr)
        cls.lib = ctypes.CDLL(str(d / 'test.so'))
        cls.lib.get_trace.restype = ctypes.c_char_p

    def run_case(self, mode=0, failure=0, command=0):
        out = (ctypes.c_int64 * 25)()
        self.lib.run(mode, failure, command, out)
        return list(out)

    def test_actual_off_roundtrip_order_and_native_adc(self):
        out = self.run_case()
        self.assertEqual(out[0], 0)
        self.assertEqual(out[2:7], [0, 1, 1, 1, 1])
        self.assertEqual(out[8:15], [0, 0, 0, 1, 1, 1, 1])
        trace = self.lib.get_trace().decode()
        self.assertLess(trace.index('C'), trace.index('L'))
        self.assertLess(trace.index('L'), trace.index('P'))
        self.assertLess(trace.index('P'), trace.index('Q'))
        self.assertLess(trace.index('Q'), trace.index('F'))
        self.assertLess(trace.index('F'), trace.index('M'))
        self.assertLess(trace.index('M'), trace.index('R'))
        self.assertNotIn('!', trace)

    def test_real_first_and_second_pack_spikes_refuse_pps(self):
        for mode in (27, 28, 29):
            with self.subTest(mode=mode):
                o = self.run_case(mode)
                self.assertNotEqual(o[0], 0)
                self.assertEqual(o[3], 0, 'unsafe pack current must precede PPS')
                self.assertEqual(o[2], 0)
                self.assertEqual(o[6], 1)
                self.assertEqual(o[23:25], [1, -3600001 if mode == 29 else 3600001])

    def test_real_current_read_error_refuses_pps(self):
        o = self.run_case(30)
        self.assertEqual(o[0], -errno.EIO)
        self.assertEqual(o[3], 0)
        self.assertEqual(o[6], 1)
        self.assertEqual(o[23:25], [0, 0], 'read failure must not reuse old current')

    def test_pack_signed_endpoints_and_zero_are_real_allowed_measurements(self):
        for mode in (31, 32, 33):
            o = self.run_case(mode)
            self.assertEqual(o[0], 0)
            self.assertEqual(o[3:7], [1, 1, 1, 1])

    def test_active_pack_spike_or_read_failure_terminalizes_once(self):
        for stage in (13, 14, 15, 16):
            with self.subTest(stage=stage):
                o = self.active_case(stage)
                self.assertNotEqual(o[0], 0)
                self.assertEqual(o[28], 0)
                self.assertEqual(o[35:37], [0, 1])
                self.assertEqual(o[4:7], [1, 1, 1])
                self.assertEqual(o[30], 1, 'fault must not enable pump again')
                self.assertEqual(o[32], 0, 'paused fault must not resume pump')
                self.assertEqual(o[42:44], [0, 0] if stage == 16 else
                                 [-3600001 if stage == 15 else 3600001, 1])

    def test_default_direct_commands_cannot_mutate_suppliers(self):
        for command in range(1, 6):
            out = self.run_case(command=command)
            self.assertEqual(out[1:8], [0] * 7)
            self.assertEqual(out[0], 0 if command == 5 else
                             -errno.EACCES if command == 1 else -errno.EPERM)

    def test_every_supplier_error_and_no_unsafe_release(self):
        count = self.run_case()[1]
        for failure in range(1, count + 1):
            with self.subTest(event=failure):
                out = self.run_case(failure=failure)
                self.assertNotEqual(out[0], 0)
                self.assertEqual(out[2], 0)
                self.assertLessEqual(out[3], 1)
                self.assertLessEqual(out[4], 1)
                self.assertLessEqual(out[6], 1)
                trace = self.lib.get_trace().decode()
                if 'R' in trace:
                    self.assertLess(trace.index('Q'), trace.index('R'))

    def test_stale_source_pack_voltage_thermal_adc_refused(self):
        for mode in (1, 2, 3, 4, 5, 6, 7, 17, 18, 19, 21, 23, 24, 25, 26):
            with self.subTest(mode=mode):
                out = self.run_case(mode)
                self.assertNotEqual(out[0], 0)
                self.assertEqual(out[3], 0)
                self.assertEqual(out[2], 0)

    def test_microvolt_voltage_boundary_not_rounded_into_acceptance(self):
        out = self.run_case(5)
        self.assertEqual(out[0], -errno.ERANGE)
        self.assertEqual(out[3], 0)

    def test_pps_failure_uses_native_restore_receipt_not_second_setter(self):
        out = self.run_case(9)
        self.assertEqual(out[0], -errno.EIO)
        self.assertEqual(out[3:7], [1, 0, 1, 1])
        self.assertEqual(out[9:11], [0, 0])
        out = self.run_case(10)
        self.assertEqual(out[3:7], [1, 0, 0, 1])
        self.assertEqual(out[10], 1)

    def test_unknown_hardware_off_forbids_voltage_and_lease_release(self):
        out = self.run_case(11)
        self.assertNotEqual(out[0], 0)
        self.assertEqual(out[4:7], [0, 0, 1])
        self.assertEqual(out[10], 1)

    def test_failed_cleanup_latches_no_retry_and_vetoes_pm(self):
        for mode in (10, 11, 12, 13, 22):
            out = (ctypes.c_int64 * 25)()
            self.lib.blocked_next(mode, out)
            self.assertEqual(out[20], -errno.ESHUTDOWN)
            self.assertEqual(out[21], 2)
            self.assertEqual(out[10], 1)

    def test_detach_or_malformed_pps_receipt_stops_forward_progress(self):
        for mode in (8, 15):
            out = self.run_case(mode)
            self.assertNotEqual(out[0], 0)
            self.assertEqual(out[3], 1)
            self.assertEqual(out[6], 1)
            self.assertEqual(out[12], 0)

    def test_adc_budget_and_cancel_during_pps_cleanup_once(self):
        out = self.run_case(14)
        self.assertEqual(out[0], -errno.ETIMEDOUT)
        self.assertEqual(out[3], 0)
        self.assertEqual(out[6], 1)
        out = self.run_case(16)
        self.assertEqual(out[0], -errno.ECANCELED)
        self.assertEqual(out[6], 1)
        self.assertEqual(out[14], 1)

    def test_claim_failure_with_cleanup_token_is_not_success(self):
        out = self.run_case(20)
        self.assertEqual(out[0], -errno.EIO)
        self.assertEqual(out[6], 1)
        self.assertEqual(out[3:6], [0, 0, 0])

    def test_timeout_and_cancel_do_not_replace_inflight_worker(self):
        for mode in (0, 2, 3):
            out = (ctypes.c_int64 * 25)()
            self.lib.race(mode, out)
            self.assertEqual(out[20], -errno.EBUSY)
            self.assertEqual(out[2], 0)
            self.assertEqual(out[15], 0)
            if mode in (2, 3):
                self.assertEqual(out[0], -errno.ETIMEDOUT)
                self.assertEqual(out[21], 1)
                self.assertEqual(out[22], -errno.EBUSY)
            self.assertEqual(out[16], 1)
            self.assertEqual(out[3], 0 if mode == 3 else 1)
            self.assertLessEqual(out[6], 1)

    def test_pm_drains_forward_operation_and_cleanup_resume_never_starts(self):
        out = (ctypes.c_int64 * 25)()
        self.lib.race(1, out)
        self.assertEqual(out[0], -errno.ECANCELED)
        self.assertEqual(out[6], 1)
        self.assertEqual(out[14:17], [1, 0, 1])
        self.assertEqual(out[23:25], [1, 0])

    def test_admission_errors(self):
        for mode, error in enumerate((errno.EINVAL, errno.ERANGE, errno.ERANGE,
                                      errno.ESHUTDOWN, errno.EOVERFLOW, errno.EBUSY)):
            self.assertEqual(self.lib.invalid(mode), -error)

    def active_case(self, stage, failure=0):
        out = (ctypes.c_int64 * 44)()
        self.lib.active_cycle(stage, failure, out)
        self.assertEqual(out[25:27], [0, 1], 'mock grant must exercise actual entry')
        self.assertEqual(out[2], 0, 'supplier called under publication lock')
        return list(out)

    def test_mock_grant_retains_session_across_monitor_refresh_and_retarget(self):
        for stage in (1, 2, 3):
            o = self.active_case(stage)
            self.assertEqual(o[0], 0)
            self.assertEqual(o[28], 1)
            self.assertEqual(o[27], o[29], 'active operation replaced original epoch')
            self.assertEqual(o[4:7], [0, 0, 0], 'active operation terminalized ownership')
            self.assertEqual(o[35:37], [1, 0])
            self.assertEqual(o[30], 1)
            self.assertEqual(o[31:33], [0, 0] if stage == 1 else [1, 1])
            self.assertGreaterEqual(o[34], 2)
            self.assertLessEqual(o[38], 1800)
            if stage == 3:
                self.assertEqual(o[37], 8380)

    def test_active_stop_restores_each_owner_once(self):
        o = self.active_case(4)
        self.assertEqual(o[0], 0)
        self.assertEqual(o[4:7], [1, 1, 1])
        self.assertEqual(o[28], 0)
        self.assertEqual(o[35:37], [0, 1])
        self.assertEqual(o[14], 1)

    def test_every_active_operation_supplier_failure_ends_safe_not_retried(self):
        for stage in (1, 2, 3, 4):
            count = self.active_case(stage)[39]
            for failed in range(1, count + 1):
                with self.subTest(stage=stage, event=failed):
                    o = self.active_case(stage, failed)
                    self.assertNotEqual(o[0], 0)
                    self.assertEqual(o[28], 0)
                    self.assertLessEqual(o[4], 1)
                    self.assertLessEqual(o[5], 1)
                    self.assertLessEqual(o[6], 1)

    def test_unknown_active_off_and_failed_switching_release_are_latched(self):
        for stage in (5, 6):
            o = self.active_case(stage)
            self.assertNotEqual(o[0], 0)
            self.assertEqual(o[10], 1)
            self.assertEqual(o[28], 0)
            self.assertEqual(o[6], 1)
        o = self.active_case(5)
        self.assertEqual(o[4:6], [0, 0])

    def test_active_cancel_pm_and_late_monitor_exit_without_rearming(self):
        for stage in (7, 8, 9, 12):
            o = self.active_case(stage)
            self.assertNotEqual(o[0], 0)
            self.assertEqual(o[28], 0)
            self.assertEqual(o[35:37], [0, 1])
            self.assertEqual(o[6], 1)
        o = self.active_case(8)
        self.assertEqual(o[40:42], [1, 0])

    def test_actual_periodic_body_monitors_and_refreshes_same_session(self):
        for stage in (10, 11):
            o = self.active_case(stage)
            self.assertEqual(o[0], 0)
            self.assertEqual(o[28], 1)
            self.assertEqual(o[27], o[29])
            self.assertEqual(o[31:33], [0, 0] if stage == 10 else [1, 1])

    def test_profile_link_and_no_automatic_activation(self):
        patch = (ROOT / 'kernel/patches/0020-power-supply-hook-sm5440-native-control.patch').read_text()
        self.assertIn('obj-$(CONFIG_X710_NATIVE_CONTROL) += x710-charge-controller.o', patch)
        source = (ROOT / 'kernel/drivers/x710-charge-controller.c').read_text()
        self.assertNotIn('armed = true', source)
        self.assertNotIn('software_ocp_verified = true', source)
        self.assertNotIn('module_param(', source)
        self.assertNotIn('power_supply_set_property(', source)
        self.assertIn('flush_work(&x710_controller_job)', source)
        self.assertIn('.priority = 100', source)
        self.assertIn('sm5714_pd_release_fixed(', source)
        self.assertIn('x710-charge-controller.c) dest="$tree/drivers/power/supply"',
                      (ROOT / 'scripts/prepare-kernel.sh').read_text())


if __name__ == '__main__':
    unittest.main()
