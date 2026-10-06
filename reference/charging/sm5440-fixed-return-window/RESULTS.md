# Fixed-PD return gate — offline qualification

2026-10-06. Source commit `9901200d`; last accepted hardware remains Test331.

## Correction and boundaries

The former ±100mV nominal check was tighter than the fixed-PDO steady-state
source range. USB-IF r3.2 v1.2 Table4.6 defines vSrcNew as nominal×0.95–1.05
at the source receptacle. The source document and exact Samsung/Fedora input
hashes are in [SOURCES.json](SOURCES.json), rationale in [PLAN.md](PLAN.md).

The physical producer and source-bound release now share a helper accepting
only fixed5V4.75–5.25V and fixed9V8.55–9.45V inclusive. The upper9V boundary
remains below9.5V. This is a sensor-based board gate using the steady-state
numeric window, not source compliance certification or ADC calibration.
No additional transient allowance, voltage offset or fabricated proof is used.

The Fedora producer additionally requires three consecutive zero-raw-IBUS
observations over≥100ms, entire minimum/maximum range≤100mV. Invalid/current
or unstable readings reset the qualifying interval. Thirty polls remain the
limit. Repeated register observations do not prove independent ADC conversions.
Native release still independently checks exact source/instance/budget/lease,
logical fixed contract, checked pump OFF, zero pump current, proof age≤100ms
and unchanged try-only lock ordering. No proof structure or companion ABI change.
Other native consumers retain their own stricter existing producer checks.

Actual-C regression now accepts stable9.272V under those conditions and rejects
9.450001V,8.549999V, unsupported/overflow-sized nominal voltages, alternating
in-window voltage with120mV range, intermittent out-of-window readings, nonzero
fractional pump current, every return-I2C failure and connection replacement.
The old +272mV expectation is intentionally replaced for this documented policy
correction; original Test330 raw data/failure and Test331 results remain sealed.

## Executed validation

| Check | Result |
|---|---|
| Affected actual-C and observer/API consumers |248 PASS,5.748s; zero errors/failures/skips|
| Actual Fedora producer tests |28 included above; stability, boundaries, all return-I2C failures, OFF-only return/no PPS or ON|
| Actual source-bound release |7 included above; boundaries/overflow/identity/lease/age/provider faults|
| Standard ARM64 Image/DTB/modules build |PASS80.757s; existing incremental directory,J8/ccache|
| Affected Fedora/TCPC/battery-header objects W=1/sparse |PASS14.443s, zero warnings; standard qualified object bytes restored|
| Kernel pin |unchanged `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`|
| Resolved and embedded config |byte-identical Test331; hash51ba6a9c;85 required symbols including USER_NS/mqueue/SM5714/ADC5,HVC_DCC=n|
| Config relative accepted323 |same six existing alternative-profile differences; `config-from323.diff`|
| DTB |byte-identical Test331 and accepted323; hash233a9fee|
| Modules |181 matching files; runtime/layout/symbol qualification; archive byte-identical Test331|
| Protected sources/history |839 verified unchanged|
| Frozen formal/rollback artifacts |22 verified unchanged|
| Default-OFF boot package |header4/unpacked payload/partition size verified;167730dd prefix; `PACKAGE.json`/`SHA256.json`|

The build emits the same four pre-existing defconfig/fragment warnings as the
Test331 build (BASE_SMALL, two boot panic defaults, console reassignment); no
new build warning. Exact resolved identity is unchanged. No full suite, routing
change, redundant changed/wrapper run, Actions or physical mutation. Existing
unaffected qualifications are reused, not reported as newly executed passes.
Build/package ran once; compiled sources match committed `9901200d` exactly.

Only `sm5440-fedora.c`, `sm5714_usbpd.c` and shared `sm5714-stage2.h` change
kernel behavior. No ADC arithmetic/init, fixed/PPS current or entry threshold,
SM5714 battery policy, float4.44V/thermal, config,DTS,TCPM,DWC3/gadget,adbd,
rootfs,CPU,Wi-Fi or Bluetooth change. PPS cap remains1.8A, fixed5V≤1.8A,
fixed9V≤1.5A. Default direct charging remains OFF.

## Device status and next scope

A grouped read-only ADB capture plus checked pump-register read confirms the
same Test331 boot6b76a591, exactconfig/notes, Sink/Device, activeADB/SSH/NCM
services, no failed unit, direct_charge=N and CNTL5=01/OFF. Endpoint67%,
VBAT4.116V,pack32.3°C,current+1.239A, ordinaryPC input ceiling1.8A.
No flash,reboot,module replacement,PPS request or pump enable occurred.
One initial host parser helper lookup failed; raw capture was preserved and the
same existing Test331 admission passed after local section parsing correction.
This read-only capture is not physical acceptance of the new candidate.

The new candidate is **OFFLINE_FIXED_RETURN_WINDOW_PASS**, physical untested;
full charging port remains **NOT_READY**. It does not resolve or calibrate the
previous PPS requested-versus-measured voltage difference. PPS startup settling
and all thermal/current/fault gates still apply unchanged.

Next physical question: prove an actual pump-OFF fixed9V return with fresh ADC
and switching lease release under the corrected stability window. Register and
push a separate OFF-only control/observation scope before device mutation;
no repeated unchanged Test330 run, automatic PPS/pump activation or current
increase. If that passes, independently register the bounded1.8A PPS trial.
Keep exact accepted323 boot/archive plus current `.gts9-test331-original` paired
rollback; do not reuse the consumed `.gts9-test327-original` slot.
