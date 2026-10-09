# GPU lifecycle correction — compiled and packaged, not deployed

The current Test331 boot remains unchanged. Test368 stopped during read-only
preflight on five new GMU HFI bandwidth-vote timeout/late-response pairs; its
STOP is not rewritten or retried. USB reconnect is not yet permanently fixed.
This offline candidate addresses a separately confirmed upstream GPU lifecycle
defect before continuing hardware qualification.

## Source and device evidence

The pinned Linux 7.2-rc3 commit is
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`. Upstream commit
[`d9108bfdb746`](https://github.com/torvalds/linux/commit/d9108bfdb746edacdb05bd27959a4ae63c6c7f3f)
was merged on 2026-07-16, after this pin. The same-model Fedora X710 repository
still points to `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`; its Linux 7.2 stable
base already carries both corrections. The saved commit API responses, stable
source and prepared-tree diff make the comparison reproducible.

The old pending adaptation carried only the inverted guard correction and
mistakenly treated a CM3 reset in the force-off function as covering the normal
shutdown function. The active patch now carries both original upstream hunks:
return only when GMU firmware was not started, and halt CM3 before RPMh stop in
normal shutdown. The incomplete pending file remains inactive historical evidence.

On exact Test331 boot `78ec1906-4713-4837-9acc-fe245647d7cf`, a read-only
15-second sample shows GPU and GMU runtime suspended time each increasing by
15,003 ms, active time unchanged, control `auto`, and 16,937 prior devfreq
transitions. Autosuspend is actually exercised. Installed GPU firmware hashes
match the previously qualified files. The same snapshot records battery 80%,
28.2°C, Good/Discharging, VBAT 4.164 V and IBAT −0.400 A. These are observations
of the old boot, not new-kernel acceptance.

Previously merged HFI empty-queue and ACD timeout fixes are already in the pin.
No HFI timeout increase, new firmware, performance setting or speculative GPU
workaround is added. The confirmed lifecycle bug does **not** establish that it
caused all observed HFI faults or any historical CPU wedge. Test247's directly
proven DCC CPU-stall path remains separately fixed.

## Build and precise scope

The standard ARM64 LLVM/ccache, JOBS=8, `sm5440-fedora` profile build completed
with Image.gz, DTB and modules. The existing incremental tree was reused. The
extra `W=1` build of `a6xx_gmu.o` also completed without a driver warning.
`BUILD_AUDIT.json` contains exact artifact identities and all 181 module hashes.

Config, DTB, 181 module payloads and exported symbol CRCs are identical to the
already compiled native-Escape candidate. The only resolved config difference
relative to accepted Test331 is the previously prepared `QCOM_SOCINFO: n → y`;
the complete text diff and machine-readable diff are saved. HVC_DCC remains n,
UPower/OCI features remain present, and no new config change is introduced here.
Native EF-DX710 Escape/grave swapping remains in the next kernel as requested.

Kernel driver/config/DTS, rootfs-overlay and adbd sources frozen before this
build remain unchanged. No charging/PD/PPS/pump, DWC3, gadget, CPU/GPU OPP,
regulator or firmware edits. Old formal Escape artifacts remain hash-identical.
The two new GPU hunks are shown separately from existing stateless-device-link
changes in `prepared-gmu.diff`.

## Input and boot pairing

`prepare-bundle.py` assembled `out/boot-bundle-x710-gmu-rpmh/boot.img`; AVB,
appended Image.gz/DTB payload, empty ramdisk, 96 MiB partition size and original
boot metadata were checked. It references accepted Test331 vendor_boot;
**no early ADSP vendor image or sensor service activation** is included.
`BUNDLE.json` saves the boot SHA and every qualification command.

The unchanged native pen and palm-aware touch modules were requalified against
the new provider: exact source/binary hashes, vermagic and all 29 + 38 imported
symbol CRCs match. Independent staged loaders accept only the new config/notes
and exact module hashes. AST comparison proves only PROFILE changed. Twelve
actual loader fixture cases passed, including wrong identity, corrupted module,
direct-charge command line and temperature rejection.

The independently staged keyboard mapping helper changes only the exact native
IDENTITIES pair, preserves accepted Test331 rollback identity, removes only the
temporary XKB swap on the new native driver, and restores it on rollback. Nine
existing behavioural tests exercised the staged implementation; four additional
real-artifact identity cases accepted the candidate and rejected old notes,
wrong config and a changed boot. No historical frozen runner was patched.

## Executed validation and retained failures

26 affected unit tests passed, 0 skipped: eight actual prepared C stop/shutdown
ASan/UBSan cases, eleven source/provenance checks and seven Pogo tests. The input
loader/mapping cases above are additional bundle qualification, not a claimed
full repository regression. Syntax/AST and artifact checks ran offline.

Two initial host mistakes are preserved: the C mock initially expected ACK bit 1
instead of the actual pinned BIT(16), and the combined command initially named a
nonexistent `test_pogo_release` module. Correcting the fixture/selection did not
change kernel behaviour or delete/skip tests. The final combined run executed
all seven existing Pogo tests. W=1 reported no driver warning; the packet mock
reports two unused shim functions, not ARM64 driver warnings.

No exhaustive historical rerun, Actions or CI wait. The previous full regression
was not green and is not represented as a reused PASS. Sparse was not executed
because its executable is unavailable. Raw logs and initial failures are hashed.

## Next hardware scope

Register a new independent one-boot GPU/native-Escape test before mutation:
essential rescue/battery/identity checks once, exact boot/module/input readback,
bounded GNOME startup and ordinary desktop use, actual native keys/touch/S Pen,
and raw kernel capture. Preserve unique boot attribution. A new fault stops
the test and restores Test331 with its original paired input and interim XKB.

Only then qualify the USB event-driven lifecycle helper with the new exact
kernel identity and a short unplug/reattach sequence. Do not ignore new GPU,
CPU, Code43, identity or rescue faults to continue. The earlier USB teardown
source audit remains narrowly scoped and does not prove every reconnect failure
benign. Sensor discovery/rotation and later charging work remain unfinished.

No device flash, reboot, partition/module/rootfs write or charging experiment
was executed for this candidate. Endpoint remains the existing GNOME system.
