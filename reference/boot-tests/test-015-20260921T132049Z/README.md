# Test 015 — kernl console on the panel (2026-09-21T13:20:23Z)

Hypothesis: the bootloader is already scanning out the splash it drew from
`splash_region` (`cont_splash_region`, 0xb8000000, 2560x1600, 32bpp, from the
stock DTBO), so binding `simple-framebuffer` to it and letting fbcon print there
would give the port a readable log channel with no storage and no USB.

Artifacts: `boot 457f276e…` (DPU/DSI disabled, `/chosen/framebuffer@b8000000`
added), `init_boot 7f892d81…`, `vendor_boot 8a0c5147…`, flashed and read back;
`vbmeta` untouched. Validator passed. No proof was armed, so the tablet stayed on.

## Result: inconclusive for the intended channel

Owner: **the tablet stayed on the logo and no kernel text appeared.**

`simple-framebuffer` is the right binding and the kernel does populate a
`/chosen` `simple-framebuffer` child (`drivers/of/platform.c`), so the likely
explanation is the panel itself: it is a command-mode DSI panel holding the
bootloader's frame in its own memory, and nothing in this kernel can ask it to
refresh. Writes to the splash buffer therefore never become visible.

Consequence: the panel is not a usable output channel until a panel driver
exists, and it should not be relied on for bring-up evidence.
