# Test252: SM5714 Stage 1 battery and ordinary charging candidate

Registered 2026-09-28. **Prepared only; no device flash, probe, battery-only
run or charging run has occurred.** This registration is independent of the
unexecuted Test251 cold/power-path proposal. The installed Test249 production
baseline accepted by the Test250 CPU-focused warm-reboot continuation remains
the device baseline. No hardware action is authorized by this file.

The purpose is battery telemetry and ordinary SM5714 switching charge on the
SM-X710. Linux remains pinned to 7.2-rc3 with HVC_DCC disabled. The expected
resolved-config delta is precisely `BATTERY_SM5714=y` and
`QCOM_SPMI_ADC5_GEN3=n -> y`. Board DTS/DTB, cmdline, rootfs, gadget, CPU OPP,
cpufreq/cpuidle, CPU watchdog/panic, pstore, WCN and display remain unchanged.
No TCPC, OTG, PD/PPS negotiation or SM5440 driver is installed. No fast-charge
control or direct-charge handoff is exposed.

Build artifacts are `out/kernel-gts9wifi/` and
`out/boot-bundle-sm5714-stage1/`; exact identities are in `ARTIFACTS.json`.
The two supplies expected **after a successful future hardware probe** are:

- `/sys/class/power_supply/sm5714-battery/`: capacity, status, present,
  thermal/OVP/watchdog health, voltage/current now and average, pack temperature,
  OCV and unchanged battery design metadata (8160 mAh rated minimum, 4.44 V).
- `/sys/class/power_supply/sm5714-usb/`: online (VBUS_POK), BC1.2 usb_type and
  input_current_limit (programmed limit in µA). Online is not CC attachment;
  input_current_limit is not measured IBUS or a PD contract. Stage 2 is required
  for Type-C attachment/contract reporting.

Future deployment requires an explicit owner request and a fresh read-only
identity/transport preflight. Verify saved Test249 five-partition and all181
module hashes, embedded config/notes and DCC absence before any writes.
If any baseline identity differs, stop. The candidate has the same kernel
release string, so the complete paired candidate module directory must be
staged/verified atomically, with an external verified Test249 module archive
and recovery entry ready; do not mix modules just because vermagic matches.
The full candidate bundle is for host verification; only a changed `boot.img`
would need partition deployment. Never overwrite unchanged `vendor_boot`,
`init_boot`, `dtbo` or `vbmeta` as part of this test.

The generated bundle's `vbmeta.img` matches Test249's **saved generated**
bundle, but differs from the accepted on-device vbmeta hash
`9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4`.
It is a host packaging artifact and **must not be deployed**. `ARTIFACTS.json`
separately records accepted device hashes and saved generated-bundle hashes;
never infer the device vbmeta identity from a generated bundle manifest.

First record stock/TWRP SOC, battery voltage and pack temperature as an
independent reference. Then, after authorized candidate deployment, disconnect
Type-C for a **150 s battery-only** observation using the local console or a
previously working Wi-Fi SSH link. Do not pretend USB NCM/ADB can collect a
battery-only sample while disconnected. Keep screen awake; this test does not
test suspend. Run these read-only commands on Debian and retain their output:

```sh
cat /proc/sys/kernel/random/boot_id
uname -a
cat /proc/cmdline
cat /proc/uptime
ls -l /sys/class/power_supply/
cat /sys/class/power_supply/sm5714-battery/uevent
cat /sys/class/power_supply/sm5714-usb/uevent
journalctl -k -b --no-pager -o short-monotonic
systemctl --failed --no-pager
```

Battery-only acceptance: present=1, USB online=0, status=Discharging, sensible
SOC/V/current/temp matching the independent reference within sampling limits,
no large SOC jump, and no new kernel/I2C fault. Establish the measured current
sign by this actual discharge sample; the source conversion alone is not proof.

Only after that passes, attach an ordinary known charger, without PPS/direct
charge, and observe for **20 minutes**, sampling every 10 s on the local
console/Wi-Fi link. A USB host CDP/SDP may separately verify ADB/NCM; a wall
charger cannot provide a Windows USB transport. Record charger/cable identity,
full uevents, boot ID/uptime and complete kernel journal with source timestamps.
For example, redirect this local-console sample loop to an evidence file:

```sh
for sample in $(seq 1 121); do
    date -u
    cat /proc/sys/kernel/random/boot_id /proc/uptime
    cat /sys/class/power_supply/sm5714-battery/uevent
    cat /sys/class/power_supply/sm5714-usb/uevent
    sleep 10
done
journalctl -k -b --no-pager -o json
```

Charging acceptance requires online=1, appropriate Charging/Full status,
measured pack current changing from the established discharge direction,
reasonable voltage/temp, SOC rising at a suitable non-full starting SOC, no
I2C/charger watchdog/reset loop or kernel fault, and plug-out returning to
Discharging/online=0. Online/Charging labels by themselves never pass this test.
Record absent PD/VBUS/IBUS/SM5440 telemetry as unavailable, not as invented
measurements. A low-current source that cannot overcome system load is
inconclusive, not a reason to increase current limits.

Stop immediately on a CPU stall/panic, transport regression/Code43, incomplete
boot attribution, charger fault/thermal trip, repeated I2C error, unknown or
implausible temperature, voltage exceeding the pack design limit, unexplained
SOC/current behavior, charge safety write/readback failure or identity change.
For the first bounded run also stop/disconnect at pack temperature **42°C**;
do not deliberately exercise hot/cold limits. Preserve raw logs. Do not raise
limits, clear charger faults, change USB configuration or continue repeated
reboot/charge attempts to obtain a pass.

If recovery is needed after a future authorized test, unplug the charger,
enter TWRP, preserve failed-boot logs, and restore the externally verified
**Test249 boot image plus its exact all181 module directory**. Verify the
unchanged four partitions and full saved Test249 config/notes/DCC/module
identity before a normal reboot. Test249 rollback artifacts remain in
`out/boot-bundle-no-dcc-production/`, `out/kernel-no-dcc-production/` and the
previously accepted Windows `D:\android\gts9-active\gts9-test249\` rescue set.
Use `/mnt/d/android/gts9-active/platform-tools/adb.exe` for later recovery;
the old ADB path is not the current default. No rollback is executed now,
because nothing has been deployed.

Stage 2 TCPM may start only after Stage 1 physical acceptance. Stage 3 SM5440
must wait for Stage 1 and Stage 2 physical acceptance and remain opt-in.
