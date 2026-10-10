# Read-only source/rail boundary after Test386

Accepted Test370 remains in boot d8654881-69bd-4603-92ee-8e14a3f81ad9.
No module, ADSP activation, firmware transfer, reboot or configuration write.
Latest ADB read at uptime996.72s: GDMactive, ADSPoffline, battery92%,33.0C,
reportedVBAT4.393V. This is current-state evidence, not another sensor test.

The original rail/pinctrl query returned status1 because its guessed
1500000.pinctrl path did not exist. Preserve that command/error. Separate native
path discovery found f100000.pinctrl; the later query succeeded on the sameboot.
Its ADSPoffline state means released hub4 pins are expected here; this does not
establish their behavior during sensor startup. GPIO22/23 remain owned by hub3
I2C at98c000, consistent with the passive charging topology; do not reclaim them.

Regulator summary reports vreg_l1b_1p8 use1/1800mV and vreg_l16b_3p0 use1/3000mV.
Current and same-model Fedora DTS retain those two sensor rails always-on. These
are software regulator state/readback values, **not physical voltage measurements**
or proof of DSP sensor power during startup. No disabled-rail repair is justified.

Fedora's current HEAD is still ab123e7d1dbc0cbcd35661f9761197e977b15aa9. Its three
RPC patches and ordered root/sensor-PD services are already imported; Test378
used that exact verbose transport. Current isolated registry ownership provides
fastrpc write access. Fedora's blanket chmod of stock persist is not needed and
was not copied. Its resume/restart helper is not an established firstboot fix.

New actionable source result is the real RPC empty-buffer codec defect, separately
qualified in ../ssc-rpc-wire/. No unknown selector/revision/electrical parameter,
oemconfig substitute, DIAG masks or hardware change. Existing wire traces do not
prove that defect was exercised. Sensor/rotation goal remains unfinished.

Tests here: executed:false (read-only evidence/source record). See the separate
wire qualification for44 actually executed affected tests and ARM64 results.
