"""Drive the real pogo suspend/resume paths against a scripted cover and rail.

The point of these cases is the lifecycle split itself: suspend must be a
recoverable stop that keeps the sysfs attribute, the work structs and the
requested IRQs, and resume must put the driver back into the state the connect
line actually describes without resetting a keyboard that is still running.

The IRQ and regulator mocks are deliberately strict - enabling an already
enabled line, disabling a disabled one, or disabling a regulator that was never
enabled aborts the harness.  That is how "no unbalanced enable_irq()" is checked
here rather than asserted by inspection.
"""
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
from test_panel_x710 import function

ROOT = Path(__file__).resolve().parents[1]

# Extracted in file order; pogo_release_keys is mocked because key delivery is
# covered by the packet test.
FUNCTIONS = (
    'pogo_power_on', 'pogo_power_off',
    'pogo_connect_irq_enable', 'pogo_connect_irq_disable',
    'pogo_detach', 'pogo_hot_connect', 'pogo_conn_check_work',
    'pogo_remove', 'pogo_suspend', 'pogo_resume',
)

HARNESS_HEAD = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
typedef uint8_t u8;
#define POGO_WATCH_MS 5000
#define CONNECT_IRQ 1
#define DATA_IRQ 2
#define NIRQ 8
struct device_attribute { int unused; };
static struct device_attribute dev_attr_rearm;
struct i2c_client { int irq, dev; };
struct device { int unused; };
struct work_struct { int unused; };
struct delayed_work { struct work_struct work; };
#define container_of(ptr, type, member) ((type *)((char *)(ptr) - offsetof(type, member)))
#define to_delayed_work(w) container_of(w, struct delayed_work, work)
struct samsung_pogo {
 struct i2c_client *client;
 struct delayed_work connect_work, watch_work, conn_check_work, hello_work;
 int lock;
 int *connected, *vdd;
 bool powered, event_enabled, ready, irq_armed, conn_irq_armed;
 bool connect_state;
 int connect_irq;
};
static void dev_note(const void *dev, const char *fmt, ...)
{ (void)dev; (void)fmt; }
#define dev_info(dev, fmt, ...) dev_note(dev, fmt, ##__VA_ARGS__)
#define dev_warn(dev, fmt, ...) dev_note(dev, fmt, ##__VA_ARGS__)
#define dev_err(dev, fmt, ...) dev_note(dev, fmt, ##__VA_ARGS__)
#define system_percpu_wq ((void *)0)
#define msecs_to_jiffies(ms) ((unsigned long)(ms))
static int lock_held, power_error, sleeps, queued, cancelled, removes, releases;
static int reg_count, rail_gpio_writes, bus_transfers;
static int irq_enabled[NIRQ], irq_enables[NIRQ], irq_disables[NIRQ];
static void mutex_lock(int *p) { (void)p; assert(!lock_held); lock_held = 1; }
static void mutex_unlock(int *p) { (void)p; assert(lock_held); lock_held = 0; }
static void msleep(int n) { assert(n >= 0); sleeps++; }
static void queue_delayed_work(void *wq, struct delayed_work *w, unsigned long d)
{ (void)wq; (void)w; (void)d; queued++; }
static void cancel_delayed_work_sync(struct delayed_work *w) { (void)w; cancelled++; }
static void device_remove_file(const void *d, struct device_attribute *a)
{ (void)d; (void)a; removes++; }
static void pogo_release_keys(struct samsung_pogo *p) { (void)p; releases++; }
/* Strict: the kernel warns on an unbalanced enable/disable, so abort here. */
static void enable_irq(int irq)
{ assert(irq >= 0 && irq < NIRQ); assert(!irq_enabled[irq]);
  irq_enabled[irq] = 1; irq_enables[irq]++; }
static void disable_irq(int irq)
{ assert(irq >= 0 && irq < NIRQ); assert(irq_enabled[irq]);
  irq_enabled[irq] = 0; irq_disables[irq]++; }
static void disable_irq_nosync(int irq) { disable_irq(irq); }
/* The rail is counted, so an enable without its disable cannot hide. */
static int regulator_enable(int *r)
{ (void)r; if (power_error) return power_error; reg_count++; return 0; }
static int regulator_disable(int *r)
{ (void)r; assert(reg_count > 0); reg_count--; return 0; }
static int cover_level = 1;
static int gpiod_get_value_cansleep(int *g) { (void)g; return cover_level; }
/* Any NRST pulse or BOOT0 write in suspend/resume would show up here. */
static void gpiod_set_value_cansleep(int *g, int v) { (void)g; (void)v; rail_gpio_writes++; }
/* Any bus traffic - in particular a 0x51 diagnostic - would show up here. */
static int i2c_master_send(struct i2c_client *c, const u8 *b, int n)
{ (void)c; (void)b; (void)n; bus_transfers++; return n; }
static int i2c_master_recv(struct i2c_client *c, u8 *b, int n)
{ (void)c; (void)b; (void)n; bus_transfers++; return n; }
static struct samsung_pogo *the_pogo;
static struct i2c_client *to_i2c_client(struct device *d) { (void)d; return NULL; }
static void *i2c_get_clientdata(struct i2c_client *c) { (void)c; return the_pogo; }
'''

MAIN = r'''
static struct samsung_pogo p;
static struct i2c_client client;
static struct device dev;
static int vdd, cover;

/* Snapshot so each case asserts the change it caused, not a running total. */
static int s_releases, s_sleeps, s_removes, s_queued, s_cancelled, s_reg;
#define SINCE(f) (f - s_##f)
/* pogo_detach() clears the key state itself and pogo_power_off() clears it
   again, so a detach is two release calls.  Harmless - the second finds nothing
   set - but it is what the driver does, so the count is asserted as it is. */
#define DETACH_RELEASES 2

static void snap(void)
{
 s_releases = releases; s_sleeps = sleeps; s_removes = removes;
 s_queued = queued; s_cancelled = cancelled; s_reg = reg_count;
}

static void clear_counts(void)
{
 int i;
 lock_held = power_error = sleeps = queued = cancelled = 0;
 removes = releases = reg_count = rail_gpio_writes = bus_transfers = 0;
 for (i = 0; i < NIRQ; i++) { irq_enabled[i] = irq_enables[i] = irq_disables[i] = 0; }
}

/* The state after a normal cold bring-up with a cover on: the rail is up and
   both lines are enabled, so preset the model to match. */
static void bring_up_attached(void)
{
 clear_counts();
 p.powered = true; p.ready = true; p.event_enabled = true;
 p.irq_armed = true; p.conn_irq_armed = true; p.connect_state = true;
 reg_count = 1;
 irq_enabled[CONNECT_IRQ] = irq_enables[CONNECT_IRQ] = 1;
 irq_enabled[DATA_IRQ] = irq_enables[DATA_IRQ] = 1;
 cover_level = cover = 1;
 snap();
}

/* ... and after a confirmed detach: connect IRQ on, DATA down, rail off. */
static void bring_up_detached(void)
{
 clear_counts();
 p.powered = false; p.ready = false; p.event_enabled = false;
 p.irq_armed = false; p.conn_irq_armed = true; p.connect_state = false;
 reg_count = 0;
 irq_enabled[CONNECT_IRQ] = irq_enables[CONNECT_IRQ] = 1;
 cover_level = cover = 0;
 snap();
}

/* Neither line may be left enabled, and no line may be toggled twice. */
static void assert_irq_balance(void)
{
 assert(irq_enables[CONNECT_IRQ] == irq_disables[CONNECT_IRQ]);
 assert(irq_enables[DATA_IRQ] == irq_disables[DATA_IRQ]);
 assert(!irq_enabled[CONNECT_IRQ] && !irq_enabled[DATA_IRQ]);
 assert(!lock_held);
}

int main(void)
{
 memset(&p, 0, sizeof(p));
 client.irq = DATA_IRQ;
 p.client = &client;
 p.connected = &cover; p.vdd = &vdd;
 p.connect_irq = CONNECT_IRQ;
 the_pogo = &p;

 /* Case 1 + 4: READY -> suspend -> resume with the cover still seated. */
 bring_up_attached();
 pogo_suspend(&dev);
 assert(!lock_held);
 assert(!p.conn_irq_armed && !irq_enabled[CONNECT_IRQ]);
 assert(!p.irq_armed && !irq_enabled[DATA_IRQ]);
 assert(!p.event_enabled);
 assert(SINCE(cancelled) == 4);          /* all four works stopped */
 assert(SINCE(releases) == 1);           /* nothing stays logically pressed */
 /* The rail and the MCU's READY state survive: no power cycle, no reset. */
 assert(p.powered && p.ready && reg_count == 1);
 assert(rail_gpio_writes == 0 && bus_transfers == 0);
 assert(SINCE(removes) == 0);            /* case 8: sysfs attribute kept */

 snap();
 pogo_resume(&dev);
 assert(!lock_held);
 assert(p.powered && p.ready && p.event_enabled);
 assert(reg_count == 1);                 /* resume did not re-enable the rail */
 /* DATA re-armed once, connect re-enabled once, watchdog restored - and no
    reset line write or bus transfer anywhere: cases 9 and 10. */
 assert(p.irq_armed && irq_enabled[DATA_IRQ]);
 assert(irq_enables[DATA_IRQ] == 2 && irq_disables[DATA_IRQ] == 1);
 assert(p.conn_irq_armed && irq_enabled[CONNECT_IRQ]);
 assert(irq_enables[CONNECT_IRQ] == 2 && irq_disables[CONNECT_IRQ] == 1);
 assert(SINCE(queued) == 1 && SINCE(sleeps) == 0);
 assert(rail_gpio_writes == 0 && bus_transfers == 0);
 assert(SINCE(removes) == 0);

 /* Case 7: a second full cycle must not unbalance either line either.  Both
    end armed again, so each line has exactly one enable still outstanding. */
 snap();
 pogo_suspend(&dev);
 pogo_resume(&dev);
 assert(irq_enabled[CONNECT_IRQ] && irq_enabled[DATA_IRQ]);
 assert(irq_enables[CONNECT_IRQ] == irq_disables[CONNECT_IRQ] + 1);
 assert(irq_enables[DATA_IRQ] == irq_disables[DATA_IRQ] + 1);
 assert(reg_count == 1 && p.ready);
 assert(rail_gpio_writes == 0 && bus_transfers == 0);

 /* Case 6: after resume, the 250 ms connect check still detaches and
    reconnects, through the same verified sequences. */
 snap();
 cover_level = cover = 0;
 pogo_conn_check_work(&p.conn_check_work.work);
 assert(!lock_held);
 assert(!p.connect_state && !p.powered && !p.ready && !p.event_enabled);
 assert(reg_count == 0 && !irq_enabled[DATA_IRQ] && SINCE(releases) == DETACH_RELEASES);
 cover_level = cover = 1;
 pogo_conn_check_work(&p.conn_check_work.work);
 assert(p.connect_state && p.powered && p.event_enabled);
 assert(reg_count == 1 && irq_enabled[DATA_IRQ] && p.irq_armed);
 assert(SINCE(sleeps) == 1);             /* the reconnect's 50 ms settle */
 assert(rail_gpio_writes == 0 && bus_transfers == 0);

 /* Case 3 + 5: DETACHED -> suspend -> resume stays DETACHED. */
 bring_up_detached();
 pogo_suspend(&dev);
 assert(!p.conn_irq_armed && !irq_enabled[CONNECT_IRQ]);
 assert(irq_disables[DATA_IRQ] == 0);    /* nothing was armed to disarm */
 assert(SINCE(releases) == 1 && reg_count == 0);
 snap();
 pogo_resume(&dev);
 assert(!lock_held);
 assert(!p.connect_state && !p.powered && !p.ready && !p.event_enabled);
 assert(!p.irq_armed && !irq_enabled[DATA_IRQ]);    /* DATA stays down */
 assert(p.conn_irq_armed && irq_enabled[CONNECT_IRQ]);
 assert(reg_count == 0 && SINCE(queued) == 1);
 assert(rail_gpio_writes == 0 && bus_transfers == 0);

 /* The cover appears while suspended: resume brings it up through the verified
    hot reconnect, with the 50 ms settle and still no reset. */
 snap();
 pogo_suspend(&dev);
 cover_level = cover = 1;
 pogo_resume(&dev);
 assert(p.connect_state && p.powered && p.event_enabled && p.irq_armed);
 assert(reg_count == 1 && irq_enabled[DATA_IRQ] && SINCE(sleeps) == 1);
 assert(rail_gpio_writes == 0 && bus_transfers == 0);

 /* The cover goes away while suspended: resume detaches and drops the rail. */
 bring_up_attached();
 pogo_suspend(&dev);
 cover_level = cover = 0;
 snap();
 pogo_resume(&dev);
 assert(!p.connect_state && !p.powered && !p.ready);
 assert(reg_count == 0 && SINCE(releases) == DETACH_RELEASES);
 assert(!p.irq_armed && !irq_enabled[DATA_IRQ]);
 assert(p.conn_irq_armed && irq_enabled[CONNECT_IRQ]);
 assert(rail_gpio_writes == 0 && bus_transfers == 0);

 /* A failed regulator enable must not arm DATA or claim the cover is up. */
 bring_up_detached();
 cover_level = cover = 1;
 power_error = -5;
 pogo_suspend(&dev);
 pogo_resume(&dev);
 assert(!p.event_enabled && !p.irq_armed && !irq_enabled[DATA_IRQ]);
 assert(reg_count == 0 && !lock_held);

 /* Teardown is the one place the attribute and both lines go away. */
 bring_up_attached();
 pogo_remove(&p);
 assert(SINCE(removes) == 1 && reg_count == 0 && !lock_held);
 assert(!p.powered && !p.event_enabled && !p.irq_armed && !p.conn_irq_armed);
 assert_irq_balance();

 /* A remove that follows a suspend must not disable the connect line twice. */
 bring_up_attached();
 pogo_suspend(&dev);
 snap();
 pogo_remove(&p);
 assert(SINCE(removes) == 1 && reg_count == 0 && !lock_held);
 assert(irq_enables[CONNECT_IRQ] == irq_disables[CONNECT_IRQ]);
 assert(irq_enables[DATA_IRQ] == irq_disables[DATA_IRQ]);

 puts("pogo suspend/resume lifecycle cases passed");
 return 0;
}
'''


class PogoSuspend(unittest.TestCase):
    def test_suspend_resume_lifecycle(self):
        source = (ROOT / 'kernel/drivers/keyboard-samsung-pogo.c').read_text()
        harness = HARNESS_HEAD
        for name in FUNCTIONS:
            definition = re.search(r'^static [^\n]*\b' + name + r'\([^;]*?\)\n\{',
                                   source, flags=re.M)
            self.assertIsNotNone(definition, name)
            harness += '\n' + function(source[definition.start():], name) + '\n'
        harness += MAIN
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'suspend.c'
            exe = Path(tmp) / 'suspend'
            c.write_text(harness)
            subprocess.run(['clang', '-Wall', '-Wextra', '-Werror',
                            '-Wno-unused-parameter', '-Wno-unused-function',
                            '-fsanitize=address,undefined',
                            '-g', str(c), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)


if __name__ == '__main__':
    unittest.main()
