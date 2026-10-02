"""Run the diagnostic C API with the established threaded provider mock.

The100ms functions remain frozen and are still tested by their original suite.
This new API reports age, not an active/freshness grant.
"""
import ctypes
import errno
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_sm5440_fresh_request as fresh
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class PassiveObservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Reuse the exact lifetime/clock/worker model, not its100ms decisions.
        fresh.FreshRequestTests.setUpClass()
        cls.addClassCleanup(fresh.FreshRequestTests.tmp.cleanup)
        code = (Path(fresh.FreshRequestTests.tmp.name) / 'fresh.c').read_text()
        src = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        header = (ROOT / 'kernel/drivers/sm5440-hw.h').read_text()
        code = code.replace('static struct mutex sm5440_companion_lock=',
                            function(header, 'struct sm5440_passive_observation {') +
                            ';\nstatic struct mutex sm5440_companion_lock=')
        observation = function(src, 'int sm5440_passive_observe(').replace(
            'if (atomic_dec_and_test(&sm->request_users))',
            'release_delay();\n\tif (atomic_dec_and_test(&sm->request_users))')
        code = code.replace('static void *unbind(void *data)',
                            observation +
                            '\nstatic void *unbind(void *data)')
        code = code.replace('if(scenario==28)atomic_store(&clock_ms,1120);',
                            'if(scenario==28)atomic_store(&clock_ms,1510);'
                            'if(scenario==38)atomic_store(&clock_ms,1139);')
        code = code.replace('current->sample.acquired_ms=1005;atomic_store(&clock_ms,1080);',
                            'current->sample.acquired_ms=1005;'
                            'current->sample.completed_ms=1140;atomic_store(&clock_ms,1140);')
        code = code.replace('atomic_store(&clock_ms,1101)', 'atomic_store(&clock_ms,1501)')
        code = code.replace('current->sample.acquired_ms=1081', 'current->sample.acquired_ms=1141')
        code = code.replace('atomic_store(&clock_ms,1100);', 'atomic_store(&clock_ms,1500);')
        code = code.replace('if(scenario==29)current->startup_confirmations=1;', r'''
 if(scenario==29)current->startup_confirmations=1;
 if(scenario==30)current->sample.completed_ms=0;
 if(scenario==31)current->sample.completed_ms=1004;
 if(scenario==32)current->sample.completed_ms=1141;
 if(scenario==35)current->sample.acquired_ms=1000;
 if(scenario==27)current->sample.completed_ms=1500;
''')
        code = code.replace('if(scenario==12)return;', r'''
 if(scenario==37){
  struct sm5440_passive_observation nested;
  recursive_result=sm5440_passive_observe(&nested);
 }
 if(scenario==12)return;
''')
        code = code.replace('atomic_fetch_add(&clock_ms,100);', 'atomic_fetch_add(&clock_ms,500);')
        code = code.replace('struct sm5440_passive_measurement value={0};',
                            'struct sm5440_passive_observation value={0};')
        code = code.replace('int ret=sm5440_passive_request_fresh(kind==2?NULL:&value);',
                            'int ret=sm5440_passive_observe(kind==2?NULL:&value);')
        for field in ('observed_ms', 'vbus_uv', 'vbat_uv', 'ibus_ua', 'die_decic', 'online'):
            code = code.replace(f'value.{field}', f'value.measurement.{field}')
        code = code.replace('struct sm5440_passive_measurement zero={0};',
                            'struct sm5440_passive_observation zero={0};')
        code = code.replace('out[12]=teardown_started;out[13]=drained;', r'''
 out[12]=teardown_started;out[13]=drained;
 out[14]=value.request_ms;out[15]=value.completed_ms;
 out[16]=value.returned_ms;out[17]=value.oldest_age_ms;
 out[18]=value.acquisition_seq;out[19]=value.request_epoch;
''')
        code = code.replace('if(kind!=1)sm5440_publish(&sm);',
                            'if(kind==33)atomic_store(&clock_ms,0);'
                            'if(kind!=1)sm5440_publish(&sm);')
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        path = Path(cls.tmp.name) / 'observation.c'
        path.write_text(code)
        binary = path.with_suffix('.so')
        result = subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                                 '-Wno-misleading-indentation', '-pthread', '-shared',
                                 '-fPIC', str(path), '-o', str(binary)],
                                capture_output=True, text=True)
        if result.returncode:
            raise AssertionError(result.stderr)
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.fresh_case.argtypes = [ctypes.c_int, ctypes.POINTER(ctypes.c_uint64)]

    def read(self, kind=0):
        values = (ctypes.c_uint64 * 20)()
        ret = self.lib.fresh_case(kind, values)
        self.assertEqual(list(values)[8:11], [0, 0, 0], 'users/reservation/locks drain')
        return ret, list(values)

    def refused(self, kind, error):
        ret, values = self.read(kind)
        self.assertEqual(ret, -error)
        self.assertEqual(values[6], 1, 'entire destination cleared on error')
        self.assertEqual(values[14:], [0] * 6)
        return values

    def test_slow_new_observation_reports_original_age_not_fresh_grant(self):
        ret, values = self.read()
        self.assertEqual(ret, 0)
        self.assertEqual(values[:6], [1005, 9000000, 4000000, 625, 300, 1])
        self.assertEqual(values[14:], [1000, 1140, 1140, 135, 6, 0])
        self.assertGreater(values[17], 100)
        self.assertEqual(values[7], 1)

    def test_null_and_absent_provider(self):
        self.assertEqual(self.read(2)[0], -errno.EINVAL)
        self.assertEqual(self.refused(1, errno.ENODEV)[7], 0)

    def test_admission_failures_never_queue(self):
        for kind, error in [(3, errno.ESHUTDOWN), (4, errno.EIO), (5, errno.EIO),
                            (6, errno.EIO), (7, errno.EAGAIN), (8, errno.EAGAIN),
                            (9, errno.EBUSY), (10, errno.EBUSY)]:
            with self.subTest(kind=kind):
                self.assertEqual(self.refused(kind, error)[7], 0)

    def test_wait_timeout_does_not_cancel_or_retry_monitor(self):
        self.assertEqual(self.refused(12, errno.ETIMEDOUT)[7], 1)
        api = function((ROOT / 'kernel/drivers/sm5440-direct.c').read_text(),
                       'int sm5440_passive_observe(')
        self.assertNotIn('cancel_delayed_work', api)
        self.assertEqual(api.count('mod_delayed_work('), 1)

    def test_budget_boundaries_and_release_delay(self):
        ret, values = self.read(27)
        self.assertEqual(ret, 0)
        self.assertEqual(values[14:18], [1000, 1500, 1500, 495])
        self.refused(13, errno.ETIMEDOUT)
        self.refused(28, errno.ETIMEDOUT)
        self.assertEqual(self.refused(24, errno.ETIMEDOUT)[7], 0)
        self.assertEqual(self.refused(33, errno.ETIMEDOUT)[7], 0)

    def test_timestamp_zero_backward_future_or_old_conversion(self):
        for kind in (14, 15, 16, 30, 31, 32):
            with self.subTest(kind=kind):
                self.refused(kind, errno.ESTALE)
        self.refused(25, errno.ETIMEDOUT)
        self.refused(38, errno.ETIMEDOUT)

    def test_same_millisecond_conversion_needs_new_sequence(self):
        ret, values = self.read(35)
        self.assertEqual(ret, 0)
        self.assertEqual(values[0], 1000)
        self.assertEqual(values[18], 6)
        self.refused(15, errno.ESTALE)

    def test_suspend_and_resume_epoch_do_not_adopt_old_work(self):
        self.refused(17, errno.ESHUTDOWN)
        self.refused(18, errno.ESHUTDOWN)

    def test_unpublish_wakes_and_drains_real_lifetime_thread(self):
        values = self.refused(19, errno.ENODEV)
        self.assertEqual(values[12:14], [1, 1])

    def test_legacy_and_diagnostic_requests_share_exclusion(self):
        for kind in (11, 37):
            ret, values = self.read(kind)
            self.assertEqual(ret, 0)
            self.assertEqual(ctypes.c_int64(values[11]).value, -errno.EBUSY)

    def test_i2c_active_pending_and_copy_contention_clear_output(self):
        for kind, error in [(20, errno.EBUSY), (21, errno.EIO), (22, errno.EBUSY),
                            (26, errno.ETIMEDOUT), (29, errno.EAGAIN)]:
            self.refused(kind, error)

    def test_offline_is_retained_as_fact(self):
        ret, values = self.read(23)
        self.assertEqual(ret, 0)
        self.assertEqual(values[5], 0)

    def test_legacy_functions_converter_and_quiesce_remain_frozen(self):
        current = (ROOT / 'kernel/drivers/sm5440-direct.c').read_text()
        old = subprocess.check_output(['git', 'show',
                                      '850f868d:kernel/drivers/sm5440-direct.c'],
                                     cwd=ROOT, text=True)
        for marker in ('int sm5440_passive_request_fresh(',
                       'int sm5440_passive_read_cached(',
                       'static int sm5440_copy_sample_locked(',
                       'static int sm5440_sample_once(', 'static int sm5440_quiesce('):
            with self.subTest(marker=marker):
                self.assertEqual(function(current, marker), function(old, marker))
        header = (ROOT / 'kernel/drivers/sm5440-hw.h').read_text()
        self.assertIn('#define SM5440_FRESH_REQUEST_MS 100U', header)
        self.assertIn('#define SM5440_PASSIVE_OBSERVATION_MS 500U', header)


if __name__ == '__main__':
    unittest.main()
