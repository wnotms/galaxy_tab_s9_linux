# Optional X710 S Pen module

Based on the same-model Fedora X710 WEZ01 driver at
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`; remote HEAD checked at preparation
still matches that pin. GPL-2.0 notices preserved. SOURCE.json binds original
and imported hashes; the precise four local changes are in
reference/desktop-bringup/wacom-wez01-offline/fedora-local.patch.

This is an external module, not a default kernel integration or replacement
for a production image. Its local Makefile defines the optional Wacom module
selector only for this translation unit so the original shared header declares
the exported implementation instead of the disabled stub. It does not modify
resolved .config. The already accepted FTS module still uses the false-returning
stub: **this first pen stage does not enable pen-proximity palm rejection**.
That requires a separately qualified paired touch module and a new loading scope;
do not replace/unload the accepted touchscreen implicitly.

The existing X710 DTS describes i2c3, address0x56, interrupt GPIO154 level-low,
flash-mode GPIO179 (normal low), PDCT GPIO137, shared panel VCI avdd. Current
accepted331 runtime maps it to6-0056; do not assume all kernels use this number.
The driver refcounts the supply, never cycles shared rails, and keeps flash-mode
low. Probe reads the32-byte query block and sends one ordinary0x31 reporting
command. No firmware downloader, firmware blob, garage/BLE feature or new DTS
is imported. Raw16-byte coordinate frames plus ACK, pressure and buttons are
cross-checked against Samsung msm-kernel/drivers/input/wacom/wacom_i2c.c and
wacom_reg.h; exact source hashes are saved.

## Local lifecycle corrections

- Proximity-out/suspend use timer_delete_sync; final cleanup retains
  timer_shutdown_sync. Linux7.2 shutdown permanently prevents rearming.
- Each new coordinate frame drains the prior silence callback before writing
  shared input/proximity state, then rearms after the frame. Threaded IRQ is
  serialized by IRQF_ONESHOT; it holds no callback lock. Suspend first disables
  and drains IRQ, teardown releases IRQ before stopping timer.
- Register input, register timer cleanup, then request IRQ. Reverse devres order
  drains IRQ and timer before unregister/free input, including probe failure.
  Linux input_register_device adds a separate unregister resource action.
- Probe returns an error if the sample-start command fails instead of claiming
  successful activation. No expanded protocol or board-current policy.

The Fedora calibration and100 units/mm resolution are retained; owner grid
acceptance is required. Query failure/default-limit fallback remains upstream
behavior, but Test362 rejects that path as physical acceptance. Unexpected MPU
ID also stops. PM command-error recovery, suspend/resume, hot-unbind and tilt
accuracy are not hardware-qualified by this stage. Tests using timer/I2C stubs
prove code paths, not real scheduling or controller operation.

## Build and test

Use the existing identified ARM64 external-module provider, after checking its
config/generated headers/Module.symvers and protected charging assets. Copy this
directory to an ignored output directory, then:

```sh
make -C .work/build/linux-out-x710-308-passive \
  M="$PWD/out/gnome-trixie-arm64/pen-module" \
  ARCH=arm64 LLVM=1 CC='ccache clang' -j8 W=1 modules
python3 -m unittest discover -s tests -p test_wacom_wez01_events.py -v
```

The provider belongs to Test348, whose kernel notes differ from installed331.
Test362 therefore checks **every consumed export CRC against exact331 Image**
using runtime export-table boundaries, including module_layout. All29 match;
.BTF.base is present, but the normal device loader still owns ABI/BTF/signature
validation. Never force a version, signature or BTF check. Unsigned external
module taint is expected with the accepted MODULE_SIG_FORCE=n, and is recorded.
Build W=1 and15 affected host tests pass; no full kernel rebuild or full host
regression was executed. No charging/config/DT/181-module directory change.

## First physical scope

Test362 registers one ordinary insmod from var/tmp,5s initial IRQ/health check,
then at most600s non-grabbing pen-only raw capture while the owner tests hover,
tip strokes, button and grid. GNOME/touch and Wi-Fi rescue must remain normal.
Reject query/probe/I2C fault, IRQ storm, new kernel/CPU/GPU fault, changed boot or
lost rescue. No suspend, calibration write, flash, reboot, autoload or charging
activation. A running capture is a bounded observer, not a permanent service.
Physical probe/input/owner results must be recorded separately from this offline
build. Full port and charging Test348 remain incomplete.
