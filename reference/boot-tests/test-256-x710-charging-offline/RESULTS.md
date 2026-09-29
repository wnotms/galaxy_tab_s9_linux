# Test256: offline X710 charging audit and staged implementation

Offline audit, fixed-path refactor, passive SM5440 monitor and default-inactive
transaction core are implemented and built. **Active PPS/direct-charge candidate:
NOT READY.** Full Samsung charging parity is not claimed. No tablet command,
flash/reboot/partition/module/rootfs change, PPS request or pump activation was
performed. Installed Test255 remains the last hardware-observed reference; its
current live state was not queried during this task.

Start `test` HEAD: `ebf4af1c098af1179c69d6f59dcdcb756d03e21a`.
Qualified final source: `61336aff` (subsequent record changes are documentation
and evidence only). Linux7.2-rc3 pin `a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
Fedora remote/local snapshot remains `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`.
Audit/design commit a9ab1daf preceded implementation. Commits are separate and
pushed only to origin/test; no CI/GitHub Actions/main merge.

## Vendor evidence and policy

The actual charging implementation is under Samsung `kernel_platform/msm-kernel`,
not just generic `common`. Kconfig/Makefiles/kalama-gki_defconfig/gts9wifi r02/r04
DTS connect SM5714 MFD, switching charger, gauge, MUIC, private PDIC engine,
sec_battery/sec_direct_charger, and SM5440 charger/CC-CV algorithm. See the
dependency graph and full three-way table in
[X710_VENDOR_CHARGING_AUDIT.md](../../../docs/X710_VENDOR_CHARGING_AUDIT.md).
The62 source hashes remain unchanged; no Samsung/Fedora source was edited.

Verified board mapping: hub8 charger0x49/gauge0x71/MUIC0x25;
hub9 PDIC0x33/GPIO133-low/400kHz; hub3 SM5440_0x63/400kHz/GPI DMA.
Do not substitute FIFO/PIO. Vendor framework votes/notifiers/private PD
state machine/extprops are not copied; stock TCPM remains the protocol owner.

Key distinctions and safety findings:

* Float4440mV is vendor CHGCNTL4 code45, preserved at probe/configure/readback.
  Frozen ordinary pack cap2100mA and fixed5V<=1800/9V<=1500mA remain.
* Vendor ordinary PD budget15W is distinct from45W fast policy and source3A
  capability. Current9V/1.5A is a13.5W policy ceiling, not measured input power.
* Vendor zones0/5/15/18/42/50°C have19-deci°C recovery modifications. Large
  aggregate zone-current votes must not become ordinary switching limits.
  The new zone helper is an audit model, not a replacement of frozen Stage1.
* Vendor manager direct admission is >18,<42°C, default endSOC95%, X710 DT
  minimumVBAT3400mV (generic3500, pump algorithm3300). Future bringup gates are
  narrower: SOC5..<80,VBAT3500..<4300mV,pack20..<38°C,die<55°C,<=1800mA.
* Vendor initial PPS is2*VBAT + I*320mohm +200mV. RTT320000uohm is traceable
  to X710 DTS, not measured cable resistance. Source/board caps and20mV/50mA
  steps apply; future8200..10500mV is separate from frozen fixed9V maximum.
* **Vendor explicitly needs software OCP**, with initialization disabling
  some hardware OCP/thermal protection. Active protection and worst-case fault
  response are unresolved. No blind0xF2/aggregate protection initialization.
* Fedora measured PPS-refresh REVBLK/TCPC I2C failure. No equivalent wired
  pump-OFF-before-every-refresh vendor sequence was found; bypass is excluded.
  Future refresh must preserve OFF -> PPS -> actual settled VBUS -> ON.
* Vendor pump PM callbacks only manage IRQs/wake; mainline must explicitly
  exit/drain direct operation before suspend. Wake locks are not that proof.
* SM5440 ADC map has no independently verified IBAT. ExactuV/uA conversion is
  implemented; pump-OFF ADC accuracy/validity remains physically unaccepted.
  Missing charger/USB/sub-pack sensors are not fabricated.
* Generated vendor9800mAh property conflicts with actual8400mAh typical /
  frozen8160mAh rated evidence; provenance is unresolved, capacity unchanged.

## Actual changes and implementation status

| Files / area | Result | Acceptance boundary |
| --- | --- | --- |
| Five design documents | vendor/Fedora/mainline mapping, registers, locks, handoff, physical plan | source audit, not hardware proof |
| sm5714-battery.c | consolidate latched Type-C inhibit; invalid contract also clears charge grant | normal fixed behavior retained; new image unaccepted |
| sm5714_usbpd.c / sm5714-pd-policy.h | bounded fixed/PPS Request validation; clear source offers on reset/detach/fault before stale RX; reject extended/malformed Requests | live dispatcher PPS authorization=false |
| sm5440-direct.c / sm5440-hw.h | ID/modeOFF check, new ADC completion, exact units, fault latch, read-only supply, bounded worker/PM teardown | no ON API/reset/protection init/Q4/PPS; not hardware-tested |
| x710-charging-policy.c/.h | default-inactive eligibility/target/epoch/transaction/fallback/refresh core, real C mock faults | no live adapter/worker/TCPM consumer/PM wiring |
| profile fragments / patches / isolated DTS / binding / build gates | explicit passive or policy-offline build only | primary SM5440 remains disabled; no default APDO |
| three new test files, retained Stage2 test fixture, artifact/profile audit scripts |39 additional executable host tests; real getter/poller coverage | no tests deleted/skipped/assertions weakened |

The original independent claimed/owned/charge/fault/suspend booleans were retained;
one enum would lose independent safety gates. No large generic policy framework.
Lock/lifetime contract is in X710_CHARGING_ARCHITECTURE.md: no charger/transport
lock across PPS/ADC waits; serialized ownership and epoch checks in the future
adapter; passive worker drains before managed resources free. Unknown OFF means
FAULT/inhibited, not a successful fallback or voltage change.

Host mocks cover malformed/fixed/APDO/EPR bounds, resets/detach/cache invalidation,
ADC timing/endianness/units, every transfer failure, thermal/SOC/VBAT/PM gates,
entry/exit/refresh ordering, PPS failure, source disappearance, physical mismatch,
REVBLK, changed epoch, ambiguous OFF and retry bounds. Successful mocks do not
prove hardware OFF when I2C is broken.

## Build, configuration and DT verification

Final default and isolated policy-offline ARM64 Image.gz/DTB/modules builds pass.
Resolved config equals embedded config; notes and exact181-file paired module
archive hashes are saved.96 protected source files,8 Stage1 safety helpers,
all62 references and accepted Stage2 artifacts remain unchanged.
Test253 adbd/rootfs/USB/NCM/SSH, TCPM core, DWC3, CPU/GPU/Wi-Fi/Bluetooth,
main fragment/primary DTS and ADC/thermal/float baseline are protected.

| Candidate | Exact semantic configuration delta vs Test255 | DT delta |
| --- | --- | --- |
| final fixed refactor | CHARGER_SM5440_DIRECT absent->n only | none; byte-identical DTB |
| passive Stage3B | CHARGER_SM5440_DIRECT absent->y only | existing hub3 charger@63 status disabled->okay only |
| final offline transaction | previous enable + X710_CHARGING_POLICY absent->y | same single status delta |

No unexpected config change; all85 container/UPower gates remain valid,
USER_NS/POSIX_MQUEUE=y,HVC_DCC=n,BATTERY_SM5714/ADC5_GEN3=y.
Default vmlinux has no HVC DCC write path, SM5440 probe or transaction-start
symbol. Primary connector fixed5/9V, Sink/Device and DWC3 peripheral unchanged.
Images are **new unaccepted software**, even when DT matches Test255.
See BUILD_RESULTS.md, summary.json and full unified configuration differences.

W=1 and actual sparse v0.6.5-rc1 check all four drivers without driver diagnostics.
One retained VDSO declaration warning is recorded. Distro sparse0.6.4 was rejected
by the kernel feature gate; that attempt is not counted as a sparse pass.
dtbs_check and SM5440 schema checks ran; no SM5440 binding diagnosis. Both frozen
and candidate boards report retained `usb-role-switch: size (4) error for type
flag` at the **unbound PS5169** node (status absent), with identical property.
Whole-board schema is therefore not advertised clean; PS5169 is outside scope.
Inherited defconfig merge warnings are recorded, not hidden or fixed here.

Final full host invocation: **1239 tests**,1200 retained+39 new,
zero failures/errors/skips,111.428s report wall time. Final changed shell wrapper
also ran1239 tests successfully. Per-phase changed/full evidence and two failed
build attempts plus corrected retries are preserved, never rewritten as success.

## Unimplemented / not accepted

No live PPS adapter, direct-current/OCP control loop, accepted protection recipe,
actual ADC calibration, complete sensor mapping or full vendor CC/CV/step/
termination/recharge/reset/watchdog equivalence is claimed. Pure models and a
transaction core are preparation, not a working direct charging path.
SIOP/LRP/Samsung UI/aging/battery care, wireless/reverse/OTG/bypass/dock/DeX/
DP/PS5169 are NOT PORTED. No source-role, APDO or current expansion is installed.

## Next and rollback

Next is only separately authorized/registered **passive probe and ADC on fixed
PD**. Then resolve software OCP/sensors/live adapter/PM before PPS-pumpOFF;
only afterwards <=1.8A short run,5min,20min and separately registered higher caps.
Every step needs real VBUS/current/temp/status/epoch/USB rescue evidence, first-
fault stop, verified OFF/fixed fallback, and physical recovery on ambiguous OFF.
Never deliberately exercise protection extremes. Full ordered A..G gates and
stops are in X710_CHARGING_TEST_PLAN.md.

Annotated `stage2-fixed-pd-known-good` preserves ebf4af1c. Rollback, if later
authorized, uses the exact accepted Test255 boot/vendor_boot/181-file module pair
and readback hashes; code checkout/new build is not equivalent. No rollback was
needed or executed here. Test252/249 rollback and Test253 userspace remain.

**Stage3 active PPS/direct-charge candidate: NOT READY.**
