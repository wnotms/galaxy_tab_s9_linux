import copy
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import sm5714_pd_telemetry as telemetry


def sample(voltage=9000000, current=1500000):
    return telemetry.parse_sample(f'''SECTION meta
boot_id=d745248e-6a16-4243-b9cc-c5e6ede21fb2
uptime=100.0
SECTION battery
POWER_SUPPLY_VOLTAGE_NOW=4000000
POWER_SUPPLY_CURRENT_NOW={current}
POWER_SUPPLY_CAPACITY=61
POWER_SUPPLY_TEMP=300
POWER_SUPPLY_HEALTH=Good
POWER_SUPPLY_STATUS=Charging
SECTION usb
POWER_SUPPLY_ONLINE=1
POWER_SUPPLY_INPUT_CURRENT_LIMIT=1500000
POWER_SUPPLY_USB_TYPE=Unknown SDP DCP CDP [PD]
SECTION tcpm
POWER_SUPPLY_ONLINE=1
POWER_SUPPLY_VOLTAGE_NOW={voltage}
POWER_SUPPLY_CURRENT_NOW=1500000
POWER_SUPPLY_USB_TYPE=C [PD] PD_PPS PD_SPR_AVS
SECTION typec
power_role=[sink]
data_role=[device]
power_operation_mode=usb_power_delivery
''')


class SM5714PDTelemetryTests(unittest.TestCase):
    def test_battery_watts_use_actual_battery_readings(self):
        value = sample()
        self.assertEqual(value["battery_net_power_w"], 6)
        self.assertEqual(value["configured_input_ceiling_w"], 13.5)
        self.assertIsNone(value["measured_input_power_w"])

    def test_discharge_sign_not_inverted(self):
        self.assertEqual(sample(current=-1000000)["battery_net_power_w"], -4)

    def test_supported_but_inactive_pps_does_not_fail(self):
        self.assertIsNone(telemetry.assess(sample(), sample()["boot_id"]))

    def test_active_pps_stops(self):
        value = sample(); value["tcpm_type"] = "PD_PPS"
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "unsupported-active-pd-type")

    def test_contract_above_9v_stops(self):
        value = sample(voltage=12000000)
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "unsupported-contract-voltage")

    def test_battery_45c_stops(self):
        value = sample(); value["battery_temp_deciC"] = 450
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "battery-temperature")

    def test_rapid_temperature_increase_stops(self):
        previous = sample(); value = copy.deepcopy(previous)
        value.update(uptime_seconds=150, battery_temp_deciC=330)
        self.assertEqual(telemetry.assess(value, value["boot_id"], [previous]), "rapid-temperature-rise")

    def test_vbat_above_float_stops(self):
        value = sample(); value["battery_voltage_uv"] = 4440001
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "battery-voltage")

    def test_charge_current_exceeds_pack_policy_stops(self):
        value = sample(current=2100001)
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "battery-charge-current")

    def test_input_limit_cannot_exceed_9v_policy(self):
        value = sample(); value["input_current_limit_ua"] = 1800000
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "input-limit-exceeds-policy-or-grant")

    def test_input_limit_cannot_exceed_pd_grant(self):
        value = sample(); value["contract_current_ua"] = 1000000
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "input-limit-exceeds-policy-or-grant")

    def test_unplug_before_charge_is_not_contract_loss(self):
        value = sample(); value.update(usb_online=0, tcpm_online=0, contract_voltage_uv=0)
        self.assertIsNone(telemetry.assess(value, value["boot_id"]))
        self.assertEqual(telemetry.assess(value, value["boot_id"], attached=True), "charger-or-contract-lost")

    def test_boot_change_stops(self):
        self.assertEqual(telemetry.assess(sample(), "a" * 32), "boot-changed")

    def test_host_role_stops(self):
        value = sample(); value["data_role"] = "host"
        self.assertEqual(telemetry.assess(value, value["boot_id"]), "unexpected-role")

    def test_missing_sections_fail(self):
        with self.assertRaises(ValueError):
            telemetry.parse_sample("SECTION meta\nboot_id=a\n")

    def test_active_type_requires_brackets(self):
        with self.assertRaises(ValueError):
            telemetry.active_type("C PD PD_PPS")

    def test_summary_never_claims_measured_input_power(self):
        stats = telemetry.summarize([sample(), sample(current=1000000)])
        self.assertEqual(stats["battery_net_power_w"]["mean"], 5)
        self.assertFalse(stats["actual_input_power_measured"])
        self.assertFalse(stats["actual_vbus_independently_measured"])
