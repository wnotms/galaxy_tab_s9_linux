"""Execute the actual optional observer C with bounded request/stop/time mocks."""
import ctypes
import errno
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'kernel/diagnostics/sm5440-fresh-observer/sm5440-fresh-observer.c'


class FreshObserverTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        src = SOURCE.read_text()
        header = (ROOT / 'kernel/drivers/sm5440-hw.h').read_text()
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
typedef uint64_t u64;typedef uint32_t u32;
#define OBSERVER_CALLS 8U
#define OBSERVER_INTERVAL_MS 1000U
#define SM5440_FRESH_REQUEST_MS 100U
static unsigned int calls,sleeps;static int fail_at,kind,locked,errors,stop_at;
static u64 clock_ms;
static int result_lock;
static u64 ktime_get_boottime(void) {return clock_ms;}
#define ktime_to_ms(x) (x)
static void mutex_lock(int *m) {(void)m;locked++;}
static void mutex_unlock(int *m) {(void)m;locked--;}
static bool kthread_should_stop(void) {return stop_at>=0 && (int)calls>=stop_at;}
static int msleep_interruptible(unsigned int ms) {
 if(locked)errors++;sleeps++;clock_ms+=ms;
 return kind==24 ? 1 : 0;
}
'''
        code += function(header, 'struct sm5440_passive_measurement {') + ';\n'
        start = src.index('enum observer_state {')
        code += src[start:src.index('static DEFINE_MUTEX', start)]
        code += r'''
static struct observer_row rows[OBSERVER_CALLS];static unsigned int nr_rows;
static enum observer_state state;
static int sm5440_passive_request_fresh(struct sm5440_passive_measurement *m) {
 if(locked)errors++;calls++;
 m->observed_ms=clock_ms+5;m->vbus_uv=5000000;m->vbat_uv=4000000;
 m->ibus_ua=0;m->die_decic=300;m->online=true;clock_ms+=80;
 if((int)calls!=fail_at)return 0;
 switch(kind) {
 case 1:memset(m,0,sizeof(*m));return -ETIMEDOUT;
 case 2:memset(m,0,sizeof(*m));return -EIO;
 case 3:memset(m,0,sizeof(*m));return -ESHUTDOWN;
 case 4:memset(m,0,sizeof(*m));return -ENODEV;
 case 5:memset(m,0,sizeof(*m));return -EBUSY;
 case 6:clock_ms+=21;break;
 case 7:m->observed_ms=clock_ms-81;break;
 case 8:m->observed_ms=clock_ms+1;break;
 case 9:m->observed_ms=0;break;
 case 10:m->online=false;break;
 case 11:m->ibus_ua=625;break;
 case 12:m->vbus_uv=9500001;break;
 case 13:m->vbus_uv=4499999;break;
 case 14:m->vbat_uv=4300000;break;
 case 15:m->vbat_uv=3499999;break;
 case 16:m->die_decic=420;break;
 case 17:m->die_decic=224;break;
 case 18:clock_ms-=81;break;
 case 19:clock_ms+=20;break;
 case 20:m->observed_ms=clock_ms-80;break;
 case 21:m->vbus_uv=9500000;break;
 case 22:m->vbus_uv=4500000;m->vbat_uv=3500000;m->die_decic=225;break;
 case 23:m->vbat_uv=4299999;m->die_decic=419;break;
 }
 return 0;
}
'''
        code += function(src, 'static int observer_check(') + '\n'
        code += function(src, 'static int observer_thread(') + '\n'
        code += r'''
int run(int scenario,int failed_call,int stop,u64 *out) {
 memset(rows,0,sizeof(rows));nr_rows=calls=sleeps=0;state=OBSERVER_RUNNING;
 errors=locked=0;clock_ms=1000;kind=scenario;fail_at=failed_call;stop_at=stop;
 observer_thread(NULL);
 out[0]=calls;out[1]=nr_rows;out[2]=state;out[3]=sleeps;out[4]=errors;out[5]=locked;
 if(nr_rows){struct observer_row *r=&rows[nr_rows-1];
  out[6]=r->provider_status;out[7]=r->status;out[8]=r->raw.observed_ms;
  out[9]=r->requested_ms;out[10]=r->returned_ms;out[11]=r->raw.ibus_ua;
 }
 return nr_rows ? rows[nr_rows-1].status : 0;
}
int null_check(void) {return observer_check(1000,1080,0,NULL);}
'''
        cfile = Path(cls.tmp.name) / 'observer.c'
        so = Path(cls.tmp.name) / 'observer.so'
        cfile.write_text(code)
        subprocess.run(['cc', '-std=gnu11', '-Wall', '-Wextra', '-Werror',
                        '-Wno-misleading-indentation', '-Wno-unused-parameter',
                        '-shared', '-fPIC', str(cfile), '-o', str(so)], check=True,
                       capture_output=True)
        cls.lib = ctypes.CDLL(str(so))
        cls.lib.run.argtypes = [ctypes.c_int] * 3 + [ctypes.POINTER(ctypes.c_uint64)]
        cls.lib.run.restype = ctypes.c_int

    def run_case(self, kind=0, fail_at=1, stop=-1):
        result = (ctypes.c_uint64 * 12)()
        status = self.lib.run(kind, fail_at, stop, result)
        self.assertEqual(result[4], 0, 'no lock over request/sleep')
        self.assertEqual(result[5], 0, 'lock released')
        return status, list(result)

    def test_eight_successes_are_bounded_and_complete(self):
        status, row = self.run_case()
        self.assertEqual(status, 0)
        self.assertEqual(row[:4], [8, 8, 1, 7])
        self.assertGreaterEqual(row[8], row[9])
        self.assertLessEqual(row[10] - row[9], 100)

    def test_null_measurement_refused(self):
        self.assertEqual(self.lib.null_check(), -errno.EINVAL)

    def test_provider_timeout_stops_first_call(self):
        status, row = self.run_case(1)
        self.assertEqual(status, -errno.ETIMEDOUT)
        self.assertEqual(row[:4], [1, 1, 2, 0])
        self.assertEqual(row[8], 0)

    def test_i2c_failure_stops_after_partial_success(self):
        status, row = self.run_case(2, fail_at=3)
        self.assertEqual(status, -errno.EIO)
        self.assertEqual(row[:4], [3, 3, 2, 2])

    def test_suspend_refusal_no_resume_retry(self):
        status, row = self.run_case(3)
        self.assertEqual(status, -errno.ESHUTDOWN)
        self.assertEqual(row[0], 1)

    def test_unpublished_provider_refused(self):
        self.assertEqual(self.run_case(4)[0], -errno.ENODEV)

    def test_busy_provider_not_retried(self):
        status, row = self.run_case(5)
        self.assertEqual(status, -errno.EBUSY)
        self.assertEqual(row[0], 1)

    def test_delivery_above_100ms_stops(self):
        status, row = self.run_case(6)
        self.assertEqual(status, -errno.ETIMEDOUT)
        self.assertEqual(row[10] - row[9], 101)

    def test_old_future_or_missing_timestamp_refused(self):
        for kind in (7, 8, 9):
            self.assertEqual(self.run_case(kind)[0], -errno.ESTALE)

    def test_offline_refused(self):
        self.assertEqual(self.run_case(10)[0], -errno.ENODATA)

    def test_nonzero_ibus_keeps_failed_raw_evidence(self):
        status, row = self.run_case(11)
        self.assertEqual(status, -errno.EBUSY)
        self.assertEqual(row[11], 625)
        self.assertEqual(row[0], 1)

    def test_voltage_or_temperature_bounds_refused(self):
        for kind in range(12, 18):
            self.assertEqual(self.run_case(kind)[0], -errno.ERANGE)

    def test_clock_reversal_refused(self):
        self.assertEqual(self.run_case(18)[0], -errno.ETIMEDOUT)

    def test_exact_deadline_acquisition_and_safe_bounds(self):
        for kind in (19, 20, 21, 22, 23):
            status, row = self.run_case(kind)
            self.assertEqual(status, 0)
            self.assertEqual(row[0], 8)

    def test_stop_before_first_request(self):
        status, row = self.run_case(stop=0)
        self.assertEqual(status, 0)
        self.assertEqual(row[:4], [0, 0, 3, 0])

    def test_unload_during_interval_stops_without_extra_call(self):
        status, row = self.run_case(stop=2)
        self.assertEqual(status, 0)
        self.assertEqual(row[:4], [2, 2, 3, 2])

    def test_interrupted_sleep_never_starts_next_request(self):
        status, row = self.run_case(24)
        self.assertEqual(status, 0)
        self.assertEqual(row[:4], [1, 1, 3, 1])

    def test_no_hardware_policy_or_read_trigger(self):
        src = SOURCE.read_text()
        show = function(src, 'static int observer_result_show(')
        self.assertNotIn('sm5440_passive_request_fresh', show)
        for token in ('regmap_', 'i2c_', 'power_supply_set_property', 'module_param',
                      'sm5714_battery_', 'SM5440_MODE_', 'debugfs_create_file_unsafe'):
            self.assertNotIn(token, src)
        self.assertIn('debugfs_create_file("result", 0400', src)
        exit_code = function(src, 'static void __exit observer_exit(')
        self.assertLess(exit_code.index('kthread_stop'), exit_code.index('debugfs_remove'))
        self.assertEqual(src.count('sm5440_passive_request_fresh(&row.raw)'), 1)


class ObserverTaskLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.tmp.cleanup)
        src = SOURCE.read_text()
        code = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <errno.h>
#define __init
#define __exit
#define DEFINE_SHOW_ATTRIBUTE(x)
#define IS_ERR(x) ((intptr_t)(x)<0 && (intptr_t)(x)>-4096)
#define PTR_ERR(x) ((intptr_t)(x))
#define IS_ERR_OR_NULL(x) (!(x)||IS_ERR(x))
struct dentry {int unused;};struct task_struct {int refs, running;};
static struct dentry root;static struct task_struct task;
static struct dentry *observer_root;static struct task_struct *observer_task;
static int observer_result_fops;
static int failure,fast,errors,joined,removed,gets,wakes;
static int observer_thread(void *arg) {(void)arg;return 0;}
static struct dentry *debugfs_create_dir(const char *name,void *p) {
 (void)name;(void)p;return failure==1 ? (void*)-ENOMEM : failure==2 ? NULL : &root;
}
static struct dentry *debugfs_create_file(const char *name,int perm,void *p,void *d,void *f) {
 (void)name;(void)perm;(void)p;(void)d;(void)f;return failure==3 ? (void*)-EINVAL : &root;
}
static void debugfs_remove(void *p) {(void)p;removed++;}
static struct task_struct *kthread_create(int (*fn)(void*),void *d,const char *name) {
 (void)fn;(void)d;(void)name;if(failure==4)return (void*)-ENOMEM;
 task.refs=1;task.running=0;return &task;
}
static void get_task_struct(struct task_struct *p) {
 if(p->refs<=0) {errors++;} p->refs++;gets++;
}
static void wake_up_process(struct task_struct *p) {
 wakes++;if(p->refs<2)errors++;p->running=1;
 /* Model autonomous return before init returns; worker drops its task ref. */
 if(fast) {p->running=0;p->refs--;}
}
static struct task_struct *kthread_run(int (*fn)(void*),void *d,const char *name) {
 struct task_struct *p=kthread_create(fn,d,name);if(!IS_ERR(p))wake_up_process(p);return p;
}
static void kthread_stop(struct task_struct *p) {
 if(p->refs<=0) {errors++;return;}
 joined++;if(p->running) {p->running=0;p->refs--;}
}
static void kthread_stop_put(struct task_struct *p) {
 kthread_stop(p);if(p->refs<=0)errors++;else p->refs--;
}
'''
        init = function(src, 'static int __init observer_init(')
        exit_code = function(src, 'static void __exit observer_exit(')
        code += init+'\n'+exit_code+'\n'
        # Negative control reproduces old unowned kthread_run + later stop.
        old_init = init.replace('observer_init(', 'old_init(').replace('kthread_create(observer_thread', 'kthread_run(observer_thread')
        old_init = old_init.replace('get_task_struct(observer_task);', '').replace('wake_up_process(observer_task);', '')
        old_exit = exit_code.replace('observer_exit(', 'old_exit(').replace('kthread_stop_put(observer_task)', 'kthread_stop(observer_task)')
        code += old_init+'\n'+old_exit+'\n'
        code += r'''
int lifecycle(int fail,int immediate,int old,int *result) {
 failure=fail;fast=immediate;errors=joined=removed=gets=wakes=0;
 task.refs=task.running=0;observer_root=NULL;observer_task=NULL;
 int ret=old?old_init():observer_init();
 int before=task.refs;if(!ret) {if(old)old_exit();else observer_exit();}
 result[0]=errors;result[1]=before;result[2]=task.refs;result[3]=joined;
 result[4]=removed;result[5]=gets;result[6]=wakes;result[7]=task.running;
 return ret;
}
'''
        cfile = Path(cls.tmp.name)/'lifetime.c';cfile.write_text(code)
        so = cfile.with_suffix('.so')
        compiled = subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',str(cfile),'-o',str(so)],capture_output=True)
        if compiled.returncode:
            raise RuntimeError(compiled.stderr.decode())
        cls.lib = ctypes.CDLL(str(so))
        cls.lib.lifecycle.argtypes = [ctypes.c_int]*3+[ctypes.POINTER(ctypes.c_int)]
        cls.lib.lifecycle.restype = ctypes.c_int

    def run_case(self, fail=0, immediate=0, old=0):
        result = (ctypes.c_int*8)()
        return self.lib.lifecycle(fail, immediate, old, result), list(result)

    def test_worker_returns_before_init_and_unload(self):
        rc, facts = self.run_case(immediate=1)
        self.assertEqual(rc, 0)
        self.assertEqual(facts, [0,1,0,1,1,1,1,0])

    def test_running_worker_join_releases_owned_reference(self):
        rc, facts = self.run_case()
        self.assertEqual(rc, 0)
        self.assertEqual(facts, [0,2,0,1,1,1,1,0])

    def test_create_failure_never_owns_or_stops_task(self):
        rc, facts = self.run_case(fail=4)
        self.assertEqual(rc, -errno.ENOMEM)
        self.assertEqual(facts, [0,0,0,0,1,0,0,0])

    def test_debugfs_failures_do_not_create_task_or_leak(self):
        for fail, expected_rc, removed in ((1,-errno.ENOMEM,0),(2,-errno.ENOMEM,0),(3,-errno.EINVAL,1)):
            rc, facts = self.run_case(fail=fail)
            self.assertEqual(rc, expected_rc)
            self.assertEqual(facts, [0,0,0,0,removed,0,0,0])

    def test_negative_control_old_code_detects_destroyed_task(self):
        rc, facts = self.run_case(immediate=1, old=1)
        self.assertEqual(rc, 0)
        self.assertGreater(facts[0], 0)
        self.assertEqual(facts[1], 0)
        self.assertEqual(facts[5], 0)


class ObserverBuilderTests(unittest.TestCase):
    def build_fixture(self, changed=False, separate_output=False):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / 'scripts').mkdir()
            shutil.copyfile(ROOT / 'scripts/build-sm5440-fresh-observer.sh', root / 'scripts/build-sm5440-fresh-observer.sh')
            src = root / 'kernel/diagnostics/sm5440-fresh-observer'
            src.mkdir(parents=True)
            for name in ('Makefile', 'sm5440-fresh-observer.c'):
                shutil.copyfile(ROOT / 'kernel/diagnostics/sm5440-fresh-observer' / name, src / name)
            driver = root / 'kernel/drivers';driver.mkdir()
            tree = root / '.work/build/linux-src-x710-charging/drivers/power/supply';tree.mkdir(parents=True)
            for name, content in (('sm5440-direct.c', b'provider'), ('sm5440-hw.h', b'header')):
                if changed and name.endswith('.h'):
                    content = b'changed ABI header'
                (driver / name).write_bytes(content);(tree / name).write_bytes(content)
            config = root / 'out/kernel-x710-272-passive/config';config.parent.mkdir(parents=True)
            config.write_bytes(b'CONFIG_MODULES=y\n')
            build = root / '.work/build/linux-out-x710-272-passive';build.mkdir()
            (build / '.config').write_bytes(config.read_bytes())
            (build / 'Module.symvers').write_text('0x123\tsm5440_passive_request_fresh\tvmlinux\tEXPORT_SYMBOL_GPL\n')
            manifest = root / 'reference/boot-tests/test-272-sm5440-fresh-request-offline/ARTIFACTS.json'
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({'config': {'path': str(config.relative_to(root)), 'sha256': hashlib.sha256(config.read_bytes()).hexdigest()}}))
            bin_dir = root / 'bin';bin_dir.mkdir()
            (bin_dir / 'git').write_text("#!/usr/bin/env python3\nimport sys\nname=sys.argv[-1].split(':')[-1].split('/')[-1]\nsys.stdout.buffer.write({'sm5440-direct.c':b'provider','sm5440-hw.h':b'header'}[name])\n")
            (bin_dir / 'make').write_text('#!/bin/sh\nfor arg in "$@"; do case "$arg" in M=*) target=${arg#M=};; esac; done\nprintf "mock module" > "$target/sm5440-fresh-observer.ko"\n')
            for name in ('git', 'make'):
                (bin_dir / name).chmod(0o755)
            env = dict(os.environ, PATH=str(bin_dir) + ':' + os.environ['PATH'])
            if separate_output:
                original = root/'out/sm5440-fresh-observer/sm5440-fresh-observer.ko'
                original.parent.mkdir(parents=True);original.write_bytes(b'original frozen module')
                env['OBSERVER_OUT_DIR'] = str(root/'out/revised-observer')
            result = subprocess.run(['bash', str(root / 'scripts/build-sm5440-fresh-observer.sh')], env=env, capture_output=True, timeout=10)
            artifact = root / ('out/revised-observer/sm5440-fresh-observer.ko' if separate_output else 'out/sm5440-fresh-observer/sm5440-fresh-observer.ko')
            if separate_output:
                self.assertEqual(original.read_bytes(), b'original frozen module')
            return result.returncode, result.stderr.decode(), artifact.exists()

    def test_matching_frozen_provider_builds_external_only(self):
        status, stderr, present = self.build_fixture()
        self.assertEqual(status, 0, stderr)
        self.assertTrue(present)

    def test_new_header_cannot_silently_pair_old_image_even_if_tree_matches(self):
        status, stderr, present = self.build_fixture(changed=True)
        self.assertNotEqual(status, 0)
        self.assertIn('source no longer matches sealed Test272 provider', stderr)
        self.assertFalse(present)

    def test_separate_output_keeps_original_frozen_module(self):
        status, stderr, present = self.build_fixture(separate_output=True)
        self.assertEqual(status, 0, stderr)
        self.assertTrue(present)


if __name__ == '__main__':
    unittest.main()
