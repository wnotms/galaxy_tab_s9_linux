# Test255 attempt01: connected-device fixed-PD Stage2 acceptance

Owner authorized physical testing with “开始测试吧” on 2026-09-29. This is a new
attempt against the sealed offline candidate in the parent directory. It does
not alter the offline result. The initial observed Debian boot is
`6c3dde80-334e-4955-8916-9a1e576c8024`, previously attributed to Test254.
Initial Windows ADB, source-bound NCM SSH and Wi-Fi SSH all respond on that same
boot; Windows reports the ADB and NCM devices OK. These preliminary observations
are not a full identity or rollback preflight.

## Available equipment and scope

The owner reports no inline USB-C PD voltage/current meter and no independent
5V-only charger. Attempt01 may proceed through rescue/identity, candidate
deployment, battery-only 150 seconds and PC USB Sink/Device/ADB/NCM checks.
Do not connect a PD charger, request/observe 9V, or mark the 5V-only or 9V
charging gates passed in this attempt. Stop at the missing-equipment gate after
the PC test. TCPM `voltage_now` is negotiated state and cannot replace an
independent actual-VBUS measurement for the registered 9.5V stop condition.
No Stage3, SM5440/PPS, source/OTG/dock or protection-limit testing.

## Candidate and rollback identity

- Candidate `boot`: `26ef6bd143a9575b997b8cf73f24686d647f1ac742f0e7d92d44aa600ef7c063`
- Candidate `vendor_boot`: `d80d03cdf0ac810d9ac741074a9b97327c48880a98a4459db219ed7813461a46`
- Candidate embedded config: `cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f`
- Candidate kernel notes: `fb3d249642e900d9bb591fb629c1865b370b50098d44970b986cc793f45c160c`
- Candidate paired modules: exactly 181 file hashes in
  `../validation/module-hashes.json`, archive `28e33cda7814686ee32b480c0b0cf4f02952cdc89d19ad7af37feb47e79edf1c`
- Installed Test254 rollback `boot`: `ea73e65836ab316af658ed53273be0ec6351b335750978095e509054164509f7`
- Installed Test254 rollback `vendor_boot`: `49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9`
- Installed Test254 config: `c80d3c661cca3588fc85c93ba3402356bd99b7e4fe85674773230914fb8e6b71`; notes `7bbb0dc382d4b89b2d6c5b79c1f02805ef0afc8459fe6b48a423d9f26744332b`
- Preserve installed `init_boot`, `dtbo`, `vbmeta`, Test252 backup
  `.gts9-test254-original` and Test249 backup `.gts9-test252-original`.

## Gate sequence

1. Before any reboot/write, save boot ID, uname/cmdline/uptime, full five
   partition hashes, exact embedded config and notes, current 181 module
   hashes, both retained 181-file rollback directories, Test253 adbd/rootfs
   settings, Windows PnP, ADB/NCM/Wi-Fi, complete kernel journal, failed units,
   battery SOC/current/voltage/temperature/health. Compare against Test254
   final accepted evidence. Any mismatch stops before maintenance.
2. Verify candidate boot/vendor_boot unpacking, AVB layout, hashes, and paired
   module archive once more. Retain exact Test254 boot and matched modules as a
   **new distinct rollback pair** before replacement; do not overwrite older
   backups. Use established TWRP, label/card-verified deployment and readback.
   Only candidate boot, vendor_boot and matched 181 modules may change. No
   generated init_boot/dtbo/vbmeta, rootfs service/config or cmdline write.
3. Boot Debian. Verify exact new five partition/config/notes/181 module
   identity, DCC absent, Sink/Device-only live topology, Stage1 safety,
   Test253 userspace adbd, ADB/NCM/Wi-Fi and full journal. Stop on mismatch.
4. Disconnect PC USB, keep Wi-Fi rescue, observe at least 150 seconds battery
   only: online=0, Discharging, negative pack current and normal temperature.
5. Reconnect PC USB only. Confirm Sink+Device/UFP, USB enumeration without
   Code43, ADB shell/file roundtrip, NCM SSH and Wi-Fi on the same boot, and
   stable telemetry/journal for at least 150 seconds. Stop on first non-clean.
6. Stop attempt01 here because the independent 5V and actual-VBUS 9V gates
   cannot be run with the reported equipment. Record a bounded partial result;
   do not label Test255 full acceptance or request further PD power.

Immediate stop on unplanned reboot, kernel panic/Oops/soft lockup/RCU/CSD
stall, repeated TCPC/SM5714 I2C fault/reset/attach loop, unexpected Source/
Host/PPS/SM5440 probe, VBAT above design, temperature at least 45°C or rapid
rise, abnormal current, loss of rescue channels or Windows Code43. Preserve
raw evidence first. Do not retry a stopped stage automatically.

If a later authorized deployment fails, restore the retained Test254 boot,
vendor_boot and exact paired module directory via verified TWRP; read back
hashes. Preserve all other partitions and older rollback pairs. No automatic
rollback is implied by this registration.
