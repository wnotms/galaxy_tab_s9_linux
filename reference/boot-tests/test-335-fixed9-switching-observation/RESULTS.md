# Test335 — device scope complete, original entry stop retained

**Device acceptance PASS:** unchanged accepted Test331, same boot
`f1e9a45a55054b88ab05b969775657e9`, fixed9 ordinary switching≥30s then unplug/discharge≥15s.
The original runner remains STOP; no retrospective clean result.

| Stage | Observed seconds | Samples | VBAT | Pack temperature | Battery current |
|---|---:|---:|---|---|---|
| Fixed9 | 30.244 | 30 | [4124000, 4140000] µV | [251, 251] deci°C | [1636000, 2068000] µA |
| Unplug | 15.675 | 16 | [4050000, 4066000] µV | [249, 249] deci°C | [-828000, -540000] µA |

All admitted samples same boot, Good/present, thermistor enabled/agrees, pump
CNTL5=01 OFF, no PPS; fixed9 sink/device PD with input≤1.5A/source ceiling.
Both stages preserve full kernel JSON, source timestamps and empty failed-unit
list, no new severe kernel/error signal. Sampling gaps≤3s. No reboot, flash,
module/rootfs/kernel/config/DT/driver/USB/adbd/current/thermal policy change.
Exact config `51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a` and notes `03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95` unchanged.
All-five/181 pairing reused from same-boot Test334 final accepted331; not
rehashed on each sample. No rollback needed, accepted331 remains installed.

## First-stop attribution and completion

At uptime2036.29s, the first9V sample was Charging but still -0.473A/input0.5A.
The host falsely equated first9V with first healthy charging sample and stopped
before the30s window began. `charge/` and FIRST_STOP retain exact failure.
No kernel/pump/identity/pack fault was detected. At2089.36s, without another
attach/reboot/software change, healthy9V/1.5A, +1.436A/24.9°C was confirmed.
The exact settling/gauge-cache mechanism is not uniquely proven.

The published device-completion supplement then collected only the missing
first30s evidence on the existing connected source in `device-completion-charge/`,
using the sealed observer and unchanged safety gates. It did not rewrite the
first STOP or repeat a previously completed physical window. Only afterwards
owner unplugged once for the original15s discharge stage, separately archived.

## Coverage and limits

53 affected host tests PASS0.112s; no routing changes, build/full tests/Actions
`executed:false`, unchanged qualification reused. New discovery admitted the
known endpoint without a /24 scan; identity remained enrolled and bound.
Original335 registration/runtime sources stay sealed. Future observer entry
needs a bounded healthy-charge settling stage; do not instantly require positive
FG current on first negotiated9V, and retain all safety gates during settling.

Battery endpoint power was 8.437W
(VBAT×IBAT). The9V×1.5A budget13.5W is a ceiling, not measured charger input power.
No independent VBUS measurement, ADC calibration, PPS-to-fixed transition,
active pump/high-power/reliability/cold-boot acceptance or automatic advancement.
Test334's native proof remains valid and original transport STOP remains sealed.
Full charging port **NOT READY**; this bounded ordinary-charge scope is complete.

Expired Test325's exact Image/boot copies retired under326–335 retention,
releasing122,805,608bytes; current331/323/334 and all historical raw/source/hash
records retained. See host-storage-cleanup/2026-10-06-test335-image-retirement.
