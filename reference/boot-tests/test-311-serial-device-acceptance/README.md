# Test311 — serial device evidence / ordinary program acceptance

Complete one normal Test308 ordinary-recovery candidate boot plus a 15-second
same-boot endpoint. Test310 stopped when its parallel boot-history query timed
out; exact Test299 was restored. The timeout cause remains UNKNOWN. Test309/310
failed results and source are immutable; this is a new registered attempt.

Reuse the exact qualified Test308 boot/config/notes/DTB and 181 matched modules.
No kernel/config/DTS/rootfs/USB/adbd/TCPM change, PPS request, pump activation,
ADC invocation, forced drift or current increase. Fixed 5V <= 1.8A, fixed 9V
<= 1.5A, 4.44V float and fail-closed pack thermal remain unchanged. No rebuild,
full regression, CI or Actions. This scope does not qualify active Stage3.

Collection order: fresh identity/rescue/pack state, actual provider-anchored
stable charger controls and real-pack thermal, full raw kernel journal and
fault classification, then one bounded boot-history query, Windows USB and one
host NCM probe. Device ADB operations are serial. History timeout is 20 seconds
(previously 10); device safety deadlines and 15-second endpoint are unchanged.
Missing history still refuses acceptance; no retry or attribution waiver.
Baseline full five-partition/181-module hashes run once before mutation. No
repeated endpoint partition/module audit. Host NCM failure is recorded separately
from mandatory device-side rescue/NCM gates. Controls/thermal are also checked
before baseline metadata and before the final journal; invalid controls stop.

The supply device, canonical I2C bus alias, address0049, bound driver and OF
compatible select the actual charger even when another bus also has0049. Seven
I2C_RDWR transfers only write a one-byte register pointer and read one byte; no
INT, register-data write or force mode. This unchanged Test310 collector must
succeed on baseline before any recovery request.

Entry requires a fresh normal accepted299 boot/config/notes; Good/present
battery, SOC5..<80, VBAT3.5..<4.3V, pack20..<38C, device rescue and PC Sink/Device.
Registration/exact inputs must be committed and pushed before BCB. Install only
boot and paired modules through native validated recovery, read back allfive/181,
clear BCB, then one normal candidate boot. Unique boot attribution, identity,
controls, thermal, journal and transport gates plus endpoint must all pass.
At most one spontaneous program recovery must finish within5s. First failure
stops and restores exact299 once if safe; unknown state needs manual recovery,
never blind retry. PASS retains the candidate. A later publication-only error
does not reflash a completed device scope. Test263 historical rollback is retired.

Windows stage: D:\android\gts9-active\gts9-test311. Six unchanged files are
hard links to Test310 stage; only the unique311 module helper is new. Hashes
are verified before transfer; hard links are not independent backups. No large
image/module copy or additional build tree. Historical evidence stays in WSL.

```sh
python3 reference/boot-tests/test-311-serial-device-acceptance/host_flow.py preflight
python3 reference/boot-tests/test-311-serial-device-acceptance/host_flow.py run
```

Physical Test311 is not executed in this registration. No fresh device state is
inferred from offline tests or the earlier Test310 final boot. New preflight is
required before a future authorized run.
