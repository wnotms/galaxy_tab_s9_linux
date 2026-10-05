# X710 PC charging: use source-authorized 5V budget

Design before implementation. Owner reports low-battery shutdown after the last
PC observation (SDP500mA, negative pack current). This observation does not prove
that the computer can supply more current; port/cable/source capabilities remain
unknown. No device write or deployment is part of this offline increment.

## Defect and mainline mapping

Linux7.2-rc3 `tcpm_get_current_limit()` maps Rp1.5A/3A to the corresponding
current; default Rp uses our BC1.2 callback. `tcpm_set_current_limit()` sends the
voltage/current budget through the existing TCPC/battery companion callback.
The battery driver currently chooses SDP500 or UNKNOWN500 before taking the
minimum with that grant, losing higher valid 5V authorization. Its battery
current remains500mA too. A Type-C shape/cable/PC label alone is no authorization.

[VENDOR] `sec_bat_set_usb_configure()` applies Rp-level current votes alongside
USB enumeration; it separately distinguishes high/super speed and suspend.
[FEDORA] same-model `sm5714_configure_charging()` gives Type-C budget precedence,
but allows5V3A and battery2800/3150mA. We do not import those expanded ceilings,
thermal changes, fast-charge knob or Android voting framework. Exact source
excerpts/hashes: `reference/charging/x710-pc-current/source-references.json`.
[MAINLINE] stock TCPM remains protocol/current-authorization owner.
[MEASURED] Test307 raw same-boot journal already records fixed5V budgets3000
then1800mA alongside500/500 charging logs. This is a historical logical grant,
not current PC-port capability or measured input watts. Recovery tests formerly
modeled1800mA authorization while expecting500mA draw; retain those exact500mA
assertions with a default500 grant and add exact1800mA recovery/poller assertions.

## Bounded correction

After existing online/thermal/fault/ownership/PPS/suspend checks, a TCPM-owned
fixed5V budget above500mA takes precedence over MUIC classification. Input is
`min(grant_ma, SM5714_FIXED_5V_MA)`; the existing500/1500 battery target rises
only to that capped input current when lower. DCP's2100mA target remains2100;
9V input1500/battery2100 remains unchanged. Then the existing contract-minimum
and reduced-temperature500/500 clamp apply. No maximum is raised. Higher grant
than actual draw is recorded as a grant, not measured current or watts.

| Source authorization | Input ceiling | Battery target |
| --- | --- | --- |
| No Type-C owner/default SDP500 |500mA|500mA|
| Fixed5V grant900/1500 with SDP/unknown |grant, <=1800mA|same capped amount|
| Fixed5V grant3000 with SDP/unknown |1800mA|1800mA|
| DCP, including granted fixed5V |existing1800mA, bounded by grant|existing2100mA|
| Fixed9V |existing1500mA, bounded by grant|existing2100mA|
| Reduced thermal |<=500mA|<=500mA|
| Fault/detach/standby/suspend/PPS-owned switching |Q4 OFF|not enabled|

No USB3-only900mA entitlement is inferred: that would need its own enumeration
integration/authorization. Unknown/error temperature, I2C/readback faults, FULL,
AICL preservation,4.44V float, switching inhibition, generations and PM remain.
No new sysfs control, TCPM/USB/DWC3/adbd/config/DT change or pump/PPS activation.

## Tests/build and future physical scope

Reproduce the missing5V path in actual C before fixing it; test default SDP,
higher grants, caps/encoding, DCP/9V preservation, thermal/fault/OFF/suspend,
callback downgrade/detach and first-fault latch. Retain existing assertions.
Run affected suites only, one incremental same-profile ARM64 build with matched
modules, exact config/DTB and protected-file audit. Native grants remain closed.

Future separate physical candidate requires recharged SOC>=20%, normal boot and
rescue paths. Read raw Rp/current budget/MUIC/input programming/pack signed
current before choosing a test. If only SDP/default500 is authorized, do not
increase it or claim this fixes low-PC-power drain. For real higher5V grant,
verify bounded input and pack current/temperature, ADB/device-side NCM, grant
downgrade/unplug/reconnect, no kernel fault. Preserve accepted311 rollback.
No deployed higher-current claim from these host tests.

Offline qualification and outstanding physical scope: [results](../reference/charging/x710-pc-current/RESULTS.md).
