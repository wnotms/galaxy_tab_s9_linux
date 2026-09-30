# Test262: ordinary fixed-PD charging on Test260 passive candidate

Owner authorizes "开始充电测试". One **SM5714 switching** charging observation,
using the previously supplied Lenovo YG65G USB-C2 18W PD source, C1 empty.
This does not authorize PPS, SM5440 pumpON, higher current, driver/config changes,
flashing/reboot, OTG, dock or Stage3 direct charging.

Current installed Test260 source6fbafede remains boot18bce160. Read-only live
identity/config/notes match Test260 acceptance, battery55%/28.1C/3.917V/Good,
passive SM5440 Good/Not charging/0A. Wi-Fi is now10.191.121.145. Reuse exact
Test260 pairing/partition/module/offline qualification from attempt02; no full
hash/build/test repetition. Fresh Wi-Fi authentication and complete initial
journal/safety gate precede the owner's plug action. Test255 rollback retained.

Publish registration first, start collector, then ask owner to disconnect PC USB
and attach the18W C2 source while retaining Wi-Fi and normal Debian boot. Capture
the transition; no separate baseline150s is repeated. Give observed source
45s for fixed5V/9V and matching fresh reported passive VBUS. PC SDP cannot start
the charging window. Waiting for physical attachment is bounded600s.

From stable independent charger state observe **300s**, combined telemetry/
roles/failed units/incremental source-timestamped journal each target5s. Complete
journal at boundaries/first failure. Retain Test260's single confirmed-inactive
startup warning; any new/repeated SM5440 fault/startup event stops. No retry.

Limits unchanged: fixed5V input<=1.8A, fixed9V input<=1.5A (13.5W configured
input ceiling), battery policy2.1A and float4.44V. Bring-up stop is more
conservative: pack>=42C, VBAT>=4.3V, rapid+3C/60s, SOCoutside5..<80, invalid/
stale telemetry, health notGood, active PPS/non5V9V contract, source/input limit
violation, SM5440 nonzeroIBUS/charging/unavailable health, die>=42C, reported
VBUS>9.5V, contract loss/reset/attach loop, I2C/kernel/CPU/service fault, unexpected
reboot or Wi-Fi loss. Final positive battery-current majority and nondecreasing
SOC are required. First fault stops and asks immediate charger disconnect;
preserve evidence, no automatic retry or parameter adjustment.

After pass ask owner to unplug; verify sameboot/offline/Discharging/negative
current, then return to PC for a fresh bounded ADB/NCM/Wi-Fi/noCode43 check.
No automatic20min extension, other charge level or Stage3 activation.

Power reporting: VBAT*IBAT is battery **net power**, not charger input power.
TCPM V/I is a contract and SM5714 ICL is a configured ceiling. SM5440 VBUS is
additional ADC telemetry, not independently calibrated. The previous absence
of an inline meter still applies; do not claim independently verified physical
voltage, actual18W draw, ADC calibration or OCP protection qualification.

Host-only runner/helper validation is affected tests + syntax, no routing change
or repeated kernel/full regression. Existing telemetry/parser behavior remains.
This accepts bounded ordinary charging only; ActiveStage3 remains NOT READY.

## Current execution status

Registration and read-only preflight only; charging collector has not started
and no charger connection has been requested. The owner reports repeated
Windows connection sounds on PC USB. Pause the charger transition while
capturing Windows PnP/device events and device-side USB/FunctionFS state under
`usb-chime-incident/`. Do not classify the sound alone as a CPU/charging fault
or repair USB configuration without an attributed failure.

Update after manual PC-USB replug: owner reports normal operation, fresh ADB,
NCM/Wi-Fi/sameboot/health gates pass. See `usb-chime-incident/RESULTS.md`.
Root cause remains unknown; the historical incident is retained, not relabeled
clean. No kernel/service/configuration change. Proceed to the registered
charging collector and attachment prompt; charging has not yet been observed.
