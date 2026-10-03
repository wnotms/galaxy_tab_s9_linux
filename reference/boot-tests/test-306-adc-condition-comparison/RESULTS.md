# Test306 — offline registration and deployment preparation

**OFFLINE REGISTRATION / PACKAGE / RUNNER READY. Physical test not executed.**
Current battery recovery and device state are not confirmed. Last retained
Test299 observation was SOC0%, 3.145V, net discharge on PC SDP500mA; this is a
historical observation, not a new live reading. No device command, partition
write, module replacement, reboot, PPS request or pump enable occurred here.

The separately qualified Test305 kernel is unchanged. Its ARM64 build, W=1 /
sparse, protected-source audit, exact configuration/DT checks and1,749 unique
host qualification results are reused. New build and full-regression
`executed: false`; no zero-selection result is represented as a pass. Final
affected run executed51 tests (43 new gate/runner/package tests plus8 existing
thermal-runner tests), with no failure/error/skip. See the final log and summary
for measured duration. Python compilation and POSIX shell syntax checks passed.
Existing tests and test routing are unchanged; no GitHub Actions/CI was started.

`PACKAGE.json` records the offline boot-only package and accepted Test299
rollback. Unpacked boot payload matches qualified Image.gz + unchanged passive
DTB, header4,100663296-byte partition. All eight referenced candidate/rollback
artifacts were hash/size verified. Candidate config differs from accepted
Test299 only by `CONFIG_SM5440_ADC_CONDITION_TEST` absent -> y; DTB is identical.
Candidate and rollback manifests each contain181 paired files. Four other
partition hashes remain unchanged. No kernel/config/DT/build source changed
since the Test305 qualification.

Initial staging failed because a historical reference-directory mounting-helper
path did not exist. Preserve `validation/package-build.txt`. The repository
`scripts/twrp-mount-debian.sh` is byte-identical to the accepted Test292 helper
(SHA2563e2a14448333e3d08f4f720ec4a3a504381dc1f53770abc30675e917884ce6ca).
The corrected stage prevalidates every source and existing partial file before
copying. Drift, extra files and symlinks are refused; exact existing files are
retained. `--stage-only` verified/reused the already built boot instead of
regenerating it. Completion and staged-file seals are preserved. Windows files
are in `D:\android\gts9-active\gts9-test306`; no additional kernel cache or
full five-partition image bundle was created.

The independent runner checks baseline and candidate config hashes separately.
One fresh baseline preflight verifies allfive partition hashes,181 modules,
notes/config/cmdline, PC SDP500mA, DCC absence,4.44V design, real pack sensor and
rescue. Readiness polls only battery/cached snapshot/services/device NCM; the
full identity packet is collected once when ready. Kernel JSON, boot history,
Windows USB and a single host NCM probe are collected together. A bounded
host-only NCM timeout is recorded without a retry series; Code43 or device
rescue/identity/safety failure still stops.

One candidate startup conversion must supply explicit CNTL6 before/during/
restored validity and exact readback, a uniquely attributed ADC/gauge pair and
original OFF/fault evidence. Original preconversion REVBLK can remain pending
only under its unchanged classifier; no live fault is exempted. An initially
clear ENHIZ yields `NO_ENHIZ_CONDITION_CHANGE`, never proof of a fix. Cached
diagnostic data, smaller voltage difference and acquisition duration are not
calibration or a100ms physical charging grant.

After a15-second endpoint, or on first failure, restore accepted Test299 boot
and original181 files unconditionally. Cleanup tracking starts before the
first possible BCB request, including failure before any kernel write. Unknown
partition identity or missing rescue requires manual recovery and preserved
first-failure evidence; no blind write/reboot/repeated experiment. Manual
recovery can verify the restored baseline without inventing missing candidate
boot history. Test263 is not the rollback target: keep the accepted thermal fix.

`INPUTS.json` seals executable/registration/dependency inputs. Mutation requires
an unchanged committed registration with HEAD equal to origin/test, exact staged
files and a successful preflight no older than300seconds. This registration
does not waive the pending recharge or confirm the recent screen state.

Next: restore ordinary accepted18W charging and confirm safe battery recovery;
with PC data cable and charger absent, execute the registered one-boot comparison
once. No unchanged failed-profile replay or fresh ADC/calibration waiver.
Physical ADC validity, <=100ms freshness, active protection/OCP, actual PPS,
handoff/PM and direct-charge acceptance remain unresolved. Full Stage3 is
**NOT READY**; the complete wired charging port goal remains active.
