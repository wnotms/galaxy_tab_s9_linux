# Test309 registration and offline runner qualification

Verdict: **REGISTRATION_RUNNER_AND_PACKAGE_READY_PHYSICAL_NOT_EXECUTED**.
Kernel source `158d0dd376dac2770cd72582be1bd1fe2474e71d`; exact Test308 qualification reused.
No new kernel build/full regression, device command, preflight, reboot or flash.

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

No device completion is claimed. Last known Test3070%/2.775V/Not charging and
lpcharge=1 cannot satisfy entry. A fresh request for present charger/displayed
SOC/running state is pending; do not interpret elapsed time as recharge proof.
Run preflight only after owner confirmation, and mutation only after this
registration is committed/pushed and every actual safety/identity gate passes.
A host-only completion recording error after all device gates pass does not
cause automatic rollback; an actual device/evidence gap still stops.

A passed Test309 can retain the ordinary recovery fix. It does not establish
physical ADC validity, active OCP, PPS/direct handoff or PM acceptance. Subsequent
fixed9V and ADC/PPS scopes must be registered independently. Full Stage3 remains
**NOT READY** and the full porting goal remains active.
