# Optional X710 touchscreen module

Byte-identical import from Fedora X710 commit
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`, with original GPL-2.0 notices.
`SOURCE.json` binds both source files. This is an **offline external-module
preparation**, not an addition to the default kernel queue or an installed
driver. No source, config, DT, module directory or device firmware was changed
by compiling it.

The X710 DT already describes `st,fts1ba90a` on i2c4, address 0x49, GPIO25,
3.3 V analog/1.8 V I/O supplies, portrait-native 1600×2560 coordinates with
swap/invert. The running device has no input from it because the driver is
absent. S9 Ultra Goodix drivers are for different hardware.

The imported `linux/wacom_wez01.h` provides the original `IS_REACHABLE()` stub
returning false when Wacom is not configured. Thus ordinary touch can compile
without enabling or importing S Pen. Pen-proximity palm rejection remains
unavailable until that separate driver is ported. Controller-classified palms
are still rejected. The double-tap-to-wake sysfs toggle defaults off; this
preparation does not enable it or test suspend.

Build only into an output directory, using an identified prepared ARM64 kernel
provider with matching config, generated headers and Module.symvers:

```sh
mkdir -p out/gnome-trixie-arm64/touch-module/include/linux
cp kernel/desktop/fts1ba90a/fts1ba90a.c \
   kernel/desktop/fts1ba90a/Makefile out/gnome-trixie-arm64/touch-module/
cp kernel/desktop/fts1ba90a/include/linux/wacom_wez01.h \
   out/gnome-trixie-arm64/touch-module/include/linux/
make -C .work/build/linux-out-x710-308-passive \
  M="$PWD/out/gnome-trixie-arm64/touch-module" \
  ARCH=arm64 LLVM=1 CC='ccache clang' -j8 W=1 modules
python3 -m unittest discover -s tests -p 'test_fts1ba90a_events.py' -v
```

The recorded provider is the currently qualified Test348 build, **not a claim
that this module has been accepted on running Test331**. Same `vermagic` alone
does not establish pairing. Revalidate the exact provider/CRC set and device
identity at the future desktop deployment boundary. Do not install it during
the frozen Test348 charging test.

First physical stage after that test closes: prepare rescue/logging, load once,
check I2C/IRQ/input enumeration, then ask the owner to touch a grid and multiple
points. Check raw events and libinput before GNOME. Require the correct X710
orientation and no interrupt storm/I2C errors. Stop at the first fault and save
full journal; do not scan unrelated I2C addresses, update controller firmware,
rebind DSI/DPU or cycle shared display rails as a recovery shortcut. Module
unload, suspend/resume and double-tap wake are separate, presently untested
operations.

Offline evidence: `reference/desktop-bringup/fts1ba90a-offline/`. It records
eight tests executing the actual imported C touch/gesture functions (input
calls captured by host stubs), W=1 ARM64 module build and protected inputs.
Host tests cover raw protocol decoding; kernel touchscreen transforms, actual
controller/IRQ behavior and the graphical session require physical validation.
