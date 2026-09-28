"""Execute the candidate's actual C policy helpers at safety boundaries."""

from pathlib import Path
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
DRIVER = ROOT / "kernel/drivers/sm5714-battery.c"


def function(source, marker):
    start = source.index(marker)
    opening = source.index("{", start)
    depth = 0
    for index in range(opening, len(source)):
        if source[index] == "{":
            depth += 1
        elif source[index] == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError(f"unclosed C function: {marker}")


class Stage1PolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = DRIVER.read_text()
        thermal = function(source, "static enum sm5714_charge_thermal_state\nsm5714_charge_thermal_state(")
        float_offset = function(source, "static u8 sm5714_batreg_offset(")
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        executable = Path(cls.temp.name) / "policy"
        code = Path(cls.temp.name) / "policy.c"
        code.write_text(
            "#include <stdio.h>\n#include <stdlib.h>\n"
            "typedef unsigned char u8;\n"
            "enum sm5714_charge_thermal_state { SM5714_THERMAL_NORMAL, "
            "SM5714_THERMAL_REDUCED, SM5714_THERMAL_STOP };\n"
            "struct sm5714_battery { enum sm5714_charge_thermal_state thermal_state; };\n"
            + thermal + "\n" + float_offset + "\n"
            "int main(int argc, char **argv) {\n"
            "  struct sm5714_battery sm;\n"
            "  if (argc != 3) return 2;\n"
            "  sm.thermal_state = atoi(argv[1]);\n"
            "  printf(\"%d %u\\n\", sm5714_charge_thermal_state(&sm, atoi(argv[2])), "
            "sm5714_batreg_offset(4440000));\n"
            "  return 0;\n}\n")
        subprocess.run(["cc", "-std=c11", "-Wall", "-Wextra", "-Werror",
                        str(code), "-o", str(executable)], check=True,
                       capture_output=True, text=True)
        cls.executable = executable

    def policy(self, old, temp):
        result = subprocess.run([str(self.executable), str(old), str(temp)],
                                check=True, capture_output=True, text=True)
        state, offset = map(int, result.stdout.split())
        self.assertEqual(offset, 0x2d, "4.44 V must encode to stock BATREG 0x2d")
        return state

    def test_cold_stop_and_hysteresis(self):
        self.assertEqual(self.policy(0, 99), 2)
        self.assertEqual(self.policy(2, 149), 2)
        self.assertEqual(self.policy(2, 150), 1)
        self.assertEqual(self.policy(1, 179), 1)
        self.assertEqual(self.policy(1, 180), 0)

    def test_warm_derate_and_hot_stop(self):
        self.assertEqual(self.policy(0, 419), 0)
        self.assertEqual(self.policy(0, 420), 1)
        self.assertEqual(self.policy(1, 499), 1)
        self.assertEqual(self.policy(1, 500), 2)
        self.assertEqual(self.policy(2, 460), 2)
        self.assertEqual(self.policy(2, 459), 1)


if __name__ == "__main__":
    unittest.main()
