"""Execute patched Debian adbd methods against real threads and owned fds."""
import os
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'userspace/adbd/source-baseline'


def function(source, signature):
    start = source.index(signature)
    brace = source.index('{', start)
    depth = 1
    end = brace + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[start:end]


WORKER = r'''
#include <atomic>
#include <cassert>
#include <chrono>
#include <csignal>
#include <cstring>
#include <iostream>
#include <mutex>
#include <thread>
#include <pthread.h>
#include <sys/eventfd.h>
#include <unistd.h>
#include <android-base/scopeguard.h>
using namespace std::chrono_literals;
#define LOG(x) std::cerr
#define PLOG(x) std::cerr
#define CHECK(x) assert(x)
void adb_thread_setname(const char*) {}
ssize_t adb_read(int fd, void* buf, size_t n) { return read(fd, buf, n); }
struct Fd { int n; int get() { return n; } };
struct Worker {
    bool worker_started_ = false, submit_ok = true;
    std::atomic<bool> stopped_{false}, worker_finished_{false};
    std::thread worker_thread_;
    Fd worker_event_fd_{eventfd(0, EFD_CLOEXEC)};
    std::mutex write_mutex_;
    int read_requests_[1], next_read_id_ = 0, stop_calls = 0;
    static constexpr int kUsbReadQueueDepth = 1, kInterruptionSignal = SIGUSR1;
    int CreateReadBlock(int) { return 0; }
    bool SubmitRead(int*) { return submit_ok; }
    void ReadEvents() {}
    void SubmitWrites() {}
    void Stop() {
        ++stop_calls; stopped_ = true;
        uint64_t value = 1; assert(write(worker_event_fd_.get(), &value, 8) == 8);
    }
    START_WORKER
    STOP_WORKER
    ~Worker() { close(worker_event_fd_.get()); }
};
int main(int argc, char** argv) {
    signal(SIGUSR1, [](int) {});
    Worker w; std::string mode(argv[1]);
    if (mode == "not-started") { w.StopWorker(); assert(w.stop_calls == 0); return 0; }
    if (mode == "original" || mode == "probe") {
        w.worker_started_ = true;
        w.worker_thread_ = std::thread([] {});
        std::this_thread::sleep_for(30ms);
        if (mode == "probe") {
            std::cout << pthread_kill(w.worker_thread_.native_handle(), 0) << '\n';
            w.worker_thread_.join(); return 0;
        }
        w.StopWorker(); return 0;
    }
    w.submit_ok = mode != "early-return";
    w.StartWorker();
    std::this_thread::sleep_for(20ms);
    w.StopWorker();
    assert(w.worker_finished_ && !w.worker_thread_.joinable());
    assert(w.stop_calls == 1);
}
'''

BOUND = r'''
#include <atomic>
#include <cassert>
#include <iostream>
#define LOG(x) std::cerr
enum { FUNCTIONFS_BIND, FUNCTIONFS_ENABLE, FUNCTIONFS_UNBIND };
struct Monitor {
    std::atomic<bool>* function_bound_;
    bool enabled = false, running = true;
    int started = 0;
    void StartWorker() { ++started; }
    void event(int type) {
        BOUND_INIT
        switch (type) { BOUND_CASES }
    }
};
int main(int argc, char** argv) {
    std::atomic<bool> bound(false);
    Monitor first{&bound}; std::string mode(argv[1]);
    if (mode == "initial-enable") {
        first.event(FUNCTIONFS_ENABLE); assert(!first.running && first.started == 0); return 0;
    }
    first.event(FUNCTIONFS_BIND); assert(bound);
    Monitor reconnect{&bound}; reconnect.event(FUNCTIONFS_ENABLE);
    assert(reconnect.running && reconnect.started == 1);
    if (mode == "duplicate-enable") {
        reconnect.event(FUNCTIONFS_ENABLE); assert(!reconnect.running && reconnect.started == 1);
    } else if (mode == "unbind") {
        reconnect.event(FUNCTIONFS_UNBIND); assert(!bound);
        Monitor next{&bound}; next.event(FUNCTIONFS_ENABLE);
        assert(!next.running && next.started == 0);
    }
}
'''

FFS = r'''
#include <cassert>
#include <cstdint>
#include <cstring>
#include <endian.h>
#include <fcntl.h>
#include <iostream>
#include <map>
#include <string>
#include <unistd.h>
#include <linux/usb/ch9.h>
#include <linux/usb/functionfs.h>
#define LOG(x) std::cerr
#define PLOG(x) std::cerr
#define D(...) ((void)0)
#define USB_FFS_ADB_EP0 "ep0"
#define USB_FFS_ADB_OUT "ep1"
#define USB_FFS_ADB_IN "ep2"
#define ADB_CLASS 0xff
#define ADB_SUBCLASS 0x42
#define ADB_PROTOCOL 0x01
int writes = 0, control_refs = 0, last_closes = 0;
bool fail_bulk = false, fail_dup = false;
std::map<int,bool> fds;
int adb_open(const char* name, int flags) {
    bool ep0 = std::string(name) == "ep0";
    if (!ep0 && fail_bulk) return -1;
    int fd = open("/dev/null", flags); assert(fd >= 0); fds[fd] = ep0;
    if (ep0) ++control_refs; return fd;
}
int simulated_fcntl(int fd, int operation, int flags) {
    assert(operation == F_DUPFD_CLOEXEC && flags == 0);
    if (fail_dup) return -1;
    int copy = fcntl(fd, operation, flags); assert(copy >= 0); fds[copy] = fds.at(fd);
    if (fds[copy]) ++control_refs; return copy;
}
void adb_close(int fd) {
    if (fds.at(fd) && --control_refs == 0) ++last_closes;
    fds.erase(fd); close(fd);
}
ssize_t adb_write(int fd, const void*, size_t n) { assert(fds.at(fd)); ++writes; return n; }
namespace android::base {
class unique_fd {
    int fd_ = -1;
 public:
    unique_fd() = default;
    explicit unique_fd(int fd): fd_(fd) {}
    ~unique_fd() { reset(); }
    unique_fd(unique_fd&& other): fd_(other.fd_) { other.fd_ = -1; }
    unique_fd& operator=(unique_fd&& other) {
        reset(other.fd_); other.fd_ = -1; return *this;
    }
    void reset(int fd = -1) { if (fd_ >= 0) adb_close(fd_); fd_ = fd; }
    int get() const { return fd_; }
    operator int() const { return fd_; }
};
bool SetProperty(const char*, const char*) { return true; }
}
using android::base::unique_fd;
#define fcntl simulated_fcntl
FFS_SOURCE
int main(int argc, char** argv) {
    unique_fd control, out, in;
    assert(open_functionfs(&control, &out, &in)); assert(writes == 2);
    std::string mode(argv[1]);
    if (mode == "bulk-failure") fail_bulk = true;
    if (mode == "dup-failure") fail_dup = true;
    bool ok = open_functionfs(&control, &out, &in);
    assert(ok == (mode == "reconnect"));
    assert(control.get() >= 0 && control_refs == 1 && last_closes == 0 && writes == 2);
}
'''


class AdbdReconnectTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for name, expected in json.loads((BASE/'SHA256.json').read_text()).items():
            actual = hashlib.sha256((BASE/name).read_bytes()).hexdigest()
            if actual != expected:
                raise RuntimeError('source baseline checksum mismatch: ' + name)
        cls.temp = tempfile.TemporaryDirectory()
        cls.path = Path(cls.temp.name)
        src = cls.path / 'packages/modules/adb/daemon'
        src.mkdir(parents=True)
        for name in ('usb.cpp', 'usb_ffs.cpp'):
            shutil.copyfile(BASE / name, src / name)
        subprocess.run(['patch', '-p1', '-i', str(ROOT / 'userspace/adbd/0001-linux-functionfs-reconnect.patch')],
                       cwd=cls.path, check=True, capture_output=True)
        usb = (src / 'usb.cpp').read_text()
        def compile(name, code):
            file = cls.path / (name + '.cpp'); file.write_text(code)
            result = subprocess.run(['clang++', '-std=c++20', '-Wno-c++11-narrowing', '-pthread', '-I' + str(BASE),
                                     str(file), '-o', str(cls.path / name)], capture_output=True, text=True)
            if result.returncode:
                raise RuntimeError(result.stderr)
        start = function(usb, 'void StartWorker()')
        compile('worker', WORKER.replace('START_WORKER', start).replace('STOP_WORKER', function(usb, 'void StopWorker()')))
        compile('original', WORKER.replace('START_WORKER', start).replace('STOP_WORKER', function((BASE/'usb.cpp').read_text(), 'void StopWorker()')))
        monitor = function(usb, 'void StartMonitor()')
        cases = ''
        for begin, end in [('FUNCTIONFS_BIND', 'FUNCTIONFS_ENABLE'), ('FUNCTIONFS_ENABLE', 'FUNCTIONFS_DISABLE'),
                           ('FUNCTIONFS_UNBIND', 'FUNCTIONFS_SETUP')]:
            cases += 'case ' + begin + ':' + monitor.split('case ' + begin + ':', 1)[1].split('case ' + end + ':', 1)[0]
        init = next(line.strip() for line in usb.splitlines() if 'bool bound =' in line)
        compile('bound', BOUND.replace('BOUND_INIT', init).replace('BOUND_CASES', cases))
        ffs = (src / 'usb_ffs.cpp').read_text()
        compile('ffs', FFS.replace('FFS_SOURCE', ffs[ffs.index('#define MAX_PACKET_SIZE_FS'):]))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def run_case(self, binary, case):
        result = subprocess.run([str(self.path / binary), case], capture_output=True, text=True, timeout=3)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_original_glibc_cleanup_reproduces_wait(self):
        probe = subprocess.check_output([str(self.path/'original'), 'probe'], text=True).strip()
        if probe == '0':
            with self.assertRaises(subprocess.TimeoutExpired):
                subprocess.run([str(self.path/'original'), 'original'], timeout=.6, capture_output=True)
        else:
            self.run_case('original', 'original')

    def test_stop_without_started_worker(self): self.run_case('worker', 'not-started')
    def test_active_worker_wakes_and_joins(self): self.run_case('worker', 'active')
    def test_initial_read_failure_signals_completion(self): self.run_case('worker', 'early-return')
    def test_remembered_bind_accepts_reconnect_enable(self): self.run_case('bound', 'reconnect')
    def test_initial_enable_requires_real_bind(self): self.run_case('bound', 'initial-enable')
    def test_unbind_clears_remembered_bind(self): self.run_case('bound', 'unbind')
    def test_duplicate_enable_still_rejected(self): self.run_case('bound', 'duplicate-enable')
    def test_reconnect_retains_ep0_without_descriptor_writes(self): self.run_case('ffs', 'reconnect')
    def test_bulk_open_failure_keeps_existing_ep0(self): self.run_case('ffs', 'bulk-failure')
    def test_dup_failure_keeps_existing_ep0(self): self.run_case('ffs', 'dup-failure')

    def test_launcher_prefers_fix_and_keeps_args(self):
        self.launcher_case(True)

    def test_launcher_missing_fix_uses_package(self):
        self.launcher_case(False)

    def launcher_case(self, fixed):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ('fixed', 'package'):
                f = root/name
                f.write_text('#!/bin/sh\nprintf "%s\\n" "' + name + ':$*"\n')
                f.chmod(0o755)
            if not fixed: (root/'fixed').unlink()
            result = subprocess.run(['sh', str(ROOT/'rootfs-overlay/usr/libexec/gts9-adbd-run'), '--version'],
                env=dict(os.environ, GTS9_ADBD_RECONNECT_BINARY=str(root/'fixed'),
                         GTS9_ADBD_PACKAGED_BINARY=str(root/'package')), capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout.strip(), ('fixed' if fixed else 'package') + ':--version')
