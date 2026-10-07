# Test336 — single pump-OFF PPS / fixed9 roundtrip

Registration and host workflow only. **No physical execution or PPS request has
occurred.** Execution needs the owner's explicit Test336 PPS-OFF scope and a
fresh accepted331 PC preflight. This registration does not enable direct charge.

The only question is whether the qualified candidate can complete one owned PPS
transaction at 1.8A with SM5440 OFF, prove its physical ADC envelope, return to
fixed9 with native physical proof/lease release, and resume ordinary SM5714
switching charging. A successful owned API call may contain multiple TCPM PD
Requests; this is not a single-wire-frame test.

## Frozen inputs and unchanged limits

Candidate source `4d058527fe437b21d381d25fd336278a3aed9e94`, boot `ffb7bc94…`,
notes `59a97374…`, paired181 files, sole opt-in
`sm5440_fedora.pps_return_check=1`. Exact hashes/paths are in PACKAGE.json.
Reuse the qualified artifacts in
`reference/charging/sm5440-pps-off-return/`; no new kernel build.

Rollback is accepted331 boot `025ebea4…`, notes `03c9c46e…`, paired181 files.
All four non-boot partitions stay unchanged. No changes to config, DTS, drivers,
rootfs, Test253 ADB, USB gadget, CPU, float4.44V or thermal fail-closed policy.
Ordinary fixed5≤1.8A/fixed9≤1.5A remain distinct from the 1.8A PPS-OFF request.
No pump ON, retries, PPS keepalive, higher-current progression or hot testing.

Prep SOC20–75, native/observer SOC20–<80, VBAT3.5–<4.3V, actual pack20–<38°C.
PPS request target8.2–10.5V in20mV steps; native measured≤10.8V and within the
existing ±500mV envelope,≥3 samples/≥100ms/whole range≤100mV/rawIBUS0/OFF.
Fixed return physical8.55–9.45V/≥3 samples/≥100ms/range≤100mV/rawIBUS0/OFF.
These internal ADC observations **are not independent VBUS calibration** or
measurements of charging watts. Source APDO CURRENT_MAX is not request current;
CURRENT_NOW is the TCPM negotiated request, not physical input current.

## Short physical sequence, after explicit authorization

Run `python3 reference/boot-tests/test-336-pps-off-roundtrip/host_flow.py ACTION`.
The runner refuses installation/admission/observation without an
`execution-scope.json` containing the concrete owner instruction, Test336,
PPS_OFF=true, pump_ON=false and frozen INPUTS.json digest. Do not create that
record merely because this plan was pushed. Restoration always remains allowed.

1. `verify`: local input/artifact hashes only. `stage`: after authorization,
   create only `D:/android/gts9-active/gts9-test336`. ADB itself stays at
   `/mnt/d/android/platform-tools/adb.exe`; no stage is created by import/verify.
2. `preflight`: one PC packet, pump CNTL5 atomic pointer/read, accepted kernel
   identity, allfive hashes/181 module files, full journal/boot history, Code0,
   device NCM/services and strict enrolled WiFi. Reuse the enrolled public key;
   never learn a replacement. Stop baseline drift; no automatic repair.
3. `install`: requires preflight≤600s and fresh live pack/boot boundary. TWRP
   verifies original layout, installs matched modules and boot, reads back
   allfive, clears BCB/unmounts, then **remains in TWRP**. No System boot here.
4. Owner removes PC USB, connects Lenovo YG65G USB-C1/C2 empty, selects System
   once. Do not boot first on C2/PC and consume the one-shot on a non-PPS source.
5. `admit`: recent enrolled IP then bounded private/24 lookup≤90s,16 TCP/2 SSH
   concurrency, TCP3s/SSH8s/shared deadline. Bind machine/config/notes and a
   uniquely attributed new boot. No unexpected extra boots or relaxed SSH keys.
6. `charge`: read-only WiFi observer. Native300s admission owns hardware actions;
   require complete ordered negotiated/sample/fixed-proof/release journal.
   Host WAIT_NATIVE≤240s/uptime≤330s, sample gap≤3s; after native completion
   require fixed9 immediately, allow status/current settling≤10s, then full30s
   healthy ordinary charging. The settling timer never resets; failures latch.
7. `discharge`: only after charge PASS; owner unplugs, same boot15s discharge
   confirmation. Source0/USB0/Discharging/negative current/OFF/pack must hold.
8. Owner returns PC. `restore` unconditionally restores accepted331 paired
   boot/modules/allfive, BCB/unmount, one attributed normal boot, final ADB,
   device NCM, strict WiFi, config/notes/cmdline/OFF flags/pump, full journal,
   failed units and exact181. Restore-only SOC can reach100%/VBAT≤4.44V; this
   does not relax candidate entry or thermal gates. `restore --from-recovery`
   is reserved for manually verified TWRP when online access was lost; missing
   candidate history is explicitly recorded and cannot become a series PASS.

## First STOP and evidence

Stop on first native primary/cleanup failure, duplicate/missing/malformed proof,
unexpected boot/identity/lease/source, pump ON, bad ADC/current/envelope, detach
during charge, bad pack/thermal, kernel fault, failed unit, transport/evidence
failure or Windows Code43. No next charging round and no automatic rearming.
If return/release is unknown, promptly unplug charger, preserve the first boot
journal, regain TWRP and restore331; never force a lease release.

Raw observer JSONL includes complete before/after kernel journals with source
timestamps and live kernel rows; failed collection preserves partial raw/stderr.
Per-phase verdicts never overwrite previous evidence. Native errors preserve
both primary and cleanup values in their original messages. Proposed result
summary must distinguish native transaction,30s charge,15s discharge and final
restoration. A physical PASS cannot be claimed until all four stages complete.

No old335 STOP is rewritten, no retrospective late endpoint is substituted for
the new30s window. The scope does not accept pump/high-power behavior, protection
limits, cold/power reliability or the complete charging port.

## Host verification and status

Tests exercise native-proof parsing, known335 pack fixtures with synthetic
clocks, PPS source/request ceilings, stop latches, settling/continuity, actual
observer with mocked I/O, strict host evidence parsing, forbidden automatic
installation and actual336 module transactions on temporary roots.
Affected host tests only; no routing change, full suite, build or Actions.
See host-qualification.json and RESULTS.md. Physical status: **NOT EXECUTED**.
