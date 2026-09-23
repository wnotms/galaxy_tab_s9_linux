"""Exercise the actual IRQ packet parser with a mock transport (no hardware)."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from test_panel_x710 import function

ROOT = Path(__file__).resolve().parents[1]

class PogoPackets(unittest.TestCase):
    def test_irq_packets(self):
        source = (ROOT / 'kernel/drivers/keyboard-samsung-pogo.c').read_text()
        harness = r'''
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint16_t u16;
typedef int irqreturn_t;
#define IRQ_HANDLED 1
#define POGO_MAX_PAYLOAD 100
#define KEY_CNT 768
#define READ_ONCE(x) (x)
struct input_dev { bool keybit[KEY_CNT]; };
struct i2c_client { int dev; };
#define msecs_to_jiffies(ms) ((unsigned long)(ms))
struct delayed_work { int unused; };
struct samsung_pogo { struct input_dev *input; struct i2c_client *client;
 int lock; int *connected; bool powered, ready; u8 caps;
 bool observe_only; unsigned int announce_seen;  bool rearm_pending;
 unsigned int stuck_fails;
 int conn_level;
 unsigned long last_rearm;
 int conn_same;
 bool reconnect;
 bool irq_armed;
 unsigned int poll_tick;
 u8 rearm_mode;
 struct delayed_work hello_work;
 unsigned int hello_tries;
};
static u8 wire[128];
/* The handler now gates on the line being asserted, as stock's ISR does. */
static int pogo_announce_level(struct samsung_pogo *p) { return 1; }
static int pos, available, short_read, reports, releases, hellos, writes;
static int codes[50], values[50];
static unsigned int get_unaligned_le16(const u8 *p) { return p[0] | (p[1]<<8); }
static int mod_delayed_work(void *wq, struct delayed_work *w, unsigned long d)
{ (void)wq; (void)w; (void)d; return 1; }
#define system_percpu_wq ((void *)0)
static void mutex_lock(int *x) { (void)x; }
static void mutex_unlock(int *x) { (void)x; }
static int gpiod_get_value_cansleep(int *x) { return *x; }
static void disable_irq_nosync(int irq) { (void)irq; }
static bool test_bit(unsigned int n, bool *b) { return b[n]; }
#define dev_info(...) ((void)0)
#define dev_warn_ratelimited(...) ((void)0)
#define dev_err_ratelimited(...) ((void)0)
/* Routine protocol traffic moved to debug level.  None of these calls has a
   side effect in its argument list, so discarding them is safe here. */
#define dev_dbg(...) ((void)0)
#define dev_dbg_ratelimited(...) ((void)0)
static void msleep(int n) { (void)n; }
static void input_sync(struct input_dev *i) { (void)i; }
static void input_report_key(struct input_dev *i, unsigned int c, int v) {
 (void)i; assert(reports < 50); codes[reports]=c; values[reports++]=v;
}
static int pogo_write(struct samsung_pogo *p, const u8 *b, int n) {
 (void)p; assert(n==3 && b[0]==3 && b[1]==0); writes++; return 0;
}
static int pogo_read(struct samsung_pogo *p, u8 *b, int n) {
 (void)p; if(short_read) return -EIO;
 assert(pos+n<=available); memcpy(b,wire+pos,n); pos+=n; return 0;
}
static void pogo_release_keys(struct samsung_pogo *p) { (void)p; releases++; }
static int pogo_hello(struct samsung_pogo *p,u8 model) { (void)p; assert(model==2); hellos++; return 0; }
'''
        harness += '\n' + function(source[source.index('static irqreturn_t pogo_irq('):], 'pogo_irq') + '\n'
        harness += r'''
static void packet(unsigned int size, u8 id) {
 memset(wire,0,sizeof(wire)); wire[0]=size; wire[1]=size>>8; wire[2]=id;
 available=size; pos=reports=releases=hellos=writes=short_read=0;
}
int main(void) {
 struct input_dev input={0}; struct i2c_client client={0}; int connected=1;
 struct samsung_pogo p={ .input=&input,.client=&client,.connected=&connected,
 .powered=true,.ready=true,.caps=1 };
 input.keybit[30]=true; input.keybit[48]=true;
 packet(7,3); wire[3]=30; wire[4]=0x80; wire[5]=30;
 pogo_irq(1,&p); assert(reports==2 && codes[0]==30 && values[0]==1 && values[1]==0 && !releases);
 packet(103,3); for(int i=3;i<103;i+=2) { wire[i]=48;wire[i+1]=0x80; }
 pogo_irq(1,&p); assert(reports==50);
 packet(4,3); wire[3]=30; pogo_irq(1,&p); assert(!reports && releases==1);
 packet(7,3); wire[3]=30; wire[4]=0x80; wire[5]=0xff; wire[6]=0x7f;
 pogo_irq(1,&p); assert(!reports && releases==1);
 packet(104,3); available=3; pogo_irq(1,&p); assert(pos==3 && releases==1);
 packet(2,3); available=3; pogo_irq(1,&p); assert(releases==1);
 packet(3,2); pogo_irq(1,&p); assert(hellos==1 && !reports);
 packet(0,2); available=3; pogo_irq(1,&p); assert(hellos==1);
 packet(5,3); short_read=1; pogo_irq(1,&p); assert(releases==1 && !reports);
 packet(4,4); pogo_irq(1,&p); assert(releases==1);
 packet(5,3); wire[3]=30; p.ready=false; pogo_irq(1,&p); assert(!reports);
 packet(5,3); p.powered=false; pogo_irq(1,&p); assert(!writes && !reports);
 puts("12 packet/error cases passed"); return 0;
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            c = Path(tmp) / 'pogo.c'; exe = Path(tmp) / 'pogo'
            c.write_text(harness)
            subprocess.run(['clang', '-Wall', '-Wextra', '-Wno-unused-parameter',
                            '-fsanitize=address,undefined', '-g', str(c), '-o', str(exe)], check=True)
            subprocess.run([str(exe)], check=True)

    def test_irq_path_is_quiet_by_default(self):
        """No per-key or per-packet line may reach dmesg at info level."""
        source = (ROOT / 'kernel/drivers/keyboard-samsung-pogo.c').read_text()
        body = function(source[source.index('static irqreturn_t pogo_irq('):],
                        'pogo_irq')
        # The interrupt path runs once per key transition, so nothing in it may
        # be dev_info(); the same information is on /dev/input/eventX already.
        self.assertNotIn('dev_info(', body)
        # Quiet is not the same as silent: a malformed packet and a failed
        # transfer must still be reported, through the ratelimited warnings.
        self.assertIn('dev_warn_ratelimited(', body)
        self.assertIn('dev_err_ratelimited(', body)
        # The three routine reports are debug level.
        for needle in ('"packet from the MCU', '"payload (%u bytes)', '"key %#x %s'):
            self.assertIn('dev_dbg(&p->client->dev, ' + needle, body)


if __name__ == '__main__':
    unittest.main()

