"""Fault injection against the actual C ordinary-charge control sequence."""

from pathlib import Path
import subprocess
import tempfile
import unittest

from test_sm5714_policy import function

ROOT = Path(__file__).resolve().parents[1]


class ChargeSafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = (ROOT / "kernel/drivers/sm5714-battery.c").read_text()
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.binary = Path(cls.temp.name) / "charge"
        definitions = "\n".join(line for line in source.splitlines()
                                if line.startswith("#define SM5714_CHG_") or
                                line.startswith("#define  SM5714_CHG_"))
        helpers = [
            "static int sm5714_chg_update_bits(",
            "static int sm5714_disable_charging(",
            "static u8 sm5714_batreg_offset(",
            "static int sm5714_set_float_voltage(",
            "static int sm5714_charge_fault(",
            "static u8 sm5714_input_current_reg(",
            "static u8 sm5714_fast_current_reg(",
            "static enum sm5714_charge_thermal_state\nsm5714_charge_thermal_state(",
            "static int sm5714_configure_charging(",
        ]
        harness = r'''
#include <stdio.h>
#include <stdlib.h>
#include <errno.h>
#include <stdbool.h>
typedef unsigned char u8;
#define BIT(n) (1U << (n))
#define GENMASK(h,l) (((~0U) >> (31 - (h))) & ((~0U) << (l)))
static unsigned int clamp_val(unsigned int v, unsigned int l, unsigned int h) {
  return v < l ? l : v > h ? h : v;
}
#define min(a,b) ((a)<(b)?(a):(b))
#define DIV_ROUND_UP(n,d) (((n)+(d)-1)/(d))
#define mutex_lock(x) ((void)(x))
#define mutex_unlock(x) ((void)(x))
#define usleep_range(a,b) ((void)(a), (void)(b))
#define dev_warn_ratelimited(...) ((void)0)
#define dev_err_ratelimited(...) ((void)0)
#define dev_info(...) ((void)0)
enum { POWER_SUPPLY_USB_TYPE_UNKNOWN, POWER_SUPPLY_USB_TYPE_SDP,
       POWER_SUPPLY_USB_TYPE_DCP, POWER_SUPPLY_USB_TYPE_CDP, POWER_SUPPLY_USB_TYPE_PD };
enum { POWER_SUPPLY_STATUS_NOT_CHARGING, POWER_SUPPLY_STATUS_FULL };
enum sm5714_charge_thermal_state { SM5714_THERMAL_NORMAL,
       SM5714_THERMAL_REDUCED, SM5714_THERMAL_STOP };
struct sm5714_battery { int chg_lock, chg, dev, psy_usb, psy_bat; unsigned int float_uv;
       unsigned int typec_mv, typec_ma;
       bool typec_owned, typec_claimed, typec_charge, typec_fault, suspended;
       enum sm5714_charge_thermal_state thermal_state; };
static unsigned int regs[256];
static int mode, temp = 250, type, writes, temp_error;
static int i2c_smbus_read_byte_data(int c, u8 r) {
  (void)c;
  if (mode == 4 && r == 0x1a) return -EIO;
  return regs[r];
}
static int i2c_smbus_write_byte_data(int c, u8 r, u8 v) {
  (void)c; writes++;
  if ((mode == 1 && r == 0x18) || (mode == 2 && r == 0x1a) ||
      (mode == 3 && r == 0x15 && (v & 0x7f) != 16)) return -EIO;
  regs[r] = v; return 0;
}
static int sm5714_get_temp(struct sm5714_battery *sm, int *v) {
  (void)sm; *v = temp; return temp_error ? -EIO : 0;
}
static int sm5714_get_usb_type(struct sm5714_battery *sm) { (void)sm; return type; }
static int sm5714_get_online_raw(struct sm5714_battery *sm) { (void)sm; return 1; }
static int sm5714_get_status(struct sm5714_battery *sm) {
  (void)sm; return mode == 7 ? POWER_SUPPLY_STATUS_FULL : POWER_SUPPLY_STATUS_NOT_CHARGING;
}
'''
        harness += definitions + "\n" + "\n".join(function(source, m) for m in helpers)
        harness += r'''
int main(int argc, char **argv) {
  struct sm5714_battery sm = { .float_uv = 4440000 };
  if (argc != 4 && argc != 8) return 2;
  mode = atoi(argv[1]); type = atoi(argv[2]); temp = atoi(argv[3]);
  if (argc == 8) {
    sm.typec_owned = true; sm.typec_mv = atoi(argv[4]); sm.typec_ma = atoi(argv[5]);
    sm.typec_charge = atoi(argv[6]); sm.suspended = atoi(argv[7]);
  }
  regs[0x13] = 8; regs[0x15] = 0x80 | 120; regs[0x1a] = 0xc0;
  temp_error = mode == 5;
  if (mode == 6) regs[0x0d] |= 4;
  if (mode == 8) regs[0x0e] |= 128;
  int result = sm5714_configure_charging(&sm);
  printf("%d %u %u %u %u %d\n", result, regs[0x13], regs[0x15],
         regs[0x18], regs[0x1a], writes);
  return 0;
}
'''
        code = Path(cls.temp.name) / "charge.c"
        code.write_text(harness)
        compiled = subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                                   str(code), "-o", str(cls.binary)],
                                  capture_output=True, text=True)
        if compiled.returncode:
            raise AssertionError(compiled.stderr)

    def run_charge(self, mode=0, usb_type=2, temp=250):
        result = subprocess.run([str(self.binary), str(mode), str(usb_type), str(temp)],
                                check=True, capture_output=True, text=True)
        return list(map(int, result.stdout.split()))

    def test_plain_dcp_programs_stock_limits_preserving_other_bits(self):
        result, q4, input_reg, battery_reg, float_reg, _ = self.run_charge()
        self.assertEqual(result, 0)
        self.assertEqual(q4 & 8, 8)
        self.assertEqual(input_reg, 0x80 | 68)  # 1800 mA, bit 7 retained
        self.assertEqual(battery_reg, 0x86)  # <=2100 mA
        self.assertEqual(float_reg, 0xc0 | 0x2d)  # 4440 mV, upper bits retained

    def test_unknown_source_stays_at_500ma(self):
        result = self.run_charge(usb_type=0)
        self.assertEqual(result[2] & 0x7f, 16)
        self.assertEqual(result[3], 32)

    def test_each_io_failure_keeps_q4_open(self):
        for mode in (1, 2, 3, 4):
            with self.subTest(mode=mode):
                result = self.run_charge(mode)
                self.assertLess(result[0], 0)
                self.assertEqual(result[1] & 8, 0)

    def test_missing_temperature_fault_and_full_never_enable_q4(self):
        for mode in (5, 6, 7, 8):
            with self.subTest(mode=mode):
                self.assertEqual(self.run_charge(mode)[1] & 8, 0)

    def test_cold_hot_and_warm_limits(self):
        for temp in (-10, 99, 500, 600):
            self.assertEqual(self.run_charge(temp=temp)[1] & 8, 0)
        for temp in (100, 179, 420, 499):
            self.assertEqual(self.run_charge(temp=temp)[2] & 0x7f, 16)


if __name__ == "__main__":
    unittest.main()
