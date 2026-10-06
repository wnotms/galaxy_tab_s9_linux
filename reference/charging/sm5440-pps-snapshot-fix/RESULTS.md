# PPS adapter fix — offline qualification

2026-10-06. Kernel source: `1f1d856858757c6d9082a4ccacc8de9de9b5cbed`. Current observer: `11e2ce1dc0f58333c4b2cbdb02883bb1192065b8`.
The source patch is kernel/drivers/sm5440-fedora.c;
its compiled bytes match that commit. Build ran before committing the reviewed
source; no later kernel-input change or second build was required. Raw build,
qualification and package stdout retain the precommit Git context; final
summary/package metadata names the verified committed kernel source.

## Corrected behavior

The final pack coherence read used the public fixed-only snapshot API during
PPS. Actual-C tests with the corrected mock reproduce -EAGAIN before the fix
(`before-fix-tests.txt`). Both coherence reads now use the existing owned PPS
API when PPS owns the lease; fixed charging still uses the public fixed API.
Lease, instance, connection/budget generation, pack and thermal checks remain.
Failure of either read or detach during the pack sample prevents pump enable.
This is a source-confirmed defect, not instruction tracing of the exact -11
reported in Test330.

`scripts/x710-pps-guard.py` retains the bounded observer and cleanup sequence.
Its fixed-return predicate uses ONLINE=1, not absence of advertised PPS
capability. It checks fixed9V voltage/min/max and coherent current≤1.5A,
then separately requires the SM5714 switching supply online/current≤1.5A.
ONLINE2/3, unknown/offline source, mismatched current, or inhibited switching
still fail. Raw Test330 fixed protocol samples are replayed; that classification
alone does not prove physical switching recovery. Historical Test328/Test330
files and verdicts are unchanged.

## Executed checks

| Check | Result |
|---|---|
| Affected tests |187 PASS, 6.296s, zero failures/errors/skips|
| Actual Fedora driver tests |19, included above; fixed-only mock, first/second owned failure, detach, +272mV return fault|
| Current observer tests |29, included above; inherited fault/window/OFF checks and new fixed-mode/raw replay|
| Standard ARM64 Image/DTB/modules |PASS, 83.454s, JOBS8/ccache/reused cache|
| Changed object W=1/sparse |PASS, 13.115s, no warnings; standard qualified object restored|
| Embedded/resolved config |Exact match; zero config delta from tested Fedora candidate|
| Accepted Test323 config |Only the same six previously qualified profile changes; `config-from323.diff`|
| DTB |Byte-identical to both Test323 and tested Fedora candidate|
| Module pairing |181 matching filenames; runtime ELF bytes/layout/symbols checked, new archive/BTF paired to this image|
| Protected sources and historical evidence |841 files verified unchanged|
| Frozen formal/rollback files |14 verified unchanged|
| Offline boot package |Header4, payload unpacked and verified, full partition size; `PACKAGE.json`|

No full suite, routing change, duplicate wrapper/changed run, Actions or device
commands. Existing unaffected qualifications are reused, not counted as new
passes. New build outputs are in `out/kernel-x710-fedora-snapshot-fix/` and
`out/boot-bundle-x710-fedora-snapshot-fix/`. Default direct charging remains OFF;
the compiled opt-in activation path exists and has **not** been device-tested
with this correction. Config85 required symbols, USER_NS/mqueue, SM5714/ADC5
and HVC_DCC=n remain intact.

No changes to Fedora ADC arithmetic/init, charge current, voltage/temperature
thresholds, DTS, SM5714 battery/TCPC, TCPM core, DWC3/gadget, adbd/rootfs or CPU
settings. Fixed5V≤1.8A, fixed9V≤1.5A, initial PPS1.8A, 4.44V float and thermal
fail-closed behavior remain unchanged.

## Remaining independent failure and next scope

Test330 fixed protocol returned9V/1.5A, but continuous ADC reported roughly
9.272–9.293V, outside the existing ±100mV/zero-raw-IBUS release proof. No meter
calibration distinguishes actual source voltage from measurement behavior.
The added +272mV C test still yields -ETIMEDOUT, pump OFF, lease held and
switching inhibited. Source-confirmed adapter/observer fixes do not resolve
this independent physical-proof timeout.

Same-model Fedora `ab123e7d`, `kernel/files/sm5440_direct.c`,
`sm5440_restore_switching()` only turns pump/ADC/watchdog off, requests fixed
ONLINE1 and returns the switching path. It does not provide independent VBUS
proof. Copying that fallback would weaken current recovery guarantees, so it
was not used to bypass this failure. No offset, fake READY or widened proof.

Before a new physical scope, decide a source-backed fixed-return verification
policy and how actual VBUS will be established. If a pump-OFF protocol/return
experiment is justified, register it separately with explicit OFF guarantee,
entry/stop bounds, fresh device rescue/identity gates and paired Test323 rollback.
Do not reuse a consumed `.gts9-test327-original` module slot. Do not restart
Test330, activate this candidate, or raise current merely because these offline
checks pass. Journal fault delivery lag remains an observation limit; original
kernel timestamps are retained, no instantaneous guardian response claimed.

Last accepted device evidence remains Test323 restoration, boot67673895 in
Test330. This offline correction made no flash/reboot/partition/module/rootfs
change and claims no new live health check.

**Offline adapter qualification: PASS. Full direct-charge candidate: NOT_READY.**
