# Test269 — offline PPS operating-point update qualified

Qualified source: `19991d6c5671cc9faadcd0bd0f2b72058ac9ce4a`.
Implemented and compiled/host-tested; **not hardware-tested or activated**.
The device remains Test263; Test267 STOP and Test268 results are unchanged.

## What was ported

`x710_charge_retarget()` follows the same-model Fedora principle of recalculating
PPS voltage as measured VBAT changes and parking the pump across negotiation.
The existing Samsung-derived twice-VBAT + cable-drop + 200mV initial headroom
calculation is reused with source/board ceilings. This is a bounded operating-point
update, not a claim to port the vendor's complete CC/CV feedback or termination.
Source identities and provenance are in sources.json and X710_PPS_RETARGET.md.
Remote Fedora HEAD was checked and still equals audited `ab123e7d`.

Fresh facts are acquired with epoch/time/eligibility checks after verified OFF.
The old physical operating point is checked before installing the new target.
Fresh source approval precedes PPS Request; actual fresh VBUS verification follows
it. Pump current regulation is reprogrammed before ON, with fresh facts and
post-ON evidence. Shrinking source current can reduce the target; an expanded
source offer never automatically increases it. Every failure uses the existing
checked OFF/fixed/physical voltage/switching fallback and revokes authorization.
Failed OFF cannot permit a voltage change; lost epoch cannot restore an old
contract to a new attachment. All previous core assertions remain.

PPS bring-up cap stays 1.8A / 10.5V, not physically validated power or current.
Fixed charging stays 5V<=1.8A and 9V<=1.5A; float4440mV, thermal, DCC-off,
USB/ADB/NCM and Docker/UPower policies are unchanged. No live adapter, timer,
TCPC PPS permission, pump-enable hardware operation or fresh-ADC API was added.
No device command, flash, reboot, current increase or fault-latch clearing occurred.

## Validation

| Check | Result |
|---|---|
| Affected real-C transaction tests | 55 passed, including 17 new tests |
| Final full host suite | 1396 passed; zero failure/error/skip; 127.013s |
| Retention | All previous 1379 test IDs retained |
| ARM64 Image/DTB/modules build | Passed; clang/ccache/JOBS8, isolated269 output |
| W=1 / compatible sparse | Passed; unchanged object SHA; known upstream VDSO declaration warning only |
| Embedded config / notes / paired module archive | Match generated artifacts, 181 regular files |
| Protected files / frozen Stage2 images | All96 unchanged / retained intact |
| Docker/UPower / DCC | All85 required enabled symbols retained / HVC_DCC absent |
| Test263 → Test269 resolved config | Only CONFIG_X710_CHARGING_POLICY=n→y |
| Test263 → Test269 DTB | Byte-identical; no property changes |

The generic charging audit also compares to Test255: its expected passive
SM5440 enable/status delta already existed in Test263, not a new Test269 DTS
change. The dedicated test263-to-test269 diffs establish this task's exact delta.
Image/DTB/config/notes/modules hashes are in ARTIFACTS.json. Output lives in
`out/kernel-x710-269-policy/`; no prior output was overwritten. An independent
build-directory copy reused compilation cache rather than rebuilding everything.

A development-only mock fixture indentation error was retained and corrected
before the final55/1396 test qualification. It was not a kernel/device fault.
Changed selection already covered all1396 IDs, so the final full run serves that
regression without another identical wrapper/changed execution. Results-only
commits reuse this exact qualification rather than rebuilding/retesting.

## Physical readiness and next stage

**Active high-power charging: NOT READY.** Old full-pack passive fault0x80,
fresh-ADC/nonzero-current accuracy, protection cutoff and live PM/lifetime adapter
are still unresolved. The stopped old snapshot is not live hardware evidence;
this core cannot repair it. No old failure result is reclassified.

See FUTURE_PHYSICAL_PLAN.md. First resolve those prerequisites and register a
separate candidate. The existing18W PD source label does not establish PPS/APDO
support. Do not negotiate PPS or start a pump based on that label, a compiled
helper or host mock success. This registration contains no hardware deployment.
