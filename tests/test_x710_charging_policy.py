"""Execute the real bounded C helpers and transport with mocked hardware only."""
import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest

import test_sm5714_stage2_pd as stage2

ROOT = Path(__file__).resolve().parents[1]


class RequestBoundsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        path = Path(cls.temp.name) / "bounds.c"
        path.write_text(r'''
#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>
typedef uint32_t u32;
typedef uint64_t u64;
#define BIT(n) (1U<<(n))
#define GENMASK(h,l) (((~0U)>>(31-(h))) & ((~0U)<<(l)))
#define min(x,y) ((x)<(y)?(x):(y))
#define PD_MAX_PAYLOAD 7
#define PDO_TYPE_FIXED 0
#define RDO_CAP_MISMATCH BIT(26)
static unsigned int rdo_index(u32 r) {return (r>>28)&7;}
static unsigned int rdo_op_current(u32 r) {return ((r>>10)&1023)*10;}
static unsigned int rdo_max_current(u32 r) {return (r&1023)*10;}
static unsigned int pdo_type(u32 p) {return p>>30;}
static unsigned int pdo_fixed_voltage(u32 p) {return ((p>>10)&1023)*50;}
static unsigned int pdo_max_current(u32 p) {return (p&1023)*10;}
''' + '\n#include "' + str(ROOT / "kernel/drivers/sm5714-pd-policy.h") + '"\n' + r'''
int validate(u32 pdo,u32 rdo,int allow,unsigned int count) {
 u32 offers[7]={pdo};return sm5714_validate_request(offers,count,rdo,allow);
}
''')
        binary = Path(cls.temp.name) / "bounds.so"
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror", "-shared",
                        "-fPIC", str(path), "-o", str(binary)], check=True,
                       capture_output=True, text=True)
        cls.lib = ctypes.CDLL(str(binary))
        cls.lib.validate.argtypes = [ctypes.c_uint32, ctypes.c_uint32,
                                     ctypes.c_int, ctypes.c_uint]

    @staticmethod
    def fixed(mv=9000, ma=3000):
        return ((mv // 50) << 10) | (ma // 10)

    @staticmethod
    def pps(low=3300, high=11000, ma=3000):
        return (3 << 30) | ((high // 100) << 17) | ((low // 100) << 8) | (ma // 50)

    @staticmethod
    def rdo(mv=8800, ma=1800, index=1):
        return (index << 28) | ((mv // 20) << 9) | (ma // 50)

    def valid(self, pdo, rdo, allow=True, count=1):
        return bool(self.lib.validate(pdo, rdo, allow, count))

    def test_accepted_fixed_limits_preserved(self):
        for mv, cap in ((5000, 1800), (9000, 1500)):
            for ma in (100, 500, cap):
                rdo = (1 << 28) | ((ma // 10) << 10) | (ma // 10)
                self.assertTrue(self.valid(self.fixed(mv), rdo, False))
            rdo = (1 << 28) | (((cap + 10) // 10) << 10) | ((cap + 10) // 10)
            self.assertFalse(self.valid(self.fixed(mv), rdo, False))

    def test_fixed_reserved_giveback_epr_and_zero_rejected(self):
        good = (1 << 28) | (150 << 10) | 150
        for bit in (20, 21, 22, 27, 31):
            self.assertFalse(self.valid(self.fixed(), good | (1 << bit)))
        self.assertFalse(self.valid(self.fixed(), 1 << 28))
        self.assertFalse(self.valid(self.fixed(), (1 << 28) | (150 << 10) | 149))

    def test_fixed_cap_mismatch_respects_operating_offer(self):
        rdo = (1 << 28) | (50 << 10) | 180
        self.assertFalse(self.valid(self.fixed(5000, 500), rdo))
        self.assertTrue(self.valid(self.fixed(5000, 500), rdo | (1 << 26)))
        self.assertFalse(self.valid(self.fixed(5000, 500), rdo | (1 << 26) | (1 << 10)))

    def test_pps_default_deny_and_guarded_future_allow(self):
        self.assertFalse(self.valid(self.pps(), self.rdo(), False))
        self.assertTrue(self.valid(self.pps(), self.rdo()))

    def test_object_position_and_count_rejected(self):
        for index in (0, 2, 7, 8):
            self.assertFalse(self.valid(self.pps(), self.rdo(index=index)))
        for count in (0, 8, 100):
            self.assertFalse(self.valid(self.pps(), self.rdo(), count=count))

    def test_pps_voltage_source_and_board_boundaries(self):
        for mv in (8200, 8220, 9000, 10500):
            self.assertTrue(self.valid(self.pps(), self.rdo(mv=mv)))
        for mv in (0, 8180, 10520, 12000, 20000):
            self.assertFalse(self.valid(self.pps(), self.rdo(mv=mv)))
        self.assertFalse(self.valid(self.pps(low=9000), self.rdo(mv=8800)))
        self.assertFalse(self.valid(self.pps(high=8500), self.rdo(mv=8800)))
        self.assertFalse(self.valid(self.pps(low=9000, high=8500), self.rdo()))

    def test_pps_current_source_and_board_boundaries(self):
        for ma in (50, 1000, 1750, 1800):
            self.assertTrue(self.valid(self.pps(), self.rdo(ma=ma)))
        for ma in (0, 1850, 3000):
            self.assertFalse(self.valid(self.pps(), self.rdo(ma=ma)))
        self.assertFalse(self.valid(self.pps(ma=1500), self.rdo(ma=1800)))
        self.assertFalse(self.valid(self.pps(ma=0), self.rdo()))

    def test_avs_epr_and_reserved_encodings_rejected(self):
        for bit in (7, 16, 25, 26, 28, 29):
            self.assertFalse(self.valid(self.pps() | (1 << bit), self.rdo()))
        for bit in (7, 8, 20, 21, 22, 27, 31):
            self.assertFalse(self.valid(self.pps(), self.rdo() | (1 << bit)))
        self.assertTrue(self.valid(self.pps() | (1 << 27), self.rdo()))


class SourceLifetimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stage2.Stage2TransportTests.setUpClass.__func__(cls)

    def run_transport(self, *args, **kwargs):
        return stage2.Stage2TransportTests.run_transport(self, *args, **kwargs)

    def test_init_open_rxoff_resets_fault_and_new_attach_invalidate(self):
        for transition in range(11):
            with self.subTest(transition=transition):
                state = self.run_transport(16, transition)
                self.assertEqual(state[14], 0)
                self.assertGreater(state[15], 0)
                self.assertEqual(state[16], 0)

    def test_detach_and_hard_reset_drop_simultaneous_old_rx(self):
        for event in range(3):
            state = self.run_transport(17, event)
            self.assertEqual(state[9], 0)
            self.assertEqual(state[14], 0)
            self.assertEqual(state[16], 0)

    def test_extended_request_never_written_and_latches_off(self):
        state = self.run_transport(18)
        self.assertLess(state[0], 0)
        self.assertEqual(state[7:9], [1, 1])
        self.assertEqual(state[14], 0)
