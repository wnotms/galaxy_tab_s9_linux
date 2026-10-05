"""Run the actual ordinary-program witness/recovery C against a register model."""
from pathlib import Path
import subprocess
import unittest

import test_sm5714_charge_safety as safety
from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class ProgramRecoveryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        safety.ChargeSafetyTests.setUpClass.__func__(cls)
        source = (ROOT / 'kernel/drivers/sm5714-battery.c').read_text()
        code = (Path(cls.temp.name) / 'charge.c').read_text().split('int main(')[0]
        code = code.replace('#include <stdbool.h>', '#include <stdbool.h>\n#include <assert.h>\n#include <stddef.h>')
        code = code.replace('static int mode, temp = 250, type, writes, temp_error;',
                            'static int mode, temp = 250, type, writes, temp_error, io, fail_at, silent, online=1;')
        code = code.replace('  (void)c;\n  if (mode == 4',
                            '  (void)c; if (++io == fail_at) return -EREMOTEIO;\n  if (mode == 4')
        code = code.replace('  (void)c; writes++;',
                            '  (void)c; writes++; if (++io == fail_at) return -EREMOTEIO;\n'
                            '  if (silent == r) return 0;')
        code = code.replace('(void)sm; return 1;', '(void)sm; return online;')
        code = code.replace('struct sm5714_battery { int chg_lock, chg, dev, psy_usb, psy_bat;',
                            'struct sm5714_battery { bool last_online; int last_status, last_capacity, last_usb_type; unsigned int poll_count; int chg_lock, chg, dev, psy_usb, psy_bat, poll_work;')
        code += function(source, 'static int sm5714_recover_programmed_charging(')
        code += r'''
struct work_struct { int dummy; };
#define to_delayed_work(x) (x)
#define container_of(x,t,m) ((t *)((char *)(x)-offsetof(t,m)))
#define msecs_to_jiffies(x) (x)
#define SM5714_CAPACITY_POLL_DIVIDER 10
#define SM5714_POLL_INTERVAL_MS 1000
#define power_supply_changed(x) ((void)(x))
#define schedule_delayed_work(x,y) ((void)(x),(void)(y))
static int sm5714_get_capacity(struct sm5714_battery *sm,int *v) {(void)sm;*v=52;return 0;}
'''
        code += function(source, 'static void sm5714_poll_work(')
        code += r'''
int main(int argc, char **argv) {
 assert(argc==3); int op=atoi(argv[1]),arg=atoi(argv[2]),ret=0;
 struct sm5714_battery sm={.float_uv=4440000,.typec_owned=true,
  .typec_charge=true,.typec_mv=5000,.typec_ma=1800};
 if((op==2 || op==22) && arg==500)sm.typec_ma=500;
 type=POWER_SUPPLY_USB_TYPE_SDP;
 regs[0x13]=0x64; regs[0x15]=0x80|68; regs[0x1a]=0xd5;
 assert(sm5714_configure_charging(&sm)==0);assert(sm.charge_programmed);
 writes=0;io=0;
 if(op==0)ret=sm5714_recover_programmed_charging(&sm);
 if(op==1) {regs[0x15]=0x80|8;ret=sm5714_recover_programmed_charging(&sm);}
 if(op>=2) {
  regs[0x13]=0x64;regs[0x15]=0x80|68;regs[0x18]=0x97;regs[0x1a]=0xd5;
  if(op==3)fail_at=arg;
  if(op==4)sm.suspended=true;
  if(op==5)sm.switching_inhibited=true;
  if(op==6)sm.typec_pps=true;
  if(op==7)sm.typec_charge=false;
  if(op==8)sm.typec_fault=true;
  if(op==9)sm.typec_ma=99;
  if(op==10)sm5714_disable_charging(&sm);
  if(op==11) {sm.typec_ma=300;}
  if(op==12)temp_error=1;
  if(op==13)regs[0x0d]=4;
  if(op==14)regs[0x0e]=128;
  if(op==15)temp=550;
  if(op==16)online=0;
  if(op==17)mode=7;
  if(op==18) {regs[0x13]|=8;silent=0x13;}
  if(op==19) silent=0x18;
  if(op==20)sm.typec_owned=false;
  if(op==21) {
   assert(sm5714_recover_programmed_charging(&sm)==1);
   regs[0x13]&=~8;writes=0;io=0;
  }
  if(op==22) {
   sm.last_online=true;sm.last_usb_type=type;sm.last_capacity=52;
   sm.last_status=POWER_SUPPLY_STATUS_NOT_CHARGING;sm.poll_count=1;
   sm5714_poll_work((struct work_struct *)&sm.poll_work);
   ret=sm.charge_programmed ? 1 : -1;
  }else ret=sm5714_recover_programmed_charging(&sm);
 }
 int recovery_io=io, recovery_writes=writes;
 if(op==21 || op==20) {
  assert(sm.charge_program_fault);type=POWER_SUPPLY_USB_TYPE_DCP;
  sm.typec_fault=false;sm.typec_charge=true;sm.typec_ma=1800;
  assert(sm5714_configure_charging(&sm)==0);assert(!(regs[0x13]&8));
 }
 printf("%d %u %u %u %u %d %d %d %d %d %d\n",ret,regs[0x13],regs[0x15],
  regs[0x18],regs[0x1a],recovery_writes,recovery_io,sm.charge_programmed,
  sm.charge_recovery_used,sm.charge_program_fault,sm.typec_fault);
 return 0;
}
'''
        # Non-Type-C fault case: force a second mismatch to test its independent latch.
        code = code.replace('if(op==20)sm.typec_owned=false;', '''if(op==20) {
 sm.typec_owned=false;assert(sm5714_recover_programmed_charging(&sm)==1);
 regs[0x13]&=~8;writes=0;io=0;
}''')
        path = Path(cls.temp.name) / 'recovery.c'
        path.write_text(code)
        cls.binary = Path(cls.temp.name) / 'recovery'
        subprocess.run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', str(path),
                        '-o', str(cls.binary)], check=True, capture_output=True, text=True)

    def run_case(self, op, arg=0):
        proc = subprocess.run([str(self.binary), str(op), str(arg)], check=True,
                              capture_output=True, text=True)
        return list(map(int, proc.stdout.split()))

    def test_unchanged_program_reads_four_controls_without_writes(self):
        r = self.run_case(0)
        self.assertEqual((r[0], r[5], r[6], r[7], r[8], r[9]), (0, 0, 4, 1, 0, 0))

    def test_aicl_lower_input_is_not_raised(self):
        r = self.run_case(1)
        self.assertEqual((r[0], r[2], r[5], r[8]), (0, 0x88, 0, 0))

    def test_test307_drift_restores_only_existing_sdp_limits_and_float(self):
        # Keep the original default-SDP assertions, and also exercise the
        # higher 5V grant actually present in Test307's TCPM journal.
        for grant, input_reg, fast_reg in ((500, 0x90, 0x20), (1800, 0xc4, 0x73)):
            with self.subTest(grant=grant):
                r = self.run_case(2, grant)
                self.assertEqual(r[:5], [1, 0x6c, input_reg, fast_reg, 0xed])
                self.assertEqual(r[7:10], [1, 1, 0])

    def test_every_recovery_transfer_error_stays_off_and_preserves_first_error(self):
        count = self.run_case(2)[6]
        for transfer in range(1, count + 1):
            with self.subTest(transfer=transfer):
                r = self.run_case(3, transfer)
                self.assertEqual(r[0], -121)
                self.assertEqual(r[1] & 8, 0)
                self.assertEqual(r[2] & 127, 0)
                self.assertEqual((r[7], r[9], r[10]), (0, 1, 1))

    def test_intentional_off_states_never_attempt_recovery(self):
        for op in range(4, 10):
            with self.subTest(op=op):
                r = self.run_case(op)
                self.assertEqual((r[0], r[5], r[6], r[8]), (0, 0, 0, 0))

    def test_deliberate_disable_invalidates_witness(self):
        r = self.run_case(10)
        self.assertEqual((r[0], r[7], r[8]), (0, 0, 0))

    def test_recovery_revalidates_contracted_source_budget(self):
        r = self.run_case(11)
        self.assertEqual((r[0], r[2] & 127, r[3]), (1, 8, 32))

    def test_fresh_sensor_ovp_watchdog_faults_fail_closed(self):
        for op in (12, 13, 14):
            with self.subTest(op=op):
                r = self.run_case(op)
                self.assertLess(r[0], 0)
                self.assertEqual((r[1] & 8, r[7], r[9], r[10]), (0, 0, 1, 1))

    def test_thermal_stop_and_full_are_intentional_off(self):
        for op in (15, 17):
            r = self.run_case(op)
            self.assertEqual((r[0], r[1] & 8, r[7], r[9]), (0, 0, 0, 0))

    def test_detach_during_recovery_refuses_old_program(self):
        r = self.run_case(16)
        self.assertLess(r[0], 0)
        self.assertEqual((r[1] & 8, r[7], r[9]), (0, 0, 1))

    def test_unacknowledged_off_is_not_claimed_safe(self):
        r = self.run_case(18)
        self.assertEqual((r[0], r[1] & 8, r[7], r[9]), (-5, 8, 0, 1))

    def test_silent_program_write_is_detected_by_readback(self):
        r = self.run_case(19)
        self.assertEqual((r[0], r[1] & 8, r[7], r[9]), (-117, 0, 0, 1))

    def test_second_drift_latches_across_future_configurations(self):
        r = self.run_case(21)
        self.assertEqual((r[0], r[1] & 8, r[7], r[8], r[9]), (-117, 0, 0, 1, 1))

    def test_non_typec_path_also_has_sticky_program_fault(self):
        r = self.run_case(20)
        self.assertEqual((r[0], r[1] & 8, r[9]), (-117, 0, 1))

    def test_actual_same_attach_poller_calls_recovery(self):
        for grant, input_reg, fast_reg in ((500, 0x90, 0x20), (1800, 0xc4, 0x73)):
            with self.subTest(grant=grant):
                r = self.run_case(22, grant)
                self.assertEqual(r[:5], [1, 0x6c, input_reg, fast_reg, 0xed])
                self.assertEqual(r[7:10], [1, 1, 0])


if __name__ == '__main__':
    unittest.main()
