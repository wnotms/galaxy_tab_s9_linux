"""Execute the integrated read-only API with real producer C and pthread locks."""
import ctypes
import errno
from pathlib import Path
import subprocess
import unittest

import test_sm5714_owned_pps as owned
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class OwnedObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        owned.OwnedPpsTests.setUpClass.__func__(cls)
        p = Path(cls.tmp.name)
        if 'int sm5714_pd_read_owned_snapshot(' not in cls.source:
            raise AssertionError('read-only observer must be present in the actual driver')
        cls.actual_source = cls.source
        cls.fixed_baseline = subprocess.run(
            ['git', 'show', '2f245cea:kernel/drivers/sm5714_usbpd.c'], cwd=ROOT,
            capture_output=True, text=True, check=True).stdout
        code = (p / 'owned-pps.c').read_text().replace('int exercise(', 'int pps_fixture_exercise(')
        code = code.replace('if(registry_held||transport_held||p!=&supply)errors++;calls++;',
                            'if(registry_held||transport_held||operation_held!=1||p!=&supply)errors++;calls++;')
        code = code.replace('if(scenario==11&&calls==5)values[2]=9000000;',
                            'if(scenario==11&&calls==5)values[2]+=20000;')
        code = code.replace('if(calls==fail_at)return -EIO;',
                            'if(calls==fail_at)return -EIO;'
                            'if(scenario==40&&calls==8){mutex_lock(&port_under_test->lock);'
                            'sm5714_pps_revoke_locked(port_under_test);mutex_unlock(&port_under_test->lock);}')
        for marker in ('static int sm5714_owned_observer_token(',
                       'int sm5714_pd_read_owned_snapshot('):
            code += function(cls.actual_source, marker) + '\n'
        code += r'''
static void *observe_reader(void *unused) {
 (void)unused;reader_ret=sm5714_pd_read_owned_snapshot(1,2,7,&result);return 0;
}
int observe(int mode,int arg,long long *out) {
 struct sm5714_usbpd sm;initialize(&sm);sm.tcpc.owner=&sm;port_under_test=&sm;
 sm.operating_snk_mw=13500;sm.nr_source_pdos=3;
 sm.source_pdos[0]=(100U<<10)|300;sm.source_pdos[1]=(180U<<10)|300;
 sm.source_pdos[2]=(3U<<30)|(110U<<17)|(50U<<8)|60;
 sm.budget_mv=sm.pps_mv=9000;sm.budget_ma=sm.pps_ma=1500;sm.budget_pps=true;
 sm.pps_lease=7;sm.pps_source_generation=2;
 sm5714_port_provider=0;sm5714_port_issuer=0;sm5714_port_publish(&sm);
 scenario=op_mode=errors=calls=force_busy=fail_at=checks=check_fail=owned_calls=normal_calls=txio=tx_fail=set_calls=set_fail=owned_error=cleanup_error=0;
 clock_ms=1000;revoked=suspended=false;inhibited=true;entered=released=false;
 atomic_store(&draining,0);atomic_store(&unpublished,0);
 values[0]=2;values[1]=POWER_SUPPLY_USB_TYPE_PD_PPS;values[2]=9000000;values[3]=1500000;
 u64 instance=1,source=2,lease=7;
 if(mode==1)sm5714_port_provider=0;
 if(mode==2)force_busy=1;
 if(mode==3)sm.fault=true;
 if(mode==4)sm.removing=true;
 if(mode==5)sm.nr_source_pdos=0;
 if(mode==6)sm.budget_pending=1;
 if(mode==7)sm.observation_exhausted=true;
 if(mode==8)instance=2;
 if(mode==9)source=3;
 if(mode==10)lease=8;
 if(mode==11){values[0]=1;sm.budget_pps=false;}
 if(mode==12)values[0]=1; /* PPS capability label on fixed mode */
 if(mode==13)sm.pps_operation_active=true;
 if(mode==14)sm.pps_restoring=true;
 if(mode==15)sm.pps_mv=9020;
 if(mode==16)sm.charge_requested=false;
 if(mode==18)sm.source_pdos[2]|=1U<<28; /* unsupported AVS */
 if(mode==19)sm.source_pdos[2]|=1U<<16;
 if(mode==20)sm.operating_snk_mw=0;
 if(mode==21)fail_at=arg;
 if(mode==22)check_fail=arg;
 if(mode==23)scenario=9; /* source reset during getter */
 if(mode==24)scenario=10; /* actual begin/end budget callback */
 if(mode==25)scenario=11; /* lockless supply publication */
 if(mode==26)scenario=13; /* native clock rollback */
 if(mode==27)suspended=true;
 if(mode==28)revoked=true;
 if(mode==29)inhibited=false;
 if(mode==30)instance=0;
 if(mode==31)source=0;
 if(mode==32)lease=0;
 if(mode==33)sm.nr_source_pdos=8;
 if(mode==34)sm.pps_source_generation=3;
 if(mode==35)values[2]=9020000;
 if(mode==36)values[3]=1450000;
 if(mode==37)values[0]=3;
 if(mode==38)values[1]=POWER_SUPPLY_USB_TYPE_PD_SPR_AVS;
 if(mode==40)scenario=40;
 memset(&result,0xff,sizeof(result));int ret;
 if(mode==17){
  scenario=17;pthread_t a,b;pthread_create(&a,0,observe_reader,0);
  pthread_mutex_lock(&control);while(!entered)pthread_cond_wait(&event,&control);pthread_mutex_unlock(&control);
  pthread_create(&b,0,unpublisher,&sm);int loops=0;
  while(!atomic_load(&draining)&&loops++<2000)usleep(1000);
  if(!atomic_load(&draining)||atomic_load(&unpublished)||atomic_read(&sm.snapshot_users)!=1)errors++;
  pthread_mutex_lock(&control);released=true;pthread_cond_broadcast(&event);pthread_mutex_unlock(&control);
  pthread_join(a,0);pthread_join(b,0);if(!atomic_load(&unpublished))errors++;ret=reader_ret;
 }else ret=sm5714_pd_read_owned_snapshot(instance,source,lease,mode==39?0:&result);
 out[0]=errors;out[1]=atomic_read(&sm.snapshot_users);out[2]=operation_held+registry_held+transport_held;
 out[3]=calls;out[4]=set_calls+txio+owned_calls+normal_calls;out[5]=checks;
 unsigned char *bytes=(void *)&result;int nonzero=0;for(unsigned int i=0;i<sizeof(result);i++)nonzero+=!!bytes[i];
 out[6]=nonzero;out[7]=result.instance;out[8]=result.source_generation;out[9]=result.budget_generation;
 out[10]=result.online;out[11]=result.budget_mv;out[12]=result.budget_ma;
 out[13]=result.started_ms;out[14]=result.completed_ms;out[15]=sm.pps_lease;
 out[16]=sm.pps_mv;out[17]=sm.pps_ma;out[18]=sm.budget_generation;
 sm5714_port_provider=0;destroy(&sm);return ret;
}
'''
        c = p / 'owned-observer.c'
        c.write_text(code)
        lib = c.with_suffix('.so')
        result = subprocess.run(['cc', '-shared', '-fPIC', '-pthread', '-Wall', '-Werror',
                                 '-Wno-misleading-indentation', str(c), '-o', str(lib)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.observe.argtypes = [ctypes.c_int, ctypes.c_int,
                                   ctypes.POINTER(ctypes.c_longlong)]

    def case(self, mode=0, arg=0):
        out = (ctypes.c_longlong * 19)()
        ret = self.lib.observe(mode, arg, out)
        self.assertEqual(list(out[:3]), [0, 0, 0], 'lock/lifetime leak')
        self.assertEqual(out[4], 0, 'read-only API must not generate Requests or programming')
        if ret and mode != 39:
            self.assertEqual(out[6], 0, 'failed output must be fully zeroed')
        return ret, list(out)

    def test_native_active_receipt_without_request_or_budget_change(self):
        ret, out = self.case()
        self.assertEqual(ret, 0)
        self.assertEqual(out[3:6], [8, 0, 2])
        self.assertEqual(out[7:15], [1, 2, 4, 2, 9000, 1500, 1000, 1008])
        self.assertEqual(out[15:], [7, 9000, 1500, 4])

    def test_invalid_identity_and_null_output_do_no_supplier_io(self):
        for mode in (8, 9, 10, 30, 31, 32, 34, 39):
            ret, out = self.case(mode)
            self.assertLess(ret, 0)
            self.assertEqual(out[3], 0)

    def test_missing_busy_fault_draining_and_exhausted_provider(self):
        for mode in (1, 2, 3, 4, 5, 6, 7, 33):
            self.assertLess(self.case(mode)[0], 0)

    def test_fixed_capability_and_malformed_or_inactive_pps_are_not_active_proof(self):
        for mode in (11, 12, 13, 14, 15, 16, 18, 19, 20, 35, 36, 37, 38):
            self.assertLess(self.case(mode)[0], 0)

    def test_every_getter_error_propagates_without_mutation(self):
        for call in range(1, 9):
            ret, out = self.case(21, call)
            self.assertEqual(ret, -errno.EIO)
            self.assertEqual(out[3], call)
            self.assertEqual(out[15:], [7, 9000, 1500, 4])

    def test_lease_check_before_and_after_native_read(self):
        for call in (1, 2):
            ret, out = self.case(22, call)
            self.assertEqual(ret, -errno.ESTALE)
            self.assertEqual(out[5], call)

    def test_source_reset_budget_callback_publication_and_clock_change(self):
        for mode in (23, 24, 25, 26):
            self.assertLess(self.case(mode)[0], 0)

    def test_pm_revocation_or_switching_not_inhibited(self):
        for mode in (27, 28, 29, 40):
            self.assertLess(self.case(mode)[0], 0)

    def test_unpublish_drains_actual_pinned_read_and_refuses_removing_source(self):
        self.assertEqual(self.case(17)[0], -errno.ESHUTDOWN)

    def test_integrated_api_is_readonly_and_preserves_fixed_wrapper(self):
        before = function(self.fixed_baseline, 'int sm5714_pd_read_snapshot(')
        after = function(self.actual_source, 'int sm5714_pd_read_snapshot(')
        self.assertEqual(before, after)
        for marker in ('static int sm5714_owned_observer_token(',
                       'int sm5714_pd_read_owned_snapshot('):
            body = function(self.actual_source, marker)
            for banned in ('set_property', 'pps_request(', 'regmap_', 'release_async', 'msleep'):
                self.assertNotIn(banned, body)


if __name__ == '__main__':
    unittest.main()
