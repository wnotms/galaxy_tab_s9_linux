# Test370 — corrected GMU lifecycle and native EF-DX710 Escape

One independent corrected-kernel boot, followed by bounded ordinary GNOME use.
This is not a retry of Test366/368, an SSC discovery test, a USB reconnect pass,
or a charging experiment. Those STOP results remain immutable.

The candidate is the compiled/paired build recorded in
`reference/desktop-bringup/gmu-hfi-transport/`. It carries the complete upstream
GMU RPMh stop/shutdown fix, the already requested native Escape/grave swap and
the previously compiled native SoCinfo configuration. Linux stays 7.2-rc3,
HVC_DCC stays off, and UPower/OCI stay enabled. Only QCOM_SOCINFO differs in
resolved config versus accepted Test331. DTB and 181 module payloads are exact
matches to the preceding native-Escape build; no fresh kernel rebuild required.

Only **boot** and its matched 181-file module directory are replaced. Accepted
Test331 vendor_boot/init_boot/dtbo/vbmeta stay unchanged. No early ADSP firmware
image, late remoteproc start, sensor daemon, GPU performance change, USB helper,
adbd patch, PPS request, pump operation or charging-limit change.

## Registration and gates

Commit/push this registration and controlled inputs before reboot or mutation.
ADB remains `D:\android\platform-tools\adb.exe`; ephemeral Windows staging is
`D:\android\gts9-active\gts9-test370`. Do not touch old test stages/ledgers.
`host_flow.py verify` and `stage` are host-only; `preflight` is read-only.

Preflight requires accepted Test331 identity and boot, all five partition hashes,
181 exact module hashes and no build symlink, known original input files, empty
new overlay targets, ADB, authenticated Wi-Fi, device NCM, Windows without
Code43, no failed units, ordinary Sink/Device roles, pump disabled, battery
Good/present, SOC 20–85%, temperature 10–<42°C and VBAT 3.4–<4.44 V. Do not
repeat full unchanged hashes during each health sample.

The old boot's full kernel history is retained. Its Test368 errors remain faults,
not newly declared clean warnings. Corrective preflight may record at most 32
additional exact GMU BW-vote timeout/late-response pairs with matching IDs,
same-boot source metadata and ≤100 ms response separation. It requires every
previous Test368 row unchanged; unknown additions or CPU/panic faults stop.
This applies only to admission from the old faulty kernel into its source-backed
correction. **The candidate admits no GPU/HFI error**, including these pairs.
No old observer gate/count is altered. Ordinary accepted startup/SMMU/QCA
classification is reused separately with its existing bounds.

## One boot and GNOME sequence

1. Check fresh preflight and pushed source, then request TWRP once via the
   accepted recovery helper. Verify recovery identity and original partitions.
2. Install a ledger-backed six-file desktop/input overlay: exact native pen
   and palm modules/loaders, one text-admission flag and two temporary service
   conditions. Do not mask/change graphical.target or display-manager links.
3. Preserve original modules under `.gts9-test370-original`, verify/extract the
   release-root candidate archive, and write only registered boot with readback.
   The candidate's sole build symlink must point exactly to the current provider
   `.work/build/linux-out-x710-308-passive`; original modules permit no symlink.
4. Boot once. Wait ≤90 seconds for Debian, then prove a unique boot-ID/history
   transition, exact config/notes/partitions/modules, rescue and ADSP **offline**.
   Observe 30 seconds with text admission and collect complete raw kernel JSON.
5. On exact admitted kernel, remove only ms's interim XKB swap, remove the owned
   flag and start the existing native palm-pair/GNOME services. Verify both module
   objects and complete input inventory. Observe normal GNOME for 60 seconds;
   record GPU/GMU runtime PM counters, boot/thermal/rescue health and full kernel
   journal. The standalone pen unit may remain inactive because palm-pair loads
   both modules; do not enable the superseded standalone service.
6. Ask for actual login, Ctrl+Alt+T, plain Esc/Fn+Esc and touch/S Pen confirmation.
   Keep hardware verification separate from kernel/host qualification. On PASS,
   keep ordinary GNOME. USB unplug/reattach and sensors need separate evidence.

## Stop and exact rollback

Any new GPU/HFI/kernel/CPU fault, unexpected boot or identity, unsafe battery,
lost rescue, Code43, failed unit or evidence gap stops the scope. Persist the
first failure; do not flash or start the same candidate again to finish a count.
Recovery does not wait for a push.

Restore only the verified `.gts9-test370-original` slot and owned overlay backups,
then exact Test331 boot. Namespace-explicit recovery verifies original/candidate
file sets and exact build-link layout **before** rename or boot write, including
partial install where originals never moved. Preserve failed-boot journals
offline when available; do not turn collection errors into an invented PASS.
Verify all five restored partition hashes, 181 original files, original input
files, restore interim XKB on exact Test331, and return to normal GNOME.
If transport fails, request TWRP instead of issuing blind reboot loops. A manual
TWRP endpoint with missing history is an explicit attribution gap, not normal
restored Debian acceptance.

## Scope and remaining work

The existing compiled candidate is reused. Only new runner/transaction/parser
tests and source/package checks execute for this registration. No Actions or
exhaustive historical rerun. Exact executed coverage is in VALIDATION.json.

Test331 rollback is retained as an active Test370 consumer, including its
original five-partition identity and original input pair. The current retention
window is Test360–Test370; no new historical image copy is created for a round
number. GPU hardware result, native keys, permanent USB reconnect, SSC/rotation
and full port remain incomplete until their actual evidence exists.

## Corrected current ownership

Test369 STOP before mutation because it assumed the superseded standalone
/usr/local/libexec/gts9-pen existed. Current accepted root has no pen helper or
pen service: enabled gts9-palm loads both Wacom and FTS itself, with gts9-touch
disabled. Captured current hashes match palm helper and both original modules.
This independent registration owns only those three originals plus one text
flag and GDM/palm conditions (six files). No pen helper or pen drop-in is added.
Same already built kernel, observations, fault/identity/thermal gates and exact
rollback semantics. Test369 failure is not erased or retried.
