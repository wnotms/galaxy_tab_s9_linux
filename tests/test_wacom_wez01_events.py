"""Execute the imported WEZ01 C IRQ/query/timer paths with host I/O stubs.

Models timer deletion versus permanent shutdown; does not simulate kernel
scheduling or qualify real I2C, calibration, palm rejection, PM or hot-unbind.
"""
import ctypes
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / 'kernel/desktop/wacom-wez01'


def function(source, name):
    match = re.search(r'^(?:static )?[^\n;]+\b' + re.escape(name) + r'\([^;]*?\)\n\{', source, re.M)
    if match is None:
        raise ValueError(name)
    end = source.index('{', match.start()) + 1
    depth = 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


class PenEvents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.folder.cleanup)
        folder = Path(cls.folder.name)
        source = (DRIVER / 'wacom-wez01.c').read_text()
        prelude = r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8; typedef uint16_t u16; typedef int8_t s8;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define BIT(n) (1U << (n))
#define BTN_TOOL_PEN 0
#define BTN_TOOL_RUBBER 1
#define BTN_TOUCH 2
#define BTN_STYLUS 3
#define ABS_X 4
#define ABS_Y 5
#define ABS_PRESSURE 6
#define ABS_DISTANCE 7
#define ABS_TILT_X 8
#define ABS_TILT_Y 9
#define clamp(v,lo,hi) ((v)<(lo)?(lo):((v)>(hi)?(hi):(v)))
#define dev_warn(...) ((void)0)
#define dev_info(...) ((void)0)
#define dev_dbg(...) ((void)0)
struct input_dev { int unused; };
struct gpio_desc { int unused; };
struct device { void *data; };
struct i2c_client { struct device dev; int irq; };
struct timer_list { bool pending, shutdown; };
#define timer_container_of(var,ptr,field) ((struct wacom_wez01 *)((char *)(ptr)-offsetof(struct wacom_wez01,field)))
typedef int atomic_t;
#define ATOMIC_INIT(n) (n)
static int atomic_read(atomic_t *a) { return *a; }
static void atomic_set(atomic_t *a, int n) { *a=n; }
static int atomic_cmpxchg(atomic_t *a,int old,int val) { int prior=*a;if(prior==old)*a=val;return prior; }
static int vals[10],syncs,read_ret,send_ret,read_calls,sleeps,irq_enabled;
static u8 bytes[32],commands[16]; static int ncommands;
static unsigned long jiffies;
static u16 get_unaligned_be16(const u8 *p) { return ((u16)p[0]<<8)|p[1]; }
static void input_report_key(struct input_dev *d,int code,int value) { (void)d; vals[code]=value; }
static void input_report_abs(struct input_dev *d,int code,int value) { (void)d; vals[code]=value; }
static void input_sync(struct input_dev *d) { (void)d; syncs++; }
static void timer_delete_sync(struct timer_list *t) { t->pending=false; }
static void timer_shutdown_sync(struct timer_list *t) { t->pending=false;t->shutdown=true; }
static void mod_timer(struct timer_list *t,unsigned long expiry) { (void)expiry;if(!t->shutdown)t->pending=true; }
static unsigned long msecs_to_jiffies(unsigned int ms) { return ms; }
static int i2c_master_recv(struct i2c_client *c,u8 *p,int len) { (void)c;read_calls++;memcpy(p,bytes,len);return read_ret; }
static int i2c_master_send(struct i2c_client *c,const u8 *p,int len) { (void)c;(void)len;if(ncommands<16)commands[ncommands++]=p[0];return send_ret; }
static void msleep(unsigned int ms) { (void)ms;sleeps++; }
static void disable_irq(int irq) { (void)irq;irq_enabled=0; }
static void enable_irq(int irq) { (void)irq;irq_enabled=1; }
static void *dev_get_drvdata(struct device *dev) { return dev->data; }
static int pen_x_min=0,pen_x_max=23575,pen_y_min=0,pen_y_max=14724;
'''
        defines = '\n'.join(re.findall(r'^#define WEZ01_.*$', source, re.M))
        state = re.search(r'struct wacom_wez01 \{.*?\n\};', source, re.S).group()
        globals_ = '\n'.join(re.findall(r'^static atomic_t .*?;$', source, re.M))
        names = ('wacom_wez01_should_suppress_touch', 'wacom_wez01_send', 'wacom_wez01_query',
                 'wacom_wez01_leave_range', 'wacom_wez01_prox_timeout', 'wacom_wez01_irq_handler',
                 'wacom_wez01_stop_timer', 'wacom_wez01_suspend', 'wacom_wez01_resume')
        wrappers = r'''
static struct input_dev input; static struct i2c_client client; static struct wacom_wez01 w;
void reset(void) {
 memset(&w,0,sizeof(w)); memset(vals,0,sizeof(vals)); memset(bytes,0,sizeof(bytes));
 syncs=read_calls=sleeps=ncommands=0;read_ret=17;send_ret=1;irq_enabled=1;
 wez01_pen_proximity=0;wez01_touch_suppression=1;
 w.client=&client;w.input=&input;w.max_x=14752;w.max_y=23603;client.dev.data=&w;
}
void feed(const u8 *p,int ret) { memcpy(bytes,p,17);read_ret=ret;wacom_wez01_irq_handler(1,&w); }
void status(int *out) {
 memcpy(out,vals,sizeof(vals));out[10]=syncs;out[11]=w.prox;
 out[12]=w.prox_timer.pending;out[13]=w.prox_timer.shutdown;
 out[14]=wacom_wez01_should_suppress_touch();out[15]=irq_enabled;
}
void timeout(void) { if(w.prox_timer.pending){w.prox_timer.pending=false;wacom_wez01_prox_timeout(&w.prox_timer);} }
void teardown(void) { wacom_wez01_stop_timer(&w); }
int suspend(void) { return wacom_wez01_suspend(&client.dev); }
int resume(void) { return wacom_wez01_resume(&client.dev); }
int query(const u8 *p,int ret,int *out) {
 memcpy(bytes,p,32);read_ret=ret;int result=wacom_wez01_query(&w);
 out[0]=w.max_x;out[1]=w.max_y;out[2]=w.max_pressure;out[3]=w.max_height;
 out[4]=w.max_tilt_x;out[5]=w.max_tilt_y;out[6]=read_calls;out[7]=sleeps;return result;
}
int send(u8 cmd,int ret) { send_ret=ret;return wacom_wez01_send(&w,cmd); }
int last_command(void) { return ncommands?commands[ncommands-1]:-1; }
'''
        unit = folder / 'events.c'
        unit.write_text(prelude + defines + '\n' + state + '\n' + globals_ + '\n' +
                        '\n'.join(function(source, n) for n in names) + '\n' + wrappers)
        built = subprocess.run(['cc','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
                        '-Wno-sign-compare','-Wno-unused-parameter',str(unit),'-o',str(folder/'events.so')],
                       capture_output=True,text=True)
        if built.returncode:
            raise RuntimeError(built.stderr)
        cls.lib = ctypes.CDLL(str(folder/'events.so'))
        cls.lib.feed.argtypes = [ctypes.POINTER(ctypes.c_ubyte),ctypes.c_int]
        cls.lib.status.argtypes = [ctypes.POINTER(ctypes.c_int)]
        cls.lib.query.argtypes = [ctypes.POINTER(ctypes.c_ubyte),ctypes.c_int,ctypes.POINTER(ctypes.c_int)]
        cls.lib.send.argtypes = [ctypes.c_ubyte,ctypes.c_int]

    def setUp(self):
        self.lib.reset()

    def frame(self, flags=0x80, x=1000, y=2000, pressure=1234, distance=12, tilt=(-5,6)):
        data = bytearray(17);data[0]=1|flags
        data[1:5]=x.to_bytes(2,'big')+y.to_bytes(2,'big')
        data[5:7]=pressure.to_bytes(2,'big');data[7]=distance
        data[8:10]=bytes(t&255 for t in tilt)
        return data

    def feed(self, data=None, ret=17):
        self.lib.feed((ctypes.c_ubyte*17).from_buffer_copy(self.frame() if data is None else data),ret)
        return self.status()

    def status(self):
        out=(ctypes.c_int*16)();self.lib.status(out);return list(out)

    def test_manifest_binds_optional_source_and_original_header(self):
        manifest=json.loads((DRIVER/'SOURCE.json').read_text())
        for name,row in manifest['files'].items():
            self.assertEqual(hashlib.sha256((DRIVER/name).read_bytes()).hexdigest(),row['imported_sha256'])
        header=manifest['files']['include/linux/wacom_wez01.h']
        self.assertEqual(header['imported_sha256'],header['upstream_sha256'])
        self.assertFalse(manifest['default_kernel_integration'])

    def test_paired_touch_build_is_opt_in_and_imports_wacom_helper(self):
        makefile = (DRIVER.parent / 'fts1ba90a' / 'Makefile.palm').read_text()
        self.assertIn('CONFIG_TOUCHSCREEN_WACOM_WEZ01_MODULE=1', makefile)
        self.assertNotIn('CONFIG_TOUCHSCREEN_WACOM_WEZ01_MODULE=1',
                         (DRIVER.parent / 'fts1ba90a' / 'Makefile').read_text())
        versions = (ROOT / 'reference/desktop-bringup/wacom-wez01-offline/palm-touch-module-versions.txt').read_text()
        self.assertIn('wacom_wez01_should_suppress_touch', versions)
        self.assertIn('module_layout', versions)

    def test_pen_hover_big_endian_swap_inversion_and_signed_tilt(self):
        v=self.feed();self.assertEqual(v[:10],[1,0,0,0,2000,13752,1234,12,-5,6])
        self.assertEqual(v[10:15],[1,1,1,0,1])

    def test_tip_side_button_and_eraser(self):
        self.assertEqual(self.feed(self.frame(flags=0xf0))[:4],[0,1,1,1])
        self.assertEqual(self.feed(self.frame(flags=0x90))[:4],[1,0,1,0])

    def test_coordinates_clamp_to_fedora_calibration(self):
        v=self.feed(self.frame(x=65535,y=65535,pressure=4095))
        self.assertEqual(v[4:7],[23575,0,4095])

    def test_pressure_masks_non_pressure_high_nibble(self):
        self.assertEqual(self.feed(self.frame(pressure=0xfabc))[6],0xabc)

    def test_out_of_range_releases_all_tools_once(self):
        self.feed(self.frame(flags=0xf0));v=self.feed(self.frame(flags=0))
        self.assertEqual(v[:4],[0,0,0,0]);self.assertEqual(v[6:8],[0,0])
        self.assertEqual(v[10:15],[2,0,0,0,0]);self.feed(self.frame(flags=0))
        self.assertEqual(self.status()[10],2)

    def test_reenter_after_range_out_rearms_silence_timer(self):
        self.feed();self.feed(self.frame(flags=0));self.feed();self.lib.timeout()
        self.assertEqual(self.status()[11:15],[0,0,0,0])
        self.assertEqual(self.status()[10],4)

    def test_silence_timeout_releases_then_next_report_rearms(self):
        self.feed();self.lib.timeout();self.assertEqual(self.status()[14],0)
        self.feed();self.assertEqual(self.status()[12:15],[1,0,1])

    def test_short_i2c_read_error_and_non_coordinate_do_not_publish(self):
        self.feed();before=self.status()
        for ret in (0,16,-5):self.assertEqual(self.feed(ret=ret),before)
        d=self.frame();d[0]=(d[0]&0xf0)|2;self.assertEqual(self.feed(d),before)
        self.lib.timeout();self.assertEqual(self.status()[14],0)

    def test_suspend_releases_and_resume_allows_timer_rearm(self):
        self.feed();self.assertEqual(self.lib.suspend(),0)
        self.assertEqual(self.status()[11:16],[0,0,0,0,0]);self.assertEqual(self.lib.last_command(),0x30)
        self.assertEqual(self.lib.resume(),0);self.assertEqual(self.lib.last_command(),0x31)
        self.assertEqual(self.status()[15],1);self.feed();self.lib.timeout()
        self.assertEqual(self.status()[14],0)

    def test_final_cleanup_permanently_prevents_timer_rearm(self):
        self.feed();self.lib.teardown();self.assertEqual(self.status()[11:15],[0,0,1,0])

    def test_send_propagates_errors_and_short_writes(self):
        self.assertEqual(self.lib.send(0x31,1),0)
        self.assertEqual(self.lib.send(0x31,0),-5)
        self.assertEqual(self.lib.send(0x31,-121),-121)

    def test_query_block_offset_big_endian_and_limits(self):
        data=bytearray(32);data[16]=15
        data[17:23]=(14752).to_bytes(2,'big')+(23603).to_bytes(2,'big')+(4095).to_bytes(2,'big')
        data[25]=0x46;data[27:30]=bytes((63,62,255))
        out=(ctypes.c_int*8)();self.assertEqual(self.lib.query((ctypes.c_ubyte*32).from_buffer_copy(data),32,out),0)
        self.assertEqual(list(out),[14752,23603,4095,255,63,62,1,0])

    def test_query_short_read_bad_header_and_bus_error_are_bounded(self):
        for ret in (31,32,-121):
            self.lib.reset();out=(ctypes.c_int*8)()
            actual=self.lib.query((ctypes.c_ubyte*32)(),ret,out)
            self.assertEqual(actual,-121 if ret<0 else -5);self.assertEqual(list(out)[6:],[10,10])

    def test_devres_unregister_is_after_irq_and_timer_cleanup(self):
        # Linux input_register_device adds its own unregister devres action.
        # This order is not safely covered by packet mocks; guard it explicitly.
        body=function((DRIVER/'wacom-wez01.c').read_text(),'wacom_wez01_probe')
        names=['input_register_device(input)','devm_add_action_or_reset(dev, wacom_wez01_stop_timer','devm_request_threaded_irq']
        positions=[body.index(n) for n in names];self.assertEqual(positions,sorted(positions))
        self.assertIn('ret = wacom_wez01_send(w, WEZ01_COM_SAMPLERATE_START);',body)
        self.assertIn('failed to start pen reports',body)


if __name__ == '__main__':
    unittest.main()
