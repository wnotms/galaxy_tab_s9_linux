# Production DCC repair: host gates passed; hardware target pending

The default mainline build completed successfully with diagnostics explicitly
disabled. Against the IKCONFIG extracted from the original production boot,
the only resolved config changes are `CONFIG_HVC_DCC=y` to `n` and the dependent
`CONFIG_HVC_DRIVER=y` to `n`. The exact built vmlinux contains neither the
`hvc_dcc`/`hvc_write` code nor temporary CSD, last-activity or calibration
symbols. Kernel release is unchanged.

The DTB equals the original production DTB byte for byte. Compared with the
passing test248 diagnostic DTB, its only decompiled difference is removal of
the diagnostic `ramoops` `ecc-size = <64>` property. `arch/arm64/mm/mmu.c`
matches the pinned upstream commit. All 167 installed `.ko` files from the
verified original backup retain the same allocated ELF sections and import
CRC values in the new build; all 181 candidate module-directory files match
their archive and manifest. `depmod -e -E` produced no unresolved symbol.
The offline module install/restore/interrupted-install rehearsal passed.

The full boot bundle passed `validate-boot-bundle.sh`. Only `boot` and
`vendor_boot` are staged for flashing; `init_boot`, `dtbo` and `vbmeta` are
preserved on-device. The staged production image hashes are
`7f021014850504c3d881504cdf4c44171d0adb1049ae987d6552774684a8482b`
and `49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9`.
The passing248 rollback pair and 181-module archive were separately checked.
At this checkpoint no test249 image or module has been installed on hardware.

The owner's intervening diagnostic248 Debian boot
`3527c008-4415-43db-bdcb-b55e8adc31ee` suffered a single Windows Code43
USB enumeration failure, then normal reboot
`b78d646f-c0c5-4c71-9c4c-17ca7d037260` recovered ADB/NCM without a
configuration change. Both journal files and the host screenshot are in
`usb-incident`; USB success is an explicit target gate for both production
startup paths. A read-only current-source preflight confirms all181 source248
module hashes on the running system.
