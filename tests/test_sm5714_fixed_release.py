"""Execute the actual source-bound lease release with lock-aware providers."""
import ctypes
import errno
from pathlib import Path
import subprocess
import unittest

from test_sm5714_policy import function
import test_sm5714_runtime_snapshot as snapshot


class FixedReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        snapshot.RuntimeSnapshotTests.setUpClass.__func__(cls)
        code = cls.fixture_code.replace('int exercise(', 'int snapshot_exercise(')
        header = (snapshot.ROOT/'kernel/drivers/sm5714-stage2.h').read_text()
        code += function(header, 'struct sm5714_fixed_proof {')+';\n'
        code += r'''
static int release_calls,release_error;
int sm5714_battery_switching_release_async(u64 lease) {
 if(registry_held||transport_held!=1||operation_held!=1||lease!=7)errors++;
 release_calls++;return release_error;
}
'''
        code += function(cls.source, 'int sm5714_pd_release_fixed(')+'\n'
        code += r'''
int exercise(int mode,int failure,long long *out) {
 struct sm5714_usbpd s;initialize(&s);port_under_test=&s;
 scenario=mode;errors=calls=force_busy=release_calls=release_error=0;
 clock_ms=1000;fail_at=failure;sm5714_port_provider=0;sm5714_port_issuer=0;
 values[0]=1;values[1]=POWER_SUPPLY_USB_TYPE_PD_PPS;values[2]=9000000;values[3]=1500000;
 s.budget_mv=9000;s.budget_ma=1500;sm5714_port_publish(&s);
 struct sm5714_fixed_proof proof={.observed_ms=990,.vbus_uv=9000000,.pump_off=true};
 u64 instance=1,source=2,lease=7;
 if(mode==1)sm5714_port_provider=0;
 if(mode==2)instance++;
 if(mode==3)source++;
 if(mode==4)proof.pump_off=false;
 if(mode==5)proof.ibus_ua=625;
 if(mode==6)proof.observed_ms=0;
 if(mode==7)proof.observed_ms=1010;
 if(mode==8)proof.observed_ms=907;
 if(mode==11)values[2]=5000000;
 if(mode==12)proof.vbus_uv=9100001;
 if(mode==13)proof.vbus_uv=8899999;
 if(mode==14)release_error=-EIO;
 if(mode==15)release_error=-ESTALE;
 if(mode==16)pthread_mutex_lock(&s.control_lock.m);
 if(mode==18)s.budget_pending=1;
 if(mode==19){values[0]=2;s.budget_pps=true;}
 if(mode==20)s.fault=true;
 if(mode==21)s.removing=true;
 if(mode==22)proof.observed_ms=908; /* inclusive100ms after eight property reads */
 if(mode==23)proof.vbus_uv=9100000;
 if(mode==24)proof.vbus_uv=8900000;
 if(mode==25)instance=0;
 if(mode==26)source=0;
 if(mode==27)lease=0;
 int ret=sm5714_pd_release_fixed(instance,source,lease,mode==28?NULL:&proof);
 if(mode==16)pthread_mutex_unlock(&s.control_lock.m);
 out[0]=calls;out[1]=atomic_read(&s.snapshot_users);out[2]=errors;
 out[3]=release_calls;out[4]=registry_held+transport_held+operation_held;
 sm5714_port_provider=0;destroy(&s);return ret;
}
'''
        c = Path(cls.tmp.name)/'release.c'
        c.write_text(code)
        lib = c.with_suffix('.so')
        subprocess.run(['cc', '-shared', '-fPIC', '-pthread', '-Wall', '-Werror',
                        '-Wno-misleading-indentation', str(c), '-o', str(lib)], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.exercise.argtypes = [ctypes.c_int, ctypes.c_int,
                                    ctypes.POINTER(ctypes.c_longlong)]

    def case(self, mode=0, failure=0):
        out = (ctypes.c_longlong*5)()
        ret = self.lib.exercise(mode, failure, out)
        self.assertEqual(out[1:3], [0, 0])
        self.assertEqual(out[4], 0)
        return ret, list(out)

    def test_fixed_pps_capable_source_releases_once_under_source_lock(self):
        ret, out = self.case()
        self.assertEqual(ret, 0)
        self.assertEqual(out[3], 1)

    def test_wrong_identity_bad_proof_and_pending_source_do_not_release(self):
        for mode in [1, 2, 3, 4, 5, 6, 7, 8, 12, 13, 16, 18, 19, 20, 21,
                     25, 26, 27, 28]:
            ret, out = self.case(mode)
            self.assertNotEqual(ret, 0)
            self.assertEqual(out[3], 0)

    def test_reset_and_budget_change_during_properties_do_not_release(self):
        for mode in [9, 10, 11]:
            ret, out = self.case(mode)
            self.assertNotEqual(ret, 0)
            self.assertEqual(out[3], 0)

    def test_each_property_failure_never_calls_release(self):
        for failure in range(1, 9):
            ret, out = self.case(failure=failure)
            self.assertEqual(ret, -errno.EIO)
            self.assertEqual(out[3], 0)

    def test_release_hardware_and_lease_errors_are_not_hidden_or_retried(self):
        for mode, expected in [(14, errno.EIO), (15, errno.ESTALE)]:
            ret, out = self.case(mode)
            self.assertEqual(ret, -expected)
            self.assertEqual(out[3], 1)

    def test_exact_physical_age_and_voltage_boundaries(self):
        for mode in [22, 23, 24]:
            ret, out = self.case(mode)
            self.assertEqual(ret, 0)
            self.assertEqual(out[3], 1)


if __name__ == '__main__':
    unittest.main()
