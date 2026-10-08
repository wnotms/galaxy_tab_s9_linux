# ACPI battery reporting repair — 2026-10-08

Owner requested this independent userspace repair during Test347's natural
discharge wait. No charging activation, flash, reboot or daemon restart occurred.

On accepted Test331 boot `a96de8c0383b4f78b976ecc6db3ab793`, the kernel's
SM5714 fuel gauge reported75% and UPower1.90.9 also reported75%. Packaged
Debian `acpi`1.8-1 ignored `capacity`, calculated from missing
`charge_now/charge_full`, and displayed0%, a dangling remaining time, and
negative learned capacity. Raw before output is retained in `device-before.txt`.

The original GPL C client now consumes valid0..100 capacity, preserves measured
charge/energy and procfs fallbacks, and reports missing charge/time/learned-full
information as unavailable. No kernel attributes or battery health data are
invented. UPower's separate `capacity:100%` health fallback and energy/time
estimates are not independent measurements of learned full capacity or wear;
its `percentage` is the relevant state-of-charge field and matches sysfs.

12 actual-C fixture tests passed in0.522s: native-capacity shape, zero/full,
capacity preference, invalid/overflow values, missing measurement/time,
charge/energy ratios and times, procfs and adapter filtering. ARM64 build passed
after fixing the build sysroot's missing merged-/usr alias. An upstream header
guard typo warning is retained; initial link failure and successful build logs
are preserved separately. No kernel/full host build was repeated.

Installed binary `/usr/local/bin/acpi` SHA256
`a0f62ffe810ca6f5722256ef78b722b104de11a611e65c9435021f0cae896722`.
`/usr/bin/acpi` retained unchanged SHA256
`b7da9983c2d3ba1f0f635765168d4b5f64b9b091c5456a371225c71605b73b07`.
Installation checked boot, transferred bytes, native preview and actual
percentage before atomic installation. No private key, build libc, or compiler
was copied to the tablet. Existing local commands would have been rejected.

Normal PATH now resolves `acpi` to the local binary. Actual `acpi -b/-bi`,
sysfs and UPower all reported74% on the same boot after installation. The
remaining-time and learned-capacity fields correctly say unavailable. Existing
shells that cached `/usr/bin/acpi` need `hash -r`. Removing the verified local
binary restores Debian's unchanged package command.

Config51ba6a9c and notes03c9c46e still match accepted331. Battery remains
Discharging, USBonline0, pack30.7C; natural watcher continues. SM5714/SM5440,
TCPM, current/voltage/thermal policy, DTS/config/modules, USB/adbd and Test347
frozen execution inputs are unchanged (`INPUTS_MATCH`). This userspace repair
does not qualify five-minute charging or full/vendor-equivalent port acceptance.

See `installed-summary.json`, normal-command-after/raw stdout, `build.json`,
offline-summary and [reproducible source/patch](../../../userspace/acpi/README.md).
