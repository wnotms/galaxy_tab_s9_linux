"""Run the driver's startup functions with a scripted STM32 transport."""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_panel_x710 import function

ROOT = Path(__file__).resolve().parents[1]


class PogoStartup(unittest.TestCase):
    def test_boot_entry_clears_probe_before_commands(self):
        source = (ROOT / 'kernel/drivers/keyboard-samsung-pogo.c').read_text()
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
typedef uint8_t u8;
#define POGO_BOOT_CMD_SYNC 0xff
struct i2c_client { int unused; };
struct samsung_pogo { struct i2c_client *boot; int *nrst, *swclk; };
static int reset_pin, boot_pin, step, send_result = 1;
/* Samsung stm32_sysboot_connect: reset, probe, reset without another probe. */
static const int expected[] = {1, 2, 3, 4, 5, 6, 7, 1, 2, 3, 4, 5, 6};
static void record(int action) {
 assert(step < (int)(sizeof(expected) / sizeof(expected[0])));
 assert(action == expected[step++]);
}
static void gpiod_set_value_cansleep(int *pin, int v) {
 if (pin == &reset_pin) record(v ? 4 : 1);
 else { assert(pin == &boot_pin); record(v ? 2 : 6); }
}
static void msleep(int ms) { assert(ms == 3 || ms == 50); record(ms == 3 ? 3 : 5); }
static int i2c_master_send(struct i2c_client *c, const u8 *buf, int len) {
 assert(c && len == 1 && *buf == 0xff); record(7); return send_result;
}
'''
        for name in ('pogo_boot_reset', 'pogo_boot_enter'):
            definition = re.search(r'^static [^\n]*\b' + name + r'\([^;]*?\)\n\{',
                                   source, flags=re.M)
            self.assertIsNotNone(definition, name)
            harness += '\n' + function(source[definition.start():], name) + '\n'
        harness += r'''
int main(void) {
 struct i2c_client client = {0};
 struct samsung_pogo p = {.boot=&client, .nrst=&reset_pin, .swclk=&boot_pin};
 assert(pogo_boot_enter(&p) && step == 13);
 step=0; send_result=-6;
 assert(!pogo_boot_enter(&p) && step == 7);
 step=0; send_result=0;
 assert(!pogo_boot_enter(&p) && step == 7);
 step=0; p.boot=0;
 assert(!pogo_boot_enter(&p) && !step);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'entry.c'
            exe = Path(tmp) / 'entry'
            c.write_text(harness)
            subprocess.run(['clang', '-Wall', '-Wextra', '-Werror',
                            '-fsanitize=address,undefined', '-g', str(c),
                            '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_startup(self):
        source = (ROOT / 'kernel/drivers/keyboard-samsung-pogo.c').read_text()
        # The shared extractor expects definitions, not forward declarations.
        source = re.sub(r'^static [^\n]+;\n', '', source, flags=re.M)
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define POGO_BOOT_CMD_GET_VER 0x01
#define POGO_BOOT_CMD_GO 0x21
#define POGO_BOOT_RESP_ACK 0x79
#define POGO_CMD_CHECK_VERSION 2
#define POGO_CMD_GET_MODE 1
#define dev_info(...) ((void)0)
#define dev_info_ratelimited(...) ((void)0)
#define dev_err(...) ((void)0)
#define dev_dbg(...) ((void)0)
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
struct work_struct { int unused; };
struct delayed_work { struct work_struct work; };
#define to_delayed_work(w) container_of(w, struct delayed_work, work)
struct i2c_client { int irq, dev; };
struct samsung_pogo {
 struct i2c_client *client, *boot;
 int lock, *connected, *nrst, *swclk, *vdd, *scl, *sda;
 struct delayed_work connect_work;
 bool powered, ready, event_enabled;
};
static unsigned long jiffies, app_ready_at;
#define msecs_to_jiffies(ms) ((unsigned long)(ms))
#define jiffies_to_msecs(ticks) ((unsigned int)(ticks))
#define time_after_eq(a, b) ((long)((a) - (b)) >= 0)
static int startup_delay;
static int reset_gpio;
static int phase, transfers, fail_at, fail_value, bad_ack;
static int resets, entries, recoveries, app, app_after_go, app_after_reset;
static int enables, power_error, entry_failure, mode = 1;
static void mutex_lock(int *p) {}
static void mutex_unlock(int *p) {}
static void msleep(int n) {
 jiffies += n;
 if (app_ready_at && time_after_eq(jiffies, app_ready_at)) app = 1;
}
static int gpiod_get_value_cansleep(int *p) { return 1; }
static void gpiod_set_value_cansleep(int *p, int v) {
 if (p == &reset_gpio && !v) { resets++; app_ready_at=0; app = app_after_reset; }
}
static int regulator_enable(int *p) { return power_error; }
static void enable_irq(int irq) { enables++; }
static void pogo_recover_bus(struct samsung_pogo *p) { recoveries++; }
static void pogo_scan_bus(struct samsung_pogo *p) {}
static bool pogo_boot_enter(struct samsung_pogo *p) {
 entries++; phase = 0; return !entry_failure;
}
/* The bank lookup reads the firmware header; it has its own path and is mocked
   here so this harness keeps testing the GO/version/startup sequencing. */
static u32 pogo_boot_app_address(struct samsung_pogo *p) { return 0x08000000; }
static int pogo_read_reg(struct samsung_pogo *p, u8 reg, u8 *buf, int n) {
 if (!app) return -ENXIO;
 memset(buf, 0, n);
 if (reg == POGO_CMD_GET_MODE) { buf[0] = mode; }
 else { assert(n == 4); buf[1] = 2; buf[2] = 4; buf[3] = 1; }
 return 0;
}
static int i2c_master_send(struct i2c_client *c, const u8 *buf, int n) {
 if (++transfers == fail_at) return fail_value;
 if (phase == 0 && n == 2 && buf[0] == 1 && buf[1] == 0xfe) phase = 1;
 else if ((phase == 0 || phase == 4) && n == 2 && buf[0] == 0x21 && buf[1] == 0xde) phase = 5;
 else if (phase == 6 && n == 5) {
  static const u8 address[] = {8, 0, 0, 0, 8};
  assert(!memcmp(buf, address, 5)); phase = 7;
 } else assert(!"write before the preceding response completed");
 return n;
}
static int i2c_master_recv(struct i2c_client *c, u8 *buf, int n) {
 if (++transfers == fail_at) return fail_value;
 assert(n == 1);
 assert(phase == 1 || phase == 2 || phase == 3 || phase == 5 || phase == 7);
 *buf = phase == 2 ? 0x12 : (bad_ack == phase ? 0x1f : 0x79);
 if (phase == 7) {
  app = app_after_go;
  if (startup_delay) { app=0; app_ready_at=jiffies+startup_delay; }
 }
 phase++;
 return 1;
}
'''
        for name in ('pogo_boot_xfer', 'pogo_boot_version', 'pogo_boot_go', 'pogo_wait_application', 'pogo_bootloader_probe',
                     'pogo_read_mcu', 'pogo_connect_work'):
            definition = re.search(r'^static [^\n]*\b' + name + r'\([^;]*?\)\n\{',
                                   source, flags=re.M)
            self.assertIsNotNone(definition, name)
            harness += '\n' + function(source[definition.start():], name) + '\n'
        harness += r'''
static void clear(struct samsung_pogo *p) {
 jiffies = app_ready_at = startup_delay = 0;
 phase = transfers = fail_at = bad_ack = resets = entries = recoveries = 0;
 app = enables = power_error = entry_failure = 0;
 app_after_go = 1; app_after_reset = 0; mode = 1;
 p->powered = p->ready = p->event_enabled = false;
}
int main(void) {
 struct i2c_client client = {0}; int gpio;
 struct samsung_pogo p = {.client=&client, .boot=&client,
  .connected=&gpio, .nrst=&reset_gpio, .swclk=&gpio};
 u8 version;
 clear(&p);
 assert(!pogo_boot_version(&p, &version) && version == 0x12 && phase == 4);
 pogo_boot_go(&p, 0x08000000); assert(phase == 8 && app);
 /* Every short/error transfer must abort the version exchange. */
 for (int i=1; i<=4; i++) {
  clear(&p); fail_at=i; fail_value=0;
  assert(pogo_boot_version(&p,&version) == -EIO && transfers == i);
  clear(&p); fail_at=i; fail_value=-ETIMEDOUT;
  assert(pogo_boot_version(&p,&version) == -ETIMEDOUT && transfers == i);
 }
 for (int i=1; i<=3; i+=2) {
  clear(&p); bad_ack=i;
  assert(pogo_boot_version(&p,&version) == -EPROTO);
 }
 /* GO must stop on every failed transfer and either rejected ACK. */
 for (int i=1; i<=4; i++) {
  clear(&p); fail_at=i; fail_value=-ENXIO;
  pogo_boot_go(&p, 0x08000000); assert(transfers == i && !app);
 }
 clear(&p); bad_ack=5; pogo_boot_go(&p, 0x08000000); assert(transfers == 2 && !app);
 clear(&p); bad_ack=7; app_after_go=0;
 pogo_boot_go(&p, 0x08000000); assert(transfers == 4 && !app);
 /* Both startup success paths must set ready without resetting the app. */
 clear(&p); app=1;
 pogo_connect_work(&p.connect_work.work);
 assert(p.ready && p.event_enabled && enables == 1 && !resets && !entries && !recoveries);
 pogo_connect_work(&p.connect_work.work); assert(enables == 1 && !resets);
 clear(&p);
 pogo_connect_work(&p.connect_work.work);
 assert(p.ready && p.event_enabled && entries == 1 && !resets && !recoveries && phase == 8);
 /* An application needing two seconds must not be reset at 150 ms. */
 clear(&p); startup_delay=2000;
 pogo_connect_work(&p.connect_work.work);
 assert(p.ready && !resets && !recoveries && jiffies >= 2000 && jiffies < 2200);
 /* Absence is bounded, and polling itself never manipulates reset or bus. */
 clear(&p);
 assert(pogo_wait_application(&p, "test") == -ENXIO);
 assert(jiffies >= 5000 && jiffies <= 5150 && !resets && !recoveries);
 /* The deadline arithmetic must work across a jiffies wrap. */
 clear(&p); jiffies=(unsigned long)-1000;
 assert(pogo_wait_application(&p, "wrap") == -ENXIO && jiffies < 4200);
 /* A failed version exchange requires a fresh session before GO. */
 clear(&p); bad_ack=3;
 pogo_bootloader_probe(&p); assert(entries == 2 && app && !resets);
 clear(&p); fail_at=4; fail_value=-ETIMEDOUT;
 pogo_bootloader_probe(&p); assert(entries == 2 && app && !resets);
 /* Failed GO permits the vendor reset fallback; success survives the caller. */
 clear(&p); app_after_go=0; app_after_reset=1;
 pogo_connect_work(&p.connect_work.work);
 assert(p.ready && resets == 1 && !recoveries);
 clear(&p); entry_failure=1;
 pogo_bootloader_probe(&p); assert(!transfers && !app);
 clear(&p); power_error=-EIO;
 pogo_connect_work(&p.connect_work.work); assert(!p.powered && !enables && !entries);
 clear(&p); app=1; mode=0;
 pogo_connect_work(&p.connect_work.work); assert(!p.ready && !resets);
 clear(&p); app_after_go=0; p.ready=true;
 assert(pogo_read_mcu(&p) == -ENXIO && !p.ready && recoveries == 1);
 return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'startup.c'
            exe = Path(tmp) / 'startup'
            c.write_text(harness)
            subprocess.run(['clang', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', '-Wno-unused-but-set-variable',
                            '-Wno-sign-compare', '-fsanitize=address,undefined',
                            '-g', str(c), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
