"""Execute the actual RAW converter and actual passive worker, without READY."""
import ctypes
import errno
import importlib.util
from pathlib import Path
import subprocess
import unittest

import test_sm5440_adc_timing as timing
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class RawHardwareTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the regmap/time/lock fault transport, not its READY assertions.
        # Both compilations use actual repository C, never mirrored decisions.
        timing.TimingHardwareTests.setUpClass.__func__(cls)
        p = Path(cls.tmp.name)
        mock = p / 'mock.c'
        source = mock.read_text().replace(
            'ret=sm5440_timing_step(&m,&t);',
            'ret=sm5440_timing_raw_step(&m,&t);')
        source = source.replace('fake_clock+=5;',
                                'fake_clock+=5; if(scenario==30&&m.enables&&!t.count)'
                                'fake_clock=t.raw_anchor_ms-1;')
        source = source.replace('out[19]=m.dropped_effective;', r'''
out[19]=m.dropped_effective;out[20]=t.observation_mode;
out[21]=t.count?t.sample[0].adc_begin_ms-t.raw_anchor_ms:0;
out[22]=t.count>1?t.sample[1].adc_begin_ms-t.sample[0].adc_end_ms:0;
out[23]=0;for(unsigned int i=0;i<t.count;i++)out[23]+=!!(t.sample[i].interrupt[3]&1);
''')
        source += r'''
void exercise_mixed(int raw_first,int *out){
 struct regmap m={0};struct sm5440_timing t={0};fake_clock=1000;
 m.reg[0x2b]=0x11;m.reg[0x1c]=0x88;m.reg[0x1d]=0x41;
 int ret=sm5440_timing_begin(&m,&t);
 if(!ret)ret=raw_first?sm5440_timing_raw_step(&m,&t):sm5440_timing_step(&m,&t);
 int before=m.calls;
 ret=raw_first?sm5440_timing_step(&m,&t):sm5440_timing_raw_step(&m,&t);
 out[0]=ret;out[1]=m.calls-before;out[2]=sm5440_timing_finish(&m,&t,ret);
 out[3]=t.restored;out[4]=m.unsafe;
}
'''
        mock.write_text(source)
        lib = p / 'raw.so'
        subprocess.run(['cc', '-shared', '-fPIC', '-std=gnu11', '-Wall',
                        '-Wextra', '-Werror', '-Wno-misleading-indentation',
                        '-D__KERNEL__', '-DCONFIG_SM5440_ADC_RAW_TEST=1',
                        '-I'+str(p), '-I'+str(ROOT/'kernel/drivers'),
                        str(mock), str(ROOT/'kernel/drivers/sm5440-timing.c'),
                        '-o', str(lib)], check=True)
        cls.lib = ctypes.CDLL(str(lib))
        cls.lib.exercise.argtypes = [ctypes.c_int]*4+[ctypes.POINTER(ctypes.c_int)]
        cls.lib.exercise_cycle.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]
        cls.lib.exercise_mixed.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_int)]

    def case(self, scenario=1, fail=0, uncertain=0, drop=0):
        out = (ctypes.c_int*24)()
        self.lib.exercise(scenario, fail, uncertain, drop, out)
        self.assertEqual(out[5], 0, 'unsafe register write or early enable')
        return list(out)

    def cycle(self, scenario=1):
        out = (ctypes.c_int*20)()
        self.lib.exercise_cycle(scenario, out)
        self.assertEqual(list(out)[4:6], [0, 0], 'unsafe I/O or held wait lock')
        return list(out)

    def test_eight_raw_reads_without_a_single_ready_exact_restore(self):
        r = self.case()
        self.assertEqual(r[:7], [0, 0, 0, 8, 1, 0, 1])
        self.assertEqual(r[8:10], [0x88, 0x41])
        self.assertEqual(r[16], 0)
        self.assertEqual(r[20], 2)
        self.assertEqual(r[23], 0)
        self.assertGreaterEqual(r[11], 50)
        self.assertGreaterEqual(r[21], 20)
        self.assertGreaterEqual(r[22], 50)
        self.assertLess(r[14], 2000)
        self.assertEqual(r[15], 1, 'stale READY retained separately before enable')

    def test_optional_ready_retained_without_waiting_for_eight_events(self):
        r = self.case(0)
        self.assertEqual(r[0], 0)
        self.assertEqual(r[3], 8)
        self.assertGreater(r[23], 0)
        self.assertLess(r[23], 8)

    def test_time_before_enable_readback_is_refused(self):
        r = self.case(30)
        self.assertEqual(r[0], -errno.ESTALE)
        self.assertEqual(r[3], 0)
        self.assertEqual(r[4], 1)

    def test_raw_and_ready_modes_cannot_be_mixed_or_touch_i2c(self):
        for first in (0, 1):
            out = (ctypes.c_int*5)()
            self.lib.exercise_mixed(first, out)
            self.assertEqual(list(out), [-errno.EINVAL, 0, -errno.EINVAL, 1, 0])

    def test_admission_no_writes_when_active_wrong_chip_or_bad_source(self):
        for scenario in (8, 9, 10):
            r = self.case(scenario)
            self.assertLess(r[0], 0)
            self.assertEqual(r[10], 0)

    def test_physical_bounds_and_live_faults_still_refuse(self):
        for scenario in (2, 3, 4, 5, 6, 7, 20, 21, 22, 23, 24):
            with self.subTest(scenario=scenario):
                r = self.case(scenario)
                self.assertLess(r[0], 0)
                self.assertEqual(r[8]&1, 0)

    def test_all_i2c_failures_and_uncertain_writes_are_terminal(self):
        total = self.case()[7]
        for fail in range(1, total+1):
            for uncertain in (0, 1):
                with self.subTest(fail=fail, uncertain=uncertain):
                    r = self.case(fail=fail, uncertain=uncertain)
                    self.assertLess(r[0], 0)
                    self.assertTrue(r[1] or r[2])
                    self.assertLessEqual(r[6], 1)
                    if r[4]:
                        self.assertEqual(r[8:10], [0x88, 0x41])

    def test_ignored_writes_cannot_report_success(self):
        witnessed = 0
        for drop in range(1, self.case()[7]+1):
            r = self.case(drop=drop)
            if r[19]:
                witnessed += 1
                self.assertLess(r[0], 0)
        self.assertGreaterEqual(witnessed, 5)

    def test_cancel_bad_clock_and_global_deadline_still_refuse(self):
        for scenario, code in ((11, errno.ESHUTDOWN), (13, errno.ESTALE),
                               (14, errno.ETIMEDOUT)):
            r = self.case(scenario)
            self.assertEqual(r[0], -code)
            self.assertEqual(r[8]&1, 0)
            self.assertEqual(r[4], 1)

    def test_real_worker_completes_without_ready(self):
        r = self.cycle()
        self.assertEqual(r[:7], [0, 0, 8, 1, 0, 0, 1])
        self.assertEqual(r[7:11], [0, 0, 0, 0])
        self.assertEqual(r[16:18], [0x88, 0x41])

    def test_real_worker_readiness_source_pack_fault_and_pm_cancellation(self):
        for scenario in (40, 41):
            r = self.cycle(scenario)
            self.assertEqual(r[0], 0)
            self.assertEqual(r[12], 3)
        for scenario in (2, 3, 6, 7, 11):
            r = self.cycle(scenario)
            self.assertLess(r[0], 0)
            self.assertEqual(r[7:11], [1, 0, 1, 1])
            self.assertEqual(r[15], 0)
        for scenario in (44, 45):
            r = self.cycle(scenario)
            self.assertEqual(r[0], -errno.ESTALE)
            self.assertEqual(r[2:4], [8, 1])
        for scenario in (42, 43, 46):
            r = self.cycle(scenario)
            self.assertLess(r[0], 0)
            self.assertEqual(r[14], 0)


class RawIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location(
            'raw_gate', ROOT/'scripts/verify-x710-charging-profile.py')
        cls.gate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.gate)

    def test_resolved_profile_exclusivity_and_production_rejection(self):
        cfg = self.gate.BASE.read_text()+'\nCONFIG_CHARGER_SM5440_DIRECT=y\nCONFIG_SM5440_ADC_RAW_TEST=y\n'
        self.assertTrue(self.gate.verify(cfg, profile='sm5440-adc-raw')['valid'])
        for profile in ('sm5440-passive', 'sm5440-policy-offline',
                        'sm5440-adc-condition', 'sm5440-adc-timing'):
            self.assertFalse(self.gate.verify(cfg, profile=profile)['valid'])
        for symbol in ('CONFIG_X710_CHARGING_POLICY', 'CONFIG_SM5440_ADC_TIMING_TEST',
                       'CONFIG_SM5440_ADC_CONDITION_TEST'):
            self.assertFalse(self.gate.verify(cfg+'\n'+symbol+'=y\n',
                                             profile='sm5440-adc-raw')['valid'])
        self.assertFalse(self.gate.STAGE2.verify(cfg)['valid'])

    def test_no_charging_companion_or_freshness_claim_and_no_resume_rearm(self):
        src = (ROOT/'kernel/drivers/sm5440-direct.c').read_text()
        pub = function(src, 'static int sm5440_publish(')
        part = pub.split('#elif defined(CONFIG_SM5440_ADC_RAW_TEST)')[1].split('#else')[0]
        self.assertIn('return 0;', part)
        self.assertNotIn('sm5440_companion =', part)
        show = function(src, 'static void sm5440_timing_show(')
        self.assertIn('conversion_freshness_proven=0', show)
        self.assertIn('raw_sample%u_read_ms=', show)
        self.assertNotIn('regmap_', show)
        self.assertIn('if (sm->timing.attempted)\n\t\treturn -EOPNOTSUPP;',
                      function(src, 'static int sm5440_resume('))


if __name__ == '__main__':
    unittest.main()
