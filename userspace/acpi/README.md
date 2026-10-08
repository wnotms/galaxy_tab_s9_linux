# ACPI client support for capacity-only fuel gauges

The Test331 SM5714 power_supply already reports its measured fuel-gauge
`capacity` correctly. Debian UPower1.90.9 consumes it correctly. Debian
`acpi`1.8 instead ignores that attribute and calculates a percentage from
`charge_now/charge_full`, which this driver does not provide. Missing values
produce a false0%, a dangling time estimate and negative learned capacity.
See the [Debian source](https://sources.debian.org/src/acpi/1.8-1/).

The patch makes the original C client prefer a valid0..100 `capacity`, with
its existing charge/energy ratio as fallback. Missing measurements are
reported as unavailable. It does not synthesize charge, learned full capacity,
health, or remaining time from design capacity. Existing measured-charge,
energy, and legacy procfs cases retain their calculations. UPower's own
energy/time estimates are separate; they are not new hardware measurements.

`source-baseline/` is the unchanged GPL-2.0-or-later upstream source subset,
identified by `SOURCE.json`; copyright and license are retained. The ARM64
sysroot package hashes come from the device's Debian APT metadata and are
checked before extraction. These libraries are build inputs only and are
never installed on the device. No privileged host package installation or
on-device compiler is needed.

Build and test:

```sh
python3 -m unittest tests/test_acpi_power_supply_capacity.py
python3 userspace/acpi/build.py --arch arm64
# Optional native executable for fixture/manual checks:
python3 userspace/acpi/build.py --arch host --out out/userspace/acpi-host
```

Build output: `out/userspace/acpi-battery-compat/acpi` and `build.json`.
The ARM64 binary uses the normal Debian dynamic loader/libc. The upstream
header guard typo produces a pre-existing compiler warning; this reporting
patch does not change it. An initial cross-link failed because the extracted
merged-/usr sysroot lacked its base-system `lib -> usr/lib` alias; the build
helper now supplies that local build alias.

For this owner's requested reporting repair, transfer the binary and
`install-local.sh` over authenticated SSH, then run on the tablet:

```sh
sh install-local.sh ./acpi VERIFIED_BINARY_SHA256
hash -r
acpi -b
acpi -bi
upower -i /org/freedesktop/UPower/devices/battery_sm5714_battery
```

The local binary takes precedence in the normal `/usr/local/bin` PATH.
`/usr/bin/acpi` and the Debian package remain untouched; an existing local
binary is never overwritten. For rollback, verify that the local binary hash
still matches the recorded installed hash, remove `/usr/local/bin/acpi`, and
run `hash -r`. No service restart, kernel rebuild, flash or reboot is needed.

Only battery-reporting userspace changes. Charging registers, current limits,
SM5714/SM5440/TCPM, DTS/config/modules, USB/adbd, and Test347's qualified
artifacts/guardian inputs remain unchanged. Full charging-port acceptance
still requires its independent physical progression.
