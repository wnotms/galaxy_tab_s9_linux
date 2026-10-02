"""Execute real fixed-restore/provider C against lock-aware TCPM faults.

The setter is a protocol mock, not evidence of hardware PPS or pump operation.
Actual battery lease checks are separately executed in SwitchingOwnershipTests.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import unittest

from test_sm5714_policy import function
import test_sm5714_runtime_snapshot as snapshot


class FixedRestoreTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot.RuntimeSnapshotTests.setUpClass.__func__(cls)
        code = cls.fixture_code.replace('int exercise(', 'int snapshot_exercise(')
        code = code.replace('static int errors,force_busy;',
                            'static int errors,force_busy,set_calls,set_error,checks,check_error;')
        code = code.replace(' v->intval=values[prop];return 0;}', r'''
 if(scenario==40&&calls==5)values[0]=1;
 if(scenario==41&&calls==4){mutex_lock(&port_under_test->lock);port_under_test->source_generation++;mutex_unlock(&port_under_test->lock);}
 if(scenario==42&&calls==4)port_under_test->budget_pending=1;
 v->intval=values[prop];return 0;}''')
        code += r'''
static int sm5714_battery_switching_check(u64 lease) {
 if(registry_held||transport_held||lease!=7)errors++;checks++;
 if(scenario==43&&checks==2)return -ESTALE;
 return check_error;
}
static int power_supply_set_property(struct power_supply *p,enum power_supply_property prop,
 const union power_supply_propval *v) {
 if(registry_held||transport_held||operation_held!=1||p!=&supply||
    prop!=POWER_SUPPLY_PROP_ONLINE||v->intval!=1)errors++;
 set_calls++;
 if(scenario==61){
  pthread_mutex_lock(&control);entered=true;pthread_cond_broadcast(&event);
  while(!released)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);
 }
 if(set_error)return set_error;
 values[0]=scenario==44?2:1;values[2]=9000000;values[3]=1500000;
 sm5714_budget_begin(port_under_test);
 sm5714_budget_end(port_under_test,0,true,9000,scenario==45?1400:1500,false);
 if(scenario==46){mutex_lock(&port_under_test->lock);port_under_test->source_generation++;mutex_unlock(&port_under_test->lock);}
 if(scenario==47){mutex_lock(&port_under_test->lock);sm5714_forget_source(port_under_test);mutex_unlock(&port_under_test->lock);}
 if(scenario==48)port_under_test->fault=true;
 return 0;
}
'''
        for marker in ('static int sm5714_restore_token(', 'int sm5714_pd_restore_fixed('):
            code += function(cls.source, marker) + '\n'
        code += r'''
static void *restorer(void *unused) {
 (void)unused;reader_ret=sm5714_pd_restore_fixed(1,2,7,&result);return 0;
}
int exercise(int mode,int failure,long long *out) {
 struct sm5714_usbpd s;initialize(&s);port_under_test=&s;
 scenario=mode;errors=calls=force_busy=set_calls=set_error=checks=check_error=0;
 clock_ms=1000;fail_at=failure;entered=released=false;
 atomic_store(&draining,0);atomic_store(&unpublished,0);
 sm5714_port_provider=0;sm5714_port_issuer=0;
 if(sm5714_port_publish(&s))errors++;
 values[0]=2;values[1]=POWER_SUPPLY_USB_TYPE_PD_PPS;
 values[2]=9000000;values[3]=1500000;
 s.budget_mv=9000;s.budget_ma=1500;
 u64 instance=1,source=2,lease=7;
 if(mode==30)values[0]=1;
 if(mode==31)sm5714_port_provider=0;
 if(mode==32)instance++;
 if(mode==33)source++;
 if(mode==34)check_error=-ESTALE;
 if(mode==35)pthread_mutex_lock(&s.control_lock.m);
 if(mode==36)values[0]=3;
 if(mode==37)values[0]=0;
 if(mode==38)values[1]=POWER_SUPPLY_USB_TYPE_PD;
 if(mode==39)values[1]=3;
 if(mode==49)set_error=-ETIMEDOUT;
 if(mode==50)set_error=-EIO;
 if(mode==51)s.budget_pending=1;
 if(mode==52)s.fault=true;
 if(mode==53)s.removing=true;
 if(mode==54)s.nr_source_pdos=0;
 if(mode==55)s.observation_exhausted=true;
 if(mode==56)instance=0;
 if(mode==57)source=0;
 if(mode==58)lease=0;
 if(mode==59)values[1]=POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS;
 if(mode==60){values[0]=1;values[1]=POWER_SUPPLY_USB_TYPE_PD_SPR_AVS;}
 memset(&result,0xff,sizeof(result));int ret;
 if(mode==61){
  pthread_t a,b;pthread_create(&a,0,restorer,0);
  pthread_mutex_lock(&control);while(!entered)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);
  pthread_create(&b,0,unpublisher,&s);int loops=0;
  while(!atomic_load(&draining)&&loops++<2000)usleep(1000);
  if(!atomic_load(&draining)||atomic_load(&unpublished)||atomic_read(&s.snapshot_users)!=1)errors++;
  pthread_mutex_lock(&control);released=true;pthread_cond_broadcast(&event);pthread_mutex_unlock(&control);
  pthread_join(a,0);pthread_join(b,0);if(!atomic_load(&unpublished))errors++;ret=reader_ret;
 }else ret=sm5714_pd_restore_fixed(instance,source,lease,mode==62?0:&result);
 if(mode==35)pthread_mutex_unlock(&s.control_lock.m);
 out[0]=calls;out[1]=atomic_read(&s.snapshot_users);out[2]=errors;
 unsigned char *bytes=(void *)&result;int nonzero=0;
 for(unsigned int i=0;i<sizeof(result);i++)nonzero+=!!bytes[i];
 out[3]=nonzero;out[4]=set_calls;out[5]=checks;out[6]=result.online;
 out[7]=result.budget_mv;out[8]=result.budget_ma;out[9]=result.source_generation;
 out[10]=operation_held;out[11]=registry_held+transport_held;
 sm5714_port_provider=0;destroy(&s);return ret;
}
'''
        c = Path(cls.tmp.name) / 'restore.c'
        c.write_text(code)
        lib = c.with_suffix('.so')
        subprocess.run(['cc', '-shared', '-fPIC', '-pthread', '-Wall', '-Werror',
                        '-Wno-misleading-indentation', str(c), '-o', str(lib)], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.exercise.argtypes = [ctypes.c_int, ctypes.c_int,
                                    ctypes.POINTER(ctypes.c_longlong)]

    def case(self, mode=0, failure=0):
        out = (ctypes.c_longlong * 12)()
        ret = self.lib.exercise(mode, failure, out)
        self.assertEqual(out[1:3], [0, 0])
        self.assertEqual(out[10:12], [0, 0])
        if ret and mode != 62:
            self.assertEqual(out[3], 0)
        return ret, list(out)

    def test_one_online_fixed_write_and_mirrored_result(self):
        ret, r = self.case()
        self.assertEqual(ret, 0)
        self.assertEqual(r[4:10], [1, 2, 1, 9000, 1500, 2])

    def test_already_fixed_does_not_write(self):
        for mode in (30, 60):
            ret, r = self.case(mode)
            self.assertEqual((ret, r[4], r[6]), (0, 0, 1))

    def test_dual_capability_pps_can_only_exit(self):
        ret, r = self.case(59)
        self.assertEqual((ret, r[4], r[6]), (0, 1, 1))

    def test_invalid_tokens_and_no_owner_never_write(self):
        for mode, error in ((31, errno.ENODEV), (32, errno.ESTALE),
                            (33, errno.ESTALE), (34, errno.ESTALE),
                            (56, errno.EINVAL), (57, errno.EINVAL), (58, errno.EINVAL)):
            ret, r = self.case(mode)
            self.assertEqual((ret, r[4]), (-error, 0))

    def test_busy_operation_is_refused_and_unpinned(self):
        ret, r = self.case(35)
        self.assertEqual((ret, r[4]), (-errno.EBUSY, 0))

    def test_active_avs_offline_and_inconsistent_type_are_refused(self):
        for mode in (36, 37, 38, 39):
            ret, r = self.case(mode)
            self.assertEqual((ret, r[4]), (-errno.EOPNOTSUPP, 0))

    def test_property_change_before_write_is_refused(self):
        ret, r = self.case(40)
        self.assertEqual((ret, r[4]), (-errno.EAGAIN, 0))

    def test_source_change_before_write_is_refused(self):
        ret, r = self.case(41)
        self.assertEqual((ret, r[4]), (-errno.ESTALE, 0))

    def test_pending_callback_before_write_is_refused(self):
        ret, r = self.case(42)
        self.assertEqual((ret, r[4]), (-errno.EAGAIN, 0))

    def test_lease_revoked_before_write_is_refused(self):
        ret, r = self.case(43)
        self.assertEqual((ret, r[4]), (-errno.ESTALE, 0))

    def test_all_property_errors_preserve_first_error_zero_output(self):
        for index in range(1, 17):
            ret, r = self.case(failure=index)
            self.assertEqual(ret, -errno.EIO)
            self.assertEqual(r[4], int(index > 8))

    def test_completed_setter_without_fixed_or_matching_budget_is_refused(self):
        for mode in (44, 45):
            self.assertEqual(self.case(mode)[0], -errno.EAGAIN)

    def test_source_change_or_withdrawal_after_setter_is_refused(self):
        for mode, error in ((46, errno.ESTALE), (47, errno.ENODATA)):
            self.assertEqual(self.case(mode)[0], -error)

    def test_fault_after_setter_is_refused(self):
        self.assertEqual(self.case(48)[0], -errno.EIO)

    def test_setter_error_is_not_hidden_or_retried(self):
        for mode, error in ((49, errno.ETIMEDOUT), (50, errno.EIO)):
            ret, r = self.case(mode)
            self.assertEqual((ret, r[4]), (-error, 1))

    def test_pending_fault_removal_source_absence_exhaustion_before_write(self):
        for mode, error in ((51, errno.EAGAIN), (52, errno.EIO),
                            (53, errno.ESHUTDOWN), (54, errno.ENODATA),
                            (55, errno.EOVERFLOW)):
            ret, r = self.case(mode)
            self.assertEqual((ret, r[4]), (-error, 0))

    def test_unbind_drains_blocking_standard_setter_before_resources(self):
        self.assertEqual(self.case(61)[0], -errno.ESHUTDOWN)

    def test_null_output(self):
        ret, r = self.case(62)
        self.assertEqual((ret, r[4]), (-errno.EINVAL, 0))

    def test_no_activation_tuning_release_or_writable_user_interface(self):
        body = function(self.source, 'int sm5714_pd_restore_fixed(')
        self.assertEqual(body.count('power_supply_set_property('), 1)
        self.assertIn('.intval = 1', body)
        self.assertNotIn('POWER_SUPPLY_PROP_VOLTAGE_NOW', body)
        self.assertNotIn('POWER_SUPPLY_PROP_CURRENT_NOW', body)
        self.assertNotIn('switching_release', body)
        self.assertIn('rdo, false)', function(self.source, 'static bool sm5714_request_allowed('))
        self.assertIn('0400', function(self.source, 'static void sm5714_snapshot_debug_init('))
