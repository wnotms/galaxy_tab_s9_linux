"""Execute actual PPS operation/RDO/callback C with a lock-aware TCPM mock.

Battery register programming is exercised separately by SwitchingOwnershipTests.
No mock result is evidence of physical PD, ADC, or direct charging.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import unittest

from test_sm5714_policy import function
import test_sm5714_runtime_snapshot as runtime


class OwnedPpsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runtime.RuntimeSnapshotTests.setUpClass.__func__(cls)
        code = cls.fixture_code.replace('int exercise(', 'int snapshot_exercise(')
        code = code.replace('struct tcpc_dev {int unused;};',
                            'struct sm5714_usbpd;struct tcpc_dev {struct sm5714_usbpd *owner;};')
        header = (runtime.ROOT/'kernel/drivers/sm5714-stage2.h').read_text()
        definition = function(header, 'struct sm5714_pd_snapshot {')+';\n'
        prelude = r'''
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define min(x,y) ((x)<(y)?(x):(y))
#define PDO_TYPE_FIXED 0
#define RDO_CAP_MISMATCH BIT(26)
#define RDO_USB_COMM BIT(25)
#define RDO_NO_SUSPEND BIT(24)
#define RDO_PROG(i,v,c,f) (((u32)(i)<<28)|(((v)/20)<<9)|((c)/50)|(f))
#define PD_HEADER_EXT_HDR BIT(15)
#define PD_DATA_REQUEST 2
#define PD_CTRL_SOFT_RESET 13
#define le16_to_cpu(x) (x)
#define le32_to_cpu(x) (x)
static unsigned int rdo_index(u32 r) {return (r>>28)&7;}
static unsigned int rdo_op_current(u32 r) {return ((r>>10)&1023)*10;}
static unsigned int rdo_max_current(u32 r) {return (r&1023)*10;}
static unsigned int pdo_type(u32 p) {return p>>30;}
static unsigned int pdo_fixed_voltage(u32 p) {return ((p>>10)&1023)*50;}
static unsigned int pdo_max_current(u32 p) {return (p&1023)*10;}
'''
        code = code.replace(definition, prelude+'\n#include "'+str(runtime.ROOT/'kernel/drivers/sm5714-pd-policy.h')+'"\n')
        code += '\n'.join(line for line in cls.source.splitlines() if line.startswith('#define SM5714_'))+'\n'
        code += r'''
#define dev_err(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)cleanup)
struct pd_message {uint16_t header;u32 payload[7];};
enum tcpm_transmit_type {TCPC_TX_SOP,TCPC_TX_HARD_RESET};
static unsigned int pd_header_cnt_le(uint16_t h) {return (h>>12)&7;}
static unsigned int pd_header_type_le(uint16_t h) {return h&31;}
static struct sm5714_usbpd *tcpc_to_sm5714(struct tcpc_dev *t){return t->owner;}
static int checks,check_fail,owned_calls,normal_calls,txio,tx_fail,set_calls,set_fail;
static int op_mode,trace_prop[20],trace_value[20],owned_error,cleanup_error;
static bool revoked,suspended,inhibited;
int sm5714_battery_switching_check(u64 lease) {
 if(registry_held||transport_held||lease!=7)errors++;
 checks++;if(checks==check_fail){revoked=true;return -ESTALE;}
 return suspended?-EAGAIN:revoked?-ESTALE:!inhibited?-ESTALE:0;
}
void sm5714_battery_typec_fault(void){revoked=true;inhibited=true;}
int sm5714_battery_set_pd_contract(unsigned int mv,unsigned int ma) {
 if(registry_held||transport_held)errors++;normal_calls++;
 if((mv!=0&&mv!=5000&&mv!=9000)||(!mv&&ma))return -ERANGE;
 return 0;
}
int sm5714_battery_set_owned_contract(u64 lease,unsigned int mv,unsigned int ma,
 enum sm5714_contract_kind kind) {
 if(registry_held||transport_held||lease!=7||!inhibited)errors++;
 (void)mv;(void)ma;(void)kind;owned_calls++;
 if(op_mode==130){mutex_lock(&port_under_test->lock);sm5714_forget_source(port_under_test);mutex_unlock(&port_under_test->lock);}
 return owned_error;
}
static int regmap_bulk_write(struct regmap *r,unsigned int a,const void *v,unsigned int n) {
 (void)r;(void)a;(void)v;(void)n;if(!transport_held)errors++;
 return ++txio==tx_fail?-EIO:0;
}
static int regmap_write(struct regmap *r,unsigned int a,unsigned int v) {
 (void)r;(void)a;(void)v;if(!transport_held)errors++;
 return ++txio==tx_fail?-EIO:0;
}
static int regmap_update_bits(struct regmap *r,unsigned int a,unsigned int mask,unsigned int v) {
 (void)mask;return regmap_write(r,a,v);
}
'''
        for marker in ('static int sm5714_result(', 'static int sm5714_usbpd_set_current_limit(',
                       'static bool sm5714_request_allowed(', 'static int sm5714_usbpd_transmit('):
            code += function(cls.source,marker)+'\n'
        code += r'''
static int power_supply_set_property(struct power_supply *p,enum power_supply_property prop,
 const union power_supply_propval *v) {
 if(registry_held||transport_held||operation_held!=1||p!=&supply)errors++;
 set_calls++;if(set_calls<20){trace_prop[set_calls]=prop;trace_value[set_calls]=v->intval;}
 if(op_mode==144&&set_calls==1){
  pthread_mutex_lock(&control);entered=true;pthread_cond_broadcast(&event);
  while(!released)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);
 }
 if(set_calls==set_fail)return -ETIMEDOUT;
 if(cleanup_error&&prop==POWER_SUPPLY_PROP_ONLINE&&v->intval==1)return cleanup_error;
 unsigned int mv=values[2]/1000,ma=values[3]/1000;bool pps=true;
 if(prop==POWER_SUPPLY_PROP_ONLINE){if(v->intval==1){mv=9000;ma=1500;pps=false;}else if(v->intval!=2){errors++;return -EINVAL;}}
 else if(prop==POWER_SUPPLY_PROP_CURRENT_NOW)ma=v->intval/1000;
 else if(prop==POWER_SUPPLY_PROP_VOLTAGE_NOW)mv=v->intval/1000;
 else{errors++;return -EINVAL;}
 unsigned int actual_mv=mv,actual_ma=ma;
 if(op_mode==113&&pps)actual_ma=2000;
 if(op_mode==114&&pps&&set_calls==3)actual_mv=mv+20;
 struct pd_message msg={.header=0x1002};
 msg.payload[0]=pps?RDO_PROG(3,actual_mv,actual_ma,RDO_USB_COMM|RDO_NO_SUSPEND):
  (2U<<28)|((ma/10)<<10)|(ma/10)|RDO_USB_COMM|RDO_NO_SUSPEND;
 int ret=sm5714_usbpd_transmit(&port_under_test->tcpc,TCPC_TX_SOP,&msg,0);
 if(ret)return ret;
 if(!pps&&values[2]!=9000000){
  ret=sm5714_usbpd_set_current_limit(&port_under_test->tcpc,SM5714_STANDBY_MAX_MW*1000/(values[2]/1000),values[2]/1000);
  if(ret)return ret;
 }
 ret=sm5714_usbpd_set_current_limit(&port_under_test->tcpc,actual_ma,actual_mv);
 if(ret)return ret;
 values[0]=pps?2:1;values[1]=POWER_SUPPLY_USB_TYPE_PD_PPS;
 values[2]=actual_mv*1000;values[3]=actual_ma*1000;
 if(op_mode==115&&set_calls==2)values[2]+=20000;
 if(op_mode==116&&set_calls==2){mutex_lock(&port_under_test->lock);port_under_test->source_generation++;mutex_unlock(&port_under_test->lock);}
 if(op_mode==117&&set_calls==2){mutex_lock(&port_under_test->lock);sm5714_forget_source(port_under_test);mutex_unlock(&port_under_test->lock);}
 return 0;
}
'''
        for marker in ('static int sm5714_restore_token(', 'static int sm5714_restore_fixed_pinned(',
                       'int sm5714_pd_restore_fixed(', 'static bool sm5714_pps_pair_locked(',
                       'static int sm5714_pps_step(', 'int sm5714_pd_request_pps('):
            code += function(cls.source,marker)+'\n'
        code += r'''
static unsigned int requested_mv,requested_ma;
static void *pps_reader(void *unused) {
 (void)unused;reader_ret=sm5714_pd_request_pps(1,2,7,requested_mv,requested_ma,&result);return 0;
}
int exercise(int mode,int arg,long long *out) {
 struct sm5714_usbpd sm;initialize(&sm);sm.tcpc.owner=&sm;port_under_test=&sm;
 sm.operating_snk_mw=13500;sm.nr_source_pdos=3;
 sm.source_pdos[0]=(100U<<10)|300;sm.source_pdos[1]=(180U<<10)|300;
 sm.source_pdos[2]=(3U<<30)|(110U<<17)|(50U<<8)|60;
 sm.budget_mv=9000;sm.budget_ma=1500;
 sm5714_port_provider=0;sm5714_port_issuer=0;sm5714_port_publish(&sm);
 scenario=0;op_mode=mode;errors=calls=force_busy=fail_at=checks=check_fail=owned_calls=normal_calls=txio=tx_fail=set_calls=set_fail=owned_error=cleanup_error=0;
 memset(trace_prop,0,sizeof(trace_prop));memset(trace_value,0,sizeof(trace_value));
 clock_ms=1000;revoked=suspended=false;inhibited=true;entered=released=false;
 atomic_store(&draining,0);atomic_store(&unpublished,0);
 values[0]=1;values[1]=POWER_SUPPLY_USB_TYPE_PD_PPS;values[2]=9000000;values[3]=1500000;
 requested_mv=8800;requested_ma=1800;u64 instance=1,source=2,lease=7;
 if(mode==100)requested_mv=9000;
 if(mode==101){requested_mv=9600;requested_ma=1450;}
 if(mode==102)revoked=true;
 if(mode==103)instance=2;
 if(mode==104)source=3;
 if(mode==105)sm.nr_source_pdos=2;
 if(mode==106){sm.budget_mv=5000;sm.budget_ma=1800;values[2]=5000000;values[3]=1800000;}
 if(mode==107)requested_mv=10520;
 if(mode==108)requested_ma=1850;
 if(mode==109)requested_mv=8801;
 if(mode==110)requested_ma=1799;
 if(mode==111){requested_mv=8800;requested_ma=1500;}
 if(mode==112)sm.operating_snk_mw=0;
 if(mode==118)set_fail=arg;
 if(mode==119)fail_at=arg;
 if(mode==120)tx_fail=arg;
 if(mode==121)check_fail=arg;
 if(mode==122)suspended=true;
 if(mode==123)sm.budget_pending=1;
 if(mode==124)sm.fault=true;
 if(mode==125)sm.removing=true;
 if(mode==126)sm.observation_exhausted=true;
 if(mode==127)instance=0;
 if(mode==128)source=0;
 if(mode==129)lease=0;
 if(mode==131)owned_error=-EREMOTEIO;
 if(mode==132){set_fail=2;cleanup_error=-EIO;}
 if(mode==133)pthread_mutex_lock(&sm.control_lock.m);
 if(mode==134){values[0]=2;sm.budget_pps=true;}
 if(mode==135){
  values[0]=2;sm.budget_pps=true;sm.pps_lease=7;sm.pps_source_generation=2;
  sm.pps_mv=9000;sm.pps_ma=1500;requested_mv=9000;requested_ma=1500;
 }
 if(mode==136){values[0]=3;sm.budget_pps=true;}
 if(mode==147)sm.nr_source_pdos=8;
 if(mode==148)sm.source_pdos[2]|=1U<<28;
 if(mode==149)sm.source_pdos[2]|=1U<<16;
 memset(&result,0xff,sizeof(result));int ret;
 if(mode==144){
  pthread_t a,b;pthread_create(&a,0,pps_reader,0);
  pthread_mutex_lock(&control);while(!entered)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);
  pthread_create(&b,0,unpublisher,&sm);int loops=0;
  while(!atomic_load(&draining)&&loops++<2000)usleep(1000);
  if(!atomic_load(&draining)||atomic_load(&unpublished)||atomic_read(&sm.snapshot_users)!=1)errors++;
  pthread_mutex_lock(&control);released=true;pthread_cond_broadcast(&event);pthread_mutex_unlock(&control);
  pthread_join(a,0);pthread_join(b,0);if(!atomic_load(&unpublished))errors++;ret=reader_ret;
 }else ret=sm5714_pd_request_pps(instance,source,lease,requested_mv,requested_ma,mode==137?0:&result);
 if(mode==133)pthread_mutex_unlock(&sm.control_lock.m);
 if(mode==138||mode==139){
  assert(!ret);u64 saved=sm.pps_lease;
  struct sm5714_pd_snapshot temp;
  ret=sm5714_pd_restore_fixed(mode==138?2:1,mode==139?3:2,7,&temp);
  if(sm.pps_lease!=saved)errors++;
  memset(&result,0,sizeof(result));
 }
 if(mode==140){assert(!ret);ret=sm5714_pd_restore_fixed(1,2,7,&result);}
 if(mode==141){assert(!ret);mutex_lock(&sm.lock);sm5714_forget_source(&sm);mutex_unlock(&sm.lock);memset(&result,0,sizeof(result));}
 if(mode==142){assert(!ret);ret=sm5714_usbpd_set_current_limit(&sm.tcpc,1700,8800);memset(&result,0,sizeof(result));}

 if(mode==146){
  assert(!ret);int before=txio;
  struct pd_message m={.header=0x1002,.payload={RDO_PROG(3,8800,1800,RDO_USB_COMM|RDO_NO_SUSPEND)}};
  ret=sm5714_usbpd_transmit(&sm.tcpc,TCPC_TX_SOP,&m,0);
  if(txio!=before)errors++;memset(&result,0,sizeof(result));
 }
 out[0]=errors;out[1]=atomic_read(&sm.snapshot_users);out[2]=operation_held+registry_held+transport_held;
 unsigned char *bytes=(void *)&result;int nonzero=0;for(unsigned int i=0;i<sizeof(result);i++)nonzero+=!!bytes[i];
 out[3]=nonzero;out[4]=set_calls;out[5]=owned_calls;out[6]=normal_calls;out[7]=txio;
 out[8]=sm.pps_lease;out[9]=sm.pps_mv;out[10]=sm.pps_ma;out[11]=sm.fault;
 out[12]=result.online;out[13]=result.budget_mv;out[14]=result.budget_ma;out[15]=result.pps_contract;
 out[16]=trace_prop[1];out[17]=trace_value[1];out[18]=trace_prop[2];out[19]=trace_value[2];
 out[20]=trace_prop[3];out[21]=trace_value[3];out[22]=trace_prop[4];out[23]=trace_value[4];
 out[27]=sm.pps_operation_active;
 out[24]=inhibited;out[25]=revoked;out[26]=sm.last_request_pps;
 sm5714_port_provider=0;destroy(&sm);return ret;
}
'''
        code=code.replace('#include <stdint.h>', '#include <stdint.h>\n#include <assert.h>')
        c=Path(cls.tmp.name)/'owned-pps.c';c.write_text(code);lib=c.with_suffix('.so')
        p=subprocess.run(['cc','-shared','-fPIC','-pthread','-Wall','-Werror',
                          '-Wno-misleading-indentation',str(c),'-o',str(lib)],capture_output=True,text=True)
        if p.returncode:raise AssertionError(p.stderr)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.exercise.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.POINTER(ctypes.c_longlong)]

    def case(self,mode=0,arg=0):
        out=(ctypes.c_longlong*28)();ret=self.lib.exercise(mode,arg,out)
        self.assertEqual(out[:3],[0,0,0]);self.assertEqual(out[24],1);self.assertEqual(out[27],0)
        if ret and mode!=137:self.assertEqual(out[3],0)
        return ret,list(out)

    def test_initial_current_first_then_voltage_and_real_rdo_callbacks(self):
        ret,r=self.case();self.assertEqual(ret,0)
        self.assertEqual(r[4:8],[3,3,0,9])
        self.assertEqual(r[12:16],[2,8800,1800,1])
        self.assertEqual(r[16:22],[0,2,3,1800000,2,8800000])
        self.assertEqual(r[8:11],[7,8800,1800])

    def test_target_seed_voltage_needs_only_activation_and_current(self):
        ret,r=self.case(100);self.assertEqual((ret,r[4]),(0,2))
        self.assertEqual(r[12:16],[2,9000,1800,1])

    def test_voltage_first_when_lower_current_intermediate_lacks_operating_power(self):
        ret,r=self.case(101);self.assertEqual(ret,0)
        self.assertEqual(r[16:22],[0,2,2,9600000,3,1450000])
        self.assertEqual(r[12:16],[2,9600,1450,1])

    def test_already_owned_unchanged_pair_requests_a_real_refresh(self):
        ret,r=self.case(135);self.assertEqual((ret,r[4]),(0,1))
        self.assertEqual(r[16:18],[3,1500000])

    def test_wrong_identity_lease_and_capabilities_do_not_write(self):
        for mode,error in ((102,errno.ESTALE),(103,errno.ESTALE),(104,errno.ESTALE),
                           (105,errno.ERANGE),(106,errno.ERANGE),(134,errno.ESTALE)):
            ret,r=self.case(mode);self.assertEqual((ret,r[4]),(-error,0))

    def test_bounds_steps_power_and_missing_operating_power_do_not_write(self):
        for mode in (107,108,109,110,111,112):
            ret,r=self.case(mode);self.assertEqual((ret,r[4]),(-errno.ERANGE,0))

    def test_automatic_rdo_current_increase_is_rejected_before_i2c(self):
        ret,r=self.case(113);self.assertEqual(ret,-errno.ERANGE)
        self.assertEqual((r[7],r[8],r[11]),(0,0,1))

    def test_bounded_but_unrequested_voltage_is_rejected(self):
        ret,r=self.case(114);self.assertEqual(ret,-errno.ERANGE)
        self.assertEqual((r[8],r[11]),(0,1))

    def test_inconsistent_properties_attempt_one_fixed_cleanup_preserving_error(self):
        ret,r=self.case(115);self.assertEqual(ret,-errno.EAGAIN)
        self.assertEqual((r[4],r[8]),(3,0));self.assertEqual(r[20:22],[0,1])

    def test_source_change_and_disappearance_do_not_cleanup_new_source(self):
        for mode,error in ((116,errno.ESTALE),(117,errno.ENODATA)):
            ret,r=self.case(mode);self.assertEqual(ret,-error)
            self.assertEqual((r[4],r[8]),(2,0))

    def test_each_setter_timeout_preserves_first_error_and_no_retry(self):
        for step in (1,2,3):
            ret,r=self.case(118,step);self.assertEqual(ret,-errno.ETIMEDOUT)
            self.assertEqual(r[8],0)
            self.assertLessEqual(r[4],step+1)

    def test_each_property_failure_zero_output_and_clears_failed_owner(self):
        for index in range(1,33):
            ret,r=self.case(119,index);self.assertEqual(ret,-errno.EIO)
            self.assertEqual(r[8],0)

    def test_each_transport_transfer_failure_faults_and_keeps_inhibited(self):
        for index in (1,2,3):
            ret,r=self.case(120,index);self.assertEqual(ret,-errno.EIO)
            self.assertEqual((r[8],r[11],r[25]),(0,1,1))

    def test_lease_loss_before_each_critical_operation_cancels(self):
        for index in range(1,11):
            ret,r=self.case(121,index);self.assertEqual(ret,-errno.ESTALE)
            self.assertEqual(r[8],0)

    def test_pm_pending_fault_remove_exhaustion_and_bad_inputs_do_not_write(self):
        for mode,error in ((122,errno.EAGAIN),(123,errno.EAGAIN),(124,errno.EIO),
                           (125,errno.ESHUTDOWN),(126,errno.EOVERFLOW),(127,errno.EINVAL),
                           (128,errno.EINVAL),(129,errno.EINVAL),(133,errno.EBUSY),
                           (136,errno.EAGAIN),(137,errno.EINVAL)):
            ret,r=self.case(mode);self.assertEqual((ret,r[4]),(-error,0))

    def test_callback_generation_race_and_owned_hardware_error_refuse(self):
        for mode,error in ((130,errno.ESTALE),(131,errno.EREMOTEIO)):
            ret,r=self.case(mode);self.assertEqual(ret,-error)
            self.assertEqual((r[8],r[11]),(0,1))

    def test_cleanup_error_does_not_replace_first_failure(self):
        ret,r=self.case(132);self.assertEqual(ret,-errno.ETIMEDOUT)
        self.assertEqual((r[4],r[8]),(3,0))

    def test_stale_restorer_cannot_revoke_newer_owner(self):
        for mode in (138,139):
            ret,r=self.case(mode);self.assertEqual(ret,-errno.ESTALE)
            self.assertEqual(r[8],7)

    def test_explicit_fixed_restore_with_transitional_old_voltage_keeps_off(self):
        ret,r=self.case(140);self.assertEqual(ret,0)
        self.assertEqual(r[12:16],[1,9000,1500,0])
        self.assertEqual((r[4],r[5],r[8]),(4,5,0))

    def test_source_forget_invalidates_window(self):
        _,r=self.case(141);self.assertEqual(r[8:11],[0,0,0])

    def test_callback_cannot_publish_budget_other_than_actual_request(self):
        ret,r=self.case(142);self.assertEqual(ret,-errno.ERANGE)
        self.assertEqual((r[8],r[11]),(0,1))

    def test_unpublish_drains_blocking_operation_before_resources(self):
        ret,r=self.case(144);self.assertEqual(ret,-errno.ESTALE)
        self.assertEqual(r[8],0)

    def test_pps_permission_closes_after_api_and_unsolicited_refresh_is_refused(self):
        ret,r=self.case(146);self.assertEqual(ret,-errno.ERANGE)
        self.assertEqual((r[8],r[11]),(0,1))

    def test_oversized_source_cache_and_avs_reserved_apdo_do_not_write(self):
        for mode,error in ((147,errno.EPROTO),(148,errno.ERANGE),(149,errno.ERANGE)):
            ret,r=self.case(mode);self.assertEqual((ret,r[4]),(-error,0))
