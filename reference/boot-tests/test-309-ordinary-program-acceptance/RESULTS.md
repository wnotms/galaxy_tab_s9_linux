# Test309 registration and offline runner qualification

Verdict: **STOP_COLLECTOR_AMBIGUOUS_I2C_ADDRESSES_ACCEPTED299_RESTORED**.
Kernel source `158d0dd376dac2770cd72582be1bd1fe2474e71d`; exact Test308 qualification reused.
Registration qualification required no device access. The two rejected
preflights below preceded the single physical candidate attempt. No new kernel
build/full regression, PPS request or pump activation occurred.

## Physical attempt and restoration

After the host path correction was committed/pushed, a fresh normal baseline
preflight passed allfive partitions/181 modules and live safety/identity gates.
Only candidate boot and paired modules were installed, with exact readback.
Candidate boot `766bce71-388b-4c96-9811-b301b6ff8fac` passed its identity,
boot attribution, pack thermal and device rescue checks. Its1063-row full kernel
journal has no matched CPU fault; the existing passive startup confirmation
refusal is separately recorded, not a physical ADC acceptance.

Stable-control collection failed before any I2C bus open: the observer required
global uniqueness of `*-0049`, but this board has both2-0049 and7-0049. The
actual battery provider is2-0049, bound to sm5714-battery with the expected OF
compatible. This is a collector assumption defect, not evidence of charger
register drift or CPU failure. The15-second endpoint was not completed and no
candidate acceptance is claimed. Source and failed collector remain sealed.

The registered first-failure path restored exact accepted299 boot and181
modules once, checked allfive partition hashes, cleared recovery request and
booted normally. Final boot `732d3733-2e87-422a-a9a6-e13e4202bfce` has43%,
3.823V,29.3°C, attributed history, expected config/notes, real pack thermal and
device ADB/NCM. Host NCM SSH returned255 and is reported separately. Complete
final journal has1065 rows and no matched CPU fault; existing passive refusal
remains explicit. `mutation-state.json` records rollback_required=false.

Do not replay Test309. A separately registered follow-up must select the
power_supply provider first, validate its bus alias/bound driver/compatible,
and tolerate unrelated same-address devices. It may reuse unchanged Test308
artifacts after new collector host tests; no kernel rebuild is necessary.

## Normal boot and host-only path correction

Owner confirmed normal power-on. New224ffde1-c182-4f8b-af83-412c3da5024e boot
matches the registered normal cmdline, accepted299 config/notes and live entry:
43%,3.826V,31°C. The second preflight stopped because the inherited partition
command used TWRP `/dev/block/by-name/` paths absent in Debian. Preserve every
parallel job's raw output in `preflight-rejected-02/`. No BCB or write occurred;
this host collection defect is not a CPU/charging failure or candidate boot.

The independent Test309 runner now reads Debian `/dev/disk/by-partlabel/` paths,
verifies each resolved block device's sysfs PARTNAME, and requires exactly five
unique valid hashes matching accepted values. Recovery aliases and historical
runners stay unchanged. No guessed disk numbers, alias creation or device-side
configuration.77 unique affected host tests passed with zero failure/error/skip,
including real shell/hash operations with fixture labels, missing/mislabelled
devices, incomplete/duplicate/wrong hash sets and mocked preflight routing.
The block-device predicate alone is mocked in host fixtures; physical preflight
uses the real predicate. Exact elapsed time/raw output are in
`validation/partition-namespace-host.json` and `.txt`.

Only runner/host test and registration metadata changed;114 source inputs are
resealed for this host correction. Qualified Test308 kernel/package/module
bytes are reused; no new kernel build/full regression or Actions. Commit/push
the correction, then execute a fresh successful preflight before deployment.

## First read-only preflight

Saved independently in `preflight-rejected-01/`, so a later fresh preflight
cannot overwrite this rejection. Current boot is
`e414c6df-d6d9-41e1-83d9-0aa5fbadf597`; its origin is not yet attributed to an
owner action. Battery recovered to46%,3.854V,31.9°C,Good/present, with the real
pack thermal zone enabled. USB is SDP/online with500mA input limit; ADB responds,
device usb0 is up at169.254.42.1 and Wi-Fi is10.139.153.81. Charging status with
negative gauge current means the pack was net discharging in this sample; it
does not prove a charging failure or measure input power.

Embedded config/notes match accepted299, but runtime cmdline still carries
vendor `lpcharge=1` parameters and fails the exact registered normal-cmdline
gate. The runner stopped there, before full partition/module hashing or any
mutation. Do not treat matching notes/config as full baseline acceptance.
The follow-up incident capture is read-only:1106 same-boot kernel JSON rows,
journal boot history and real-pack thermal state. The existing classifier
reports no matched CPU/kernel fault or new suspect; known startup display
diagnostics are preserved, not erased or claimed resolved. This is neither
Test309 candidate acceptance nor a stability proof.

Requested next action: boot normally with the cable disconnected, then reconnect
PC USB and run a fresh preflight. No automatic reboot was issued. New boot
history must be attributed before candidate deployment. Offline qualification
and the registered scope remain unchanged; `executed: false` for additional
host tests/builds in this evidence-only update.

One ordinary PC-USB candidate boot /15-second endpoint is registered, with
actual stable charger controls, real pack sensor, unique boot/full JSON journal,
source/config/notes/DCC/rescue gates. Matching controls and AICL-lowered input
are accepted; no artificial hardware fault/reset is triggered. At most one
natural programming mismatch must have one verified recovery within5s; a second
or failed recovery stops. See README.md and registration.json for scope.

73 unique affected host tests passed,0.192s, zero failure/error/skip.
30 Test309 tests execute the new parser, seven atomic read operations and mocked
lifecycle, including unsafe live/rollback entry, first-failure restoration,
no retry, retention on PASS, post-acceptance host-record failure without reflash,
source/stage/archive drift, observed AICL reduction, real Test307 bad control
values, boot history/Code43/CPU fault and exact provider/FD cleanup.43 unchanged
Test306 gate/runner tests were also executed; their original behavior remains.
No routing change or test retirement. Python syntax and POSIX module-swap syntax
passed.114 sealed inputs/7 staging files were checked without device access.

Boot-only package was built from qualified Image.gz+byte-identical DTB and
unpacked back to exact payload/header4.181 candidate and rollback module files
are independently represented in archive/manifests. Only boot is a write target;
otherfour hashes stay registered. Exact accepted299 rollback is retained and
new309 module backup slots keep pair identity. No full-five-partition bundle,
rootfs/USB/config service modification or observer load was introduced.

Candidate boot: `f4efa07e88ca3bc012b373827529fe4f92f35105e0040623da6486f1509fdacb`.
Rollback boot: `ea7f2da99c5d0ba71fdb76d38a81bfb044498938a75feae9c76502f0708eb8af`.
Windows stage: `D:\android\gts9-active\gts9-test309`,
248695976 bytes (~238MiB),7 files. Windows ADB remains at
`D:\android\platform-tools\adb.exe`. Input/provenance/module manifests,
package/header verification and exact hashes are preserved in this directory.

No device completion is claimed. The new sample supersedes Test307's critical
battery observation for current state, but does not satisfy normal-cmdline
identity. Run another preflight after normal boot is confirmed; mutation still
requires pushed registration and every actual safety/identity gate.
A host-only completion recording error after all device gates pass does not
cause automatic rollback; an actual device/evidence gap still stops.

A passed Test309 can retain the ordinary recovery fix. It does not establish
physical ADC validity, active OCP, PPS/direct handoff or PM acceptance. Subsequent
fixed9V and ADC/PPS scopes must be registered independently. Full Stage3 remains
**NOT READY** and the full porting goal remains active.
