# Test310 — provider-anchored ordinary charging acceptance

Purpose: complete one normal Test308 ordinary-recovery candidate boot and a
15-second same-boot endpoint, using a corrected host-only register observer.
Test309 stopped before bus access and restored accepted299; its failed attempt
and collector remain immutable. This is a separate registered scope, not a
clean reclassification or replay of Test309.

Reuse the exact Test308 boot/config/notes/DTB/181-module package. No kernel,
DTS, configuration, charging limits, thermal policy, USB/ADB/rootfs or TCPM
change. Fixed5V<=1.8A/fixed9V<=1.5A,4.44V float and fail-closed pack thermal
remain unchanged. No PPS, pump, forced register drift, ADC request or current
increase. No new kernel build/full regression/Actions.

The battery supply's actual `device` is authoritative. Validate its numeric I2C
bus/address0049, canonical bus alias, bound sm5714-battery driver and OF
compatible before bus open. Other buses may have devices at0049. Seven stable
controls use only atomic one-byte pointer/write plus one-byte read; no register
data/INT access/force mode. Missing, misbound or inconsistent providers refuse
before I2C. The old unsafe global-uniqueness assumption is not reused.

Sequence and gates remain those registered in Test309's corrected host runner:
fresh normal accepted299 config/notes; battery Good/present,SOC5..<80,
3.5..<4.3V,20..<38°C; one allfive/181 baseline check, live rescue/role/real-pack
thermal/journal; committed/pushed exact inputs before BCB. Use the normal
recovery helper only after the corrected collector also succeeds against the
running baseline during preflight; this prevents discovering a host binding
defect only after flash. Use the normal
recovery helper, unique310 module slots, only boot+matched modules, allfive/181
readback, clear BCB, normal candidate boot. Verify unique attribution, actual
controls, full journal and essential device transport, then15-second endpoint.
No repeated startup window or full endpoint hashing. Host-only NCM probe
failure is recorded, not a substitute for the mandatory device NCM/ADB gates.

At most one spontaneous ordinary programming recovery must complete within5s;
otherwise stop. First actual device/evidence failure restores exact299 once
when safe; unknown state/lost rescue requires manual recovery, never blind
retry. Registered PASS retains the candidate; a later host recording error
does not reflash a completed device scope. Physical ADC, active OCP/PPS/pump,
handoff and PM acceptance remain outside this ordinary scope.

Windows stage is `D:\android\gts9-active\gts9-test310`. Six unchanged files
hard-link the existing309 staging files; only the unique310 module helper is
new. Verify content hashes before transfer; hard links are not independent
backups. No repeated large image/module copy or build tree is created. Accepted
299 is the current running baseline and this scope's exact rollback.

```sh
python3 reference/boot-tests/test-310-ordinary-provider-acceptance/host_flow.py preflight
python3 reference/boot-tests/test-310-ordinary-provider-acceptance/host_flow.py run
```

Registration must be committed and pushed to origin/test before physical run.
