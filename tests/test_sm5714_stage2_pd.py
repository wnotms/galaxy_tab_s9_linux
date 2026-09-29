"""Stage2 exact config/topology gates and real C transport/power boundaries."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_sm5714_charge_safety as safety
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("stage2_gate", ROOT / "scripts/verify-sm5714-stage2.py")
GATE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GATE)


class Stage2ConfigTests(unittest.TestCase):
    def setUp(self):
        self.base = GATE.BASE.read_text()
        self.new = self.base + "CONFIG_TYPEC_SM5714=y\n"

    def test_exact_one_symbol_delta(self):
        self.assertTrue(GATE.verify(self.new, self.base)["valid"])

    def test_dcc_and_other_hardware_changes_fail(self):
        for name in ("CONFIG_HVC_DCC", "CONFIG_USB_DWC3", "CONFIG_BATTERY_SM5714"):
            cfg = GATE.CONTAINER.read_config(self.new)
            cfg[name] = "n" if cfg[name] == "y" else "y"
            text = "\n".join(f"{k}={v}" for k, v in cfg.items())
            self.assertFalse(GATE.verify(text, self.base)["valid"])

    def test_every_test254_prerequisite_stays_builtin(self):
        for name in GATE.CONTAINER.REQUIRED_Y:
            with self.subTest(name=name):
                cfg = GATE.CONTAINER.read_config(self.new)
                cfg[name] = "n"
                self.assertFalse(GATE.verify("\n".join(f"{k}={v}" for k, v in cfg.items()),
                                             self.base)["valid"])

    def test_forbidden_features_and_missing_transport_fail(self):
        for name in GATE.FORBIDDEN:
            cfg = GATE.CONTAINER.read_config(self.new)
            cfg[name] = "y"
            self.assertFalse(GATE.verify("\n".join(f"{k}={v}" for k, v in cfg.items()),
                                         self.base)["valid"])
        self.assertFalse(GATE.verify(self.base, self.base)["valid"])

    def test_fragment_and_default_build_gate(self):
        cfg = GATE.CONTAINER.read_config((ROOT / "kernel/config/gts9wifi-mainline.fragment").read_text())
        # REGMAP_I2C is selected by the new Kconfig hook, verified after resolve.
        for name in GATE.REQUIRED - {"CONFIG_REGMAP_I2C"}:
            self.assertEqual(cfg.get(name), "y")
        self.assertEqual(cfg["CONFIG_HVC_DCC"], "n")
        self.assertNotIn("CONFIG_CHARGER_SM5440_DIRECT", cfg)
        self.assertIn('scripts/verify-sm5714-stage2.py" "$build_dir/.config"',
                      (ROOT / "scripts/build-kernel.sh").read_text())

    def test_minimum_sink_topology(self):
        dts = (ROOT / "kernel/dts/sm8550-samsung-gts9wifi.dts").read_text()
        hub = dts.split("&i2c_hub_9 {")[1].split("/* I2C3")[0]
        for expected in ('clock-frequency = <400000>', 'status = "okay"',
                         'reg = <0x33>', '<&tlmm 133 IRQ_TYPE_LEVEL_LOW>',
                         'power-role = "sink"', 'data-role = "device"',
                         'PDO_FIXED(5000, 1800, PDO_FIXED_USB_COMM)',
                         'PDO_FIXED(9000, 1500, PDO_FIXED_USB_COMM)'):
            self.assertIn(expected, hub)
        for forbidden in ('source-pdos', 'PDO_PPS', 'PDO_FIXED_DUAL_ROLE',
                          'PDO_FIXED_DATA_SWAP', 'altmodes', 'port@1', 'port@2', 'otg-det-gpios'):
            self.assertNotIn(forbidden, hub)
        self.assertIn('pins = "gpio133"', dts)
        self.assertIn('status = "disabled"', dts.split('sm5440_direct: charger@63')[1].split('};')[0])
        self.assertNotIn('tcpm-power-supply', dts)
        self.assertIn('dr_mode = "peripheral"', dts.split('&usb_1 {')[1].split('};')[0])
        self.assertIn('/delete-property/ usb-role-switch;', dts.split('&usb_1 {')[1].split('};')[0])
        self.assertIn('voltage-max-design-microvolt = <4440000>', dts)

    def test_kbuild_no_core_patch_or_advanced_transport(self):
        patch = (ROOT / "kernel/patches/0012-usb-typec-hook-sm5714-sink.patch").read_text()
        self.assertIn('depends on I2C && TYPEC_TCPM && BATTERY_SM5714', patch)
        self.assertNotIn('+++ b/drivers/usb/typec/tcpm/tcpm.c', patch)
        src = (ROOT / "kernel/drivers/sm5714_usbpd.c").read_text()
        for forbidden in ('sm5714_battery_set_otg', 'adopt_retained', 'start_toggling =',
                          'gpiod_set_value', 'sm5440', 'fast_charge', 'max_pps_ma'):
            self.assertNotIn(forbidden, src)

    def test_stage2_probe_inhibited_before_tcpc_claim(self):
        src = (ROOT / "kernel/drivers/sm5714-battery.c").read_text()
        probe = function(src, "static int sm5714_probe(")
        self.assertLess(probe.index('typec_owned = IS_ENABLED(CONFIG_TYPEC_SM5714)'),
                        probe.index('sm5714_configure_charging(sm)'))
        claim = function(src, "int sm5714_battery_typec_claim(")
        self.assertIn('if (sm->typec_claimed)', claim)

    def test_build_default_gate_does_not_reject_separate_diagnostic_delta(self):
        cfg = GATE.CONTAINER.read_config(self.new)
        cfg['CONFIG_CSD_LOCK_WAIT_DEBUG'] = 'y'
        text = "\n".join(f"{k}={v}" for k, v in cfg.items())
        self.assertTrue(GATE.verify(text)["valid"])
        self.assertFalse(GATE.verify(text, self.base)["valid"])


class Stage2ChargeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Same real configure_charging fixture as Stage1; its old checks remain.
        safety.ChargeSafetyTests.setUpClass.__func__(cls)

    def charge(self, mv=9000, ma=3000, enabled=1, suspended=0, temp=250, mode=0):
        result = subprocess.run([str(self.binary), str(mode), "4", str(temp),
                                 str(mv), str(ma), str(enabled), str(suspended)],
                                check=True, capture_output=True, text=True)
        return list(map(int, result.stdout.split()))

    def test_9v_three_amp_offer_draws_at_most_1500ma(self):
        result = self.charge()
        self.assertEqual(result[0], 0)
        self.assertEqual(result[2] & 0x7f, 56)  #100+56*25=1500mA
        self.assertEqual(result[3], 0x86)
        self.assertEqual(result[4] & 0x3f, 0x2d)

    def test_contract_current_is_respected(self):
        for ma in (100, 250, 500, 900, 1200):
            with self.subTest(ma=ma):
                result = self.charge(ma=ma)
                self.assertLessEqual(100 + (result[2] & 0x7f) * 25, ma)

    def test_zero_and_subminimum_standby_budget_open_q4(self):
        for ma in (0, 55, 99):
            r = self.charge(ma=ma)
            self.assertEqual(r[1] & 8, 0)
            self.assertEqual(r[2] & 0x7f, 0)  # hardware minimum100mA, not isolation

    def test_tcpm_off_and_suspend_inhibit_async_charge(self):
        self.assertEqual(self.charge(enabled=0)[1] & 8, 0)
        self.assertEqual(self.charge(suspended=1)[1] & 8, 0)

    def test_same_thermal_limits_and_float(self):
        for temp in (99, 500, 650):
            self.assertEqual(self.charge(temp=temp)[1] & 8, 0)
        for temp in (100, 179, 420, 499):
            result = self.charge(temp=temp)
            self.assertEqual(result[2] & 0x7f, 16)
            self.assertEqual(result[4] & 0x3f, 0x2d)

    def test_pd_program_readback_faults_never_enable_q4(self):
        for mode in (1, 2, 3, 4, 5, 6, 8):
            self.assertEqual(self.charge(mode=mode)[1] & 8, 0)


class Stage2CompanionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        safety.ChargeSafetyTests.setUpClass.__func__(cls)
        src = (ROOT / "kernel/drivers/sm5714-battery.c").read_text()
        code = (Path(cls.temp.name) / "charge.c").read_text().split("int main(")[0]
        code += '''
#define EPROBE_DEFER 517
#define EXPORT_SYMBOL_GPL(x)
#define power_supply_changed(x) ((void)(x))
#define lockdep_assert_held(x) ((void)(x))
static int sm5714_companion_lock;
static struct sm5714_battery *sm5714_companion;
'''
        for name in ("static void sm5714_inhibit_typec_locked(",
                     "int sm5714_battery_set_pd_contract(",
                     "int sm5714_battery_set_typec_charge(",
                     "void sm5714_battery_typec_fault(",
                     "int sm5714_battery_typec_claim("):
            code += function(src, name) + "\n"
        code += r'''
int main(int argc, char **argv) {
 if(argc!=4)return 2;
 struct sm5714_battery sm={.float_uv=4440000};
 int op=atoi(argv[1]),mv=atoi(argv[2]),ma=atoi(argv[3]),r=0;
 type=POWER_SUPPLY_USB_TYPE_PD;
 regs[0x13]=8; regs[0x1a]=0xc0;
 regs[0x15]=0x80|120;
 if(op!=5)sm5714_companion=&sm;
 if(op==6)sm.typec_owned=true;
 r=sm5714_battery_typec_claim();
 if(op!=5 && op!=6){
   sm.typec_charge=true; sm.suspended=op==2;
   if(op==7)mode=1;
   r=sm5714_battery_set_pd_contract(mv,ma);
   if(op==7){mode=0;r=sm5714_battery_set_pd_contract(mv,ma);}
   if(op==1)r=sm5714_battery_set_typec_charge(false);
   if(op==3){sm5714_battery_typec_fault();r=sm5714_battery_set_typec_charge(true);}
   if(op==4)r=sm5714_battery_typec_claim();
 }
 printf("%d %u %u %u %u %d\n",r,regs[0x13],regs[0x15],sm.typec_mv,
        sm.typec_ma,sm.typec_fault);
 return 0;
}
'''
        path = Path(cls.temp.name) / "companion.c"
        path.write_text(code)
        cls.binary = Path(cls.temp.name) / "companion"
        run = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                              str(path), "-o", str(cls.binary)], capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stderr)

    def run_companion(self, op=0, mv=9000, ma=3000):
        run = subprocess.run([str(self.binary), str(op), str(mv), str(ma)],
                             check=True, capture_output=True, text=True)
        return list(map(int, run.stdout.split()))

    def test_grant_preserved_actual_draw_capped(self):
        r = self.run_companion()
        self.assertEqual(r[0], 0)
        self.assertEqual(r[2] & 0x7f, 56)
        self.assertEqual(r[3:5], [9000, 3000])

    def test_invalid_voltage_latches_off(self):
        for mv in (6000, 9500, 12000, 15000, 20000):
            r = self.run_companion(mv=mv)
            self.assertLess(r[0], 0)
            self.assertEqual(r[1] & 8, 0)
            self.assertEqual(r[5], 1)

    def test_zero_budget_and_explicit_charge_off(self):
        for r in (self.run_companion(ma=0), self.run_companion(op=1)):
            self.assertEqual(r[1] & 8, 0)
            self.assertEqual(r[4], 0)

    def test_suspended_callback_cannot_reenable(self):
        self.assertEqual(self.run_companion(op=2)[1] & 8, 0)

    def test_first_fault_survives_enable_and_rebind(self):
        r = self.run_companion(op=3)
        self.assertEqual(r[1] & 8, 0)
        self.assertEqual(r[2] & 0x7f, 0)
        self.assertLess(self.run_companion(op=4)[0], 0)

    def test_not_ready_supplier_defers_without_pointer_access(self):
        self.assertEqual(self.run_companion(op=5)[0], -517)

    def test_pending_probe_claim_keeps_retained_high_input_inhibited(self):
        r = self.run_companion(op=6)
        self.assertEqual(r[0], 0)
        self.assertEqual(r[1] & 8, 0)
        self.assertEqual(r[2], 0x80)

    def test_program_failure_stays_inhibited_after_io_recovers(self):
        r = self.run_companion(op=7)
        self.assertEqual(r[1] & 8, 0)
        self.assertEqual(r[5], 1)


class Stage2TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        src = (ROOT / "kernel/drivers/sm5714_usbpd.c").read_text()
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "transport"
        code = r'''
#include <stdint.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
typedef uint8_t u8;
typedef uint32_t u32;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define READ_ONCE(x) (x)
#define WRITE_ONCE(x,v) ((x)=(v))
#define min(x,y) ((x)<(y)?(x):(y))
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
#define lockdep_assert_held(x) ((void)(x))
#define dev_info(...) ((void)0)
#define dev_err(...) ((void)0)
#define le32_to_cpu(x) (x)
#define le16_to_cpu(x) (x)
#define PD_MAX_PAYLOAD 7
#define PD_DATA_REQUEST 2
#define PD_DATA_SOURCE_CAP 1
#define PD_CTRL_SOFT_RESET 13
#define PD_HEADER_EXT_HDR (1U<<15)
#define RDO_CAP_MISMATCH (1U<<26)
#define PDO_TYPE_FIXED 0
enum typec_cc_status { TYPEC_CC_OPEN, TYPEC_CC_RA, TYPEC_CC_RD,
 TYPEC_CC_RP_DEF, TYPEC_CC_RP_1_5, TYPEC_CC_RP_3_0 };
enum typec_cc_polarity { TYPEC_POLARITY_CC1, TYPEC_POLARITY_CC2 };
enum typec_role { TYPEC_SINK, TYPEC_SOURCE };
enum typec_data_role { TYPEC_DEVICE, TYPEC_HOST };
enum tcpm_transmit_type { TCPC_TX_SOP, TCPC_TX_SOP_PRIME, TCPC_TX_SOP_PRIME_PRIME,
 TCPC_TX_SOP_DEBUG_PRIME, TCPC_TX_SOP_DEBUG_PRIME_PRIME, TCPC_TX_HARD_RESET };
enum { TCPC_TX_SUCCESS, TCPC_TX_DISCARDED, TCPC_TX_FAILED };
struct pd_message { uint16_t header; u32 payload[7]; };
struct sm5714_usbpd;
struct tcpc_dev { struct sm5714_usbpd *owner; };
struct sm5714_usbpd { int dev, lock; void *regmap, *port; struct tcpc_dev tcpc;
 u32 source_pdos[7]; unsigned int nr_source_pdos;
 unsigned long long source_generation; bool fault, removing; };
static unsigned char regs[256];
static int calls, failure, disabled, charge_stops, rx_count, tx_status=-1;
static unsigned int budget_mv, budget_ma;
static struct pd_message delivered;
static struct sm5714_usbpd *tcpc_to_sm5714(struct tcpc_dev *t) {return t->owner;}
static int step(void) {return ++calls == failure ? -EIO : 0;}
static int regmap_read(void *m, unsigned int r, unsigned int *v) {
 (void)m; int e=step(); if (!e) *v=regs[r]; return e; }
static int regmap_write(void *m, unsigned int r, unsigned int v) {
 (void)m; int e=step(); if (!e) regs[r]=v; return e; }
static int regmap_update_bits(void *m,unsigned int r,unsigned int mask,unsigned int v) {
 (void)m; int e=step(); if (!e) regs[r]=(regs[r]&~mask)|(v&mask); return e; }
static int regmap_bulk_read(void *m, unsigned int r, void *v, unsigned int n) {
 (void)m; int e=step(); if (!e) {memcpy(v,regs+r,n); if(r==1) memset(regs+r,0,n);} return e; }
static int regmap_bulk_write(void *m,unsigned int r,const void *v,unsigned int n) {
 (void)m; int e=step(); if (!e) memcpy(regs+r,v,n); return e; }
static void sm5714_battery_typec_fault(void) {charge_stops++;}
static int sm5714_battery_get_bc12_limit(void) {return 1800;}
static int sm5714_battery_set_typec_charge(bool b) {if(!b) charge_stops++; return 0;}
static int sm5714_battery_set_pd_contract(unsigned int mv,unsigned int ma) {
 budget_mv=mv; budget_ma=ma; return mv==0||mv==5000||mv==9000?0:-ERANGE; }
static unsigned int pd_header_cnt_le(uint16_t h) {return (h>>12)&7;}
static unsigned int pd_header_type_le(uint16_t h) {return h&31;}
static unsigned int rdo_index(u32 r) {return (r>>28)&7;}
static unsigned int rdo_op_current(u32 r) {return ((r>>10)&1023)*10;}
static unsigned int rdo_max_current(u32 r) {return (r&1023)*10;}
static unsigned int pdo_type(u32 p) {return p>>30;}
static unsigned int pdo_fixed_voltage(u32 p) {return ((p>>10)&1023)*50;}
static unsigned int pdo_max_current(u32 p) {return (p&1023)*10;}
static void tcpm_pd_receive(void *p, const struct pd_message *m,int sop) {
 (void)p;(void)sop;delivered=*m;rx_count++; }
static void tcpm_pd_transmit_complete(void *p,int s) {(void)p;tx_status=s;}
static void tcpm_pd_hard_reset(void *p) {(void)p;}
static void tcpm_cc_change(void *p) {(void)p;}
static void tcpm_vbus_change(void *p) {(void)p;}
static void disable_irq_nosync(int i) {(void)i;disabled++;}
typedef int irqreturn_t;
#define IRQ_HANDLED 1
'''
        code += "\n".join(line for line in src.splitlines() if line.startswith("#define SM5714_"))
        code += '\n#include "' + str(ROOT / 'kernel/drivers/sm5714-pd-policy.h') + '"\n'
        names = ["static void sm5714_forget_source(",
                 "static int sm5714_result(", "static int sm5714_usbpd_init(",
                 "static int sm5714_usbpd_get_vbus(", "static int sm5714_usbpd_get_current_limit(",
                 "static int sm5714_usbpd_get_cc(", "static int sm5714_usbpd_set_cc(",
                 "static int sm5714_usbpd_set_polarity(", "static int sm5714_usbpd_set_vconn(",
                 "static int sm5714_usbpd_set_vbus(", "static int sm5714_usbpd_set_current_limit(",
                 "static int sm5714_usbpd_set_pd_rx(", "static int sm5714_usbpd_set_roles(",
                 "static bool sm5714_request_allowed(", "static int sm5714_usbpd_transmit(",
                 "static int sm5714_usbpd_receive(", "static irqreturn_t sm5714_usbpd_irq("]
        code += "\n" + "\n".join(function(src, marker) for marker in names)
        code += r'''
int main(int argc, char **argv) {
 struct sm5714_usbpd sm={0}; sm.tcpc.owner=&sm;
 if(argc<3)return 2;
 int op=atoi(argv[1]),v=atoi(argv[2]),r=0; failure=argc>3?atoi(argv[3]):0;
 enum typec_cc_status a=0,b=0;
 if(op==0){regs[0x39]=0xff;regs[0xd8]=6;r=sm5714_usbpd_init(&sm.tcpc);}
 if(op==1){regs[0x28]=v;r=sm5714_usbpd_get_cc(&sm.tcpc,&a,&b);}
 if(op==2)r=sm5714_usbpd_set_cc(&sm.tcpc,v);
 if(op==3)r=sm5714_usbpd_set_roles(&sm.tcpc,true,v/2,v%2);
 if(op==4)r=sm5714_usbpd_set_vconn(&sm.tcpc,v);
 if(op==5)r=sm5714_usbpd_set_vbus(&sm.tcpc,v,true);
 if(op==6){
   sm.nr_source_pdos=4;
   sm.source_pdos[0]=(100U<<10)|300; sm.source_pdos[1]=(180U<<10)|300;
   sm.source_pdos[2]=(240U<<10)|300; sm.source_pdos[3]=3U<<30;
   u32 rdo=((unsigned)v>>16)<<28 | (((unsigned)v&65535)/10)<<10 | ((unsigned)v&65535)/10;
   r=sm5714_request_allowed(&sm,rdo);
 }
 if(op==7){regs[0x28]=1;r=sm5714_usbpd_set_current_limit(&sm.tcpc,1500,v);}
 if(op==8){
   struct pd_message m={.header=0x1001,.payload={0x0001912c}};
   memcpy(regs+0x42,&m.header,2);memcpy(regs+0x44,m.payload,4);
   regs[0x41]=v;r=sm5714_usbpd_receive(&sm);
 }
 if(op==9){regs[4]=v;r=sm5714_usbpd_irq(1,&sm);}
 if(op==10)r=sm5714_usbpd_transmit(&sm.tcpc,TCPC_TX_HARD_RESET,NULL,0);
 if(op==11)r=sm5714_usbpd_set_pd_rx(&sm.tcpc,v);
 if(op==12){regs[0x0b]=v;r=sm5714_usbpd_get_vbus(&sm.tcpc);}
 if(op==13)r=sm5714_usbpd_get_current_limit(&sm.tcpc);
 if(op==14)r=sm5714_usbpd_set_polarity(&sm.tcpc,v);
 if(op==15){
   sm.nr_source_pdos=1; sm.source_pdos[0]=(100U<<10)|50;
   u32 rdo=(1U<<28)|(50U<<10)|180U|(v?RDO_CAP_MISMATCH:0);
   r=sm5714_request_allowed(&sm,rdo);
 }
 if(op==16){
   sm.nr_source_pdos=1;sm.source_pdos[0]=(180U<<10)|150;
   if(v==0)r=sm5714_usbpd_init(&sm.tcpc);
   if(v==1)r=sm5714_usbpd_set_cc(&sm.tcpc,TYPEC_CC_OPEN);
   if(v==2)r=sm5714_usbpd_set_pd_rx(&sm.tcpc,false);
   if(v==3)r=sm5714_usbpd_transmit(&sm.tcpc,TCPC_TX_HARD_RESET,NULL,0);
   if(v==4)r=sm5714_result(&sm,-EIO);
   if(v==5){struct pd_message m={.header=13};r=sm5714_usbpd_transmit(&sm.tcpc,TCPC_TX_SOP,&m,0);}
   if(v==6){regs[0x42]=13;r=sm5714_usbpd_receive(&sm);}
   if(v==7){regs[1]=16;r=sm5714_usbpd_irq(1,&sm);}
   if(v==8){regs[1]=8;r=sm5714_usbpd_irq(1,&sm);}
   if(v==9){regs[4]=32;r=sm5714_usbpd_irq(1,&sm);}
   if(v==10){regs[4]=64;r=sm5714_usbpd_irq(1,&sm);}
 }
 if(op==17){
   sm.nr_source_pdos=1;sm.source_pdos[0]=(180U<<10)|150;
   regs[0x42]=1;regs[0x43]=16;regs[4]=1;
   if(v==0)regs[1]=16;
   if(v==1)regs[4]|=32;
   if(v==2)regs[4]|=64;
   r=sm5714_usbpd_irq(1,&sm);
 }
 if(op==18){struct pd_message m={.header=0x9002,.payload={(1U<<28)|(180U<<10)|180}};
   sm.nr_source_pdos=1;sm.source_pdos[0]=(100U<<10)|300;
   r=sm5714_usbpd_transmit(&sm.tcpc,TCPC_TX_SOP,&m,0);
 }
 printf("%d %u %u %u %u %u %u %d %d %d %d %d %u %u %u %llu %u\n",r,a,b,regs[0x29],
 regs[0x2b],regs[0x39],regs[0x3b],sm.fault,charge_stops,rx_count,tx_status,disabled,
 budget_mv,budget_ma,sm.nr_source_pdos,sm.source_generation,sm.source_pdos[0]);
 return 0;
}
'''
        path = Path(cls.temp.name) / "transport.c"
        path.write_text(code)
        run = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                              "-Wno-unused-parameter", str(path), "-o", str(cls.binary)],
                             capture_output=True, text=True)
        if run.returncode:
            raise AssertionError(run.stderr)

    def run_transport(self, op, value=0, failure=0):
        result = subprocess.run([str(self.binary), str(op), str(value), str(failure)],
                                check=True, capture_output=True, text=True)
        return list(map(int, result.stdout.split()))

    def test_init_sink_only_and_header_bits_preserved(self):
        r = self.run_transport(0)
        self.assertEqual(r[0], 0)
        self.assertEqual(r[3:7], [0x45, 0x82, 0xfc, 1])

    def test_each_init_transfer_failure_latches_charge_off(self):
        for step in range(1, 12):
            with self.subTest(step=step):
                r = self.run_transport(0, failure=step)
                self.assertLess(r[0], 0)
                self.assertEqual(r[7:9], [1, 1])

    def test_cc_polarity_and_rp_levels(self):
        for cc, expected in ((1, 3), (9, 4), (17, 5), (25, 5)):
            self.assertEqual(self.run_transport(1, cc)[1:3], [expected, 0])
            self.assertEqual(self.run_transport(1, cc | 32)[1:3], [0, expected])

    def test_local_source_accessory_states_not_accepted(self):
        for cc in (0, 2, 3, 4, 5):
            self.assertEqual(self.run_transport(1, cc)[1:3], [0, 0])

    def test_only_rd_and_open_allowed(self):
        self.assertEqual(self.run_transport(2, 0)[4], 0x88)
        self.assertEqual(self.run_transport(2, 2)[3:5], [0x45, 0x82])
        for cc in (1, 3, 4, 5):
            self.assertLess(self.run_transport(2, cc)[0], 0)

    def test_host_source_vconn_and_vbus_rejected(self):
        for role in (1, 2, 3):
            self.assertLess(self.run_transport(3, role)[0], 0)
        self.assertEqual(self.run_transport(3, 0)[0], 0)
        self.assertLess(self.run_transport(4, 1)[0], 0)
        self.assertLess(self.run_transport(5, 1)[0], 0)

    def test_fixed_request_voltage_and_current_guard(self):
        for index, ma, allowed in ((1, 1800, 1), (2, 1500, 1), (2, 3000, 0),
                                   (3, 1000, 0), (4, 1000, 0), (0, 1000, 0)):
            self.assertEqual(self.run_transport(6, (index << 16) | ma)[0], allowed)

    def test_rx_sop_delivered_and_cable_frames_ignored(self):
        self.assertEqual(self.run_transport(8, 0)[9], 1)
        for sop in (1, 2, 3):
            self.assertEqual(self.run_transport(8, sop)[9], 0)

    def test_cap_mismatch_does_not_exceed_source_operating_current(self):
        self.assertEqual(self.run_transport(15, 0)[0], 0)
        self.assertEqual(self.run_transport(15, 1)[0], 1)

    def test_rx_transfer_failures_do_not_deliver_partial_frames(self):
        for step in (1, 2, 3):
            self.assertEqual(self.run_transport(8, failure=step)[9], 0)

    def test_hard_reset_completion_and_error_precedence(self):
        self.assertEqual(self.run_transport(10)[6] & 4, 4)
        self.assertEqual(self.run_transport(9, 64)[10], 0)
        self.assertEqual(self.run_transport(9, 2 | 4)[10], 2)
        self.assertEqual(self.run_transport(9, 128)[10], 1)

    def test_failed_level_irq_clear_disables_irq_and_charge(self):
        r = self.run_transport(9, failure=1)
        self.assertEqual(r[7:9], [1, 1])
        self.assertEqual(r[11], 1)


if __name__ == "__main__":
    unittest.main()
