# Test252 physical attempt01

The owner explicitly requested physical testing: "开始测试吧". This supersedes
only the prepared/unflashed phase of the original registration. Execute its
150s battery-only observation, then20-minute ordinary charging observation,
plug-out and USB checks, with the same first-anomaly stop conditions. Stage2/3
remain excluded. No configuration or protection limit changes are authorized.

The owner subsequently specified ADB tools directly under
`D:\android\platform-tools\`; use `/mnt/d/android/platform-tools/adb.exe`.
All Windows test/rescue files remain below `D:\android\gts9-active\gts9-test252\`.
Historical paths and the original sealed registration remain unedited.

The full read-only preflight matches Test249 config, notes, all five partitions
and all181 module files, with DCC absent and no failed unit. ADB/NCM/banner/SSH
pass immediately and Wi-Fi SSH at10.191.121.224 returns the same boot ID. It is
therefore possible to observe battery-only operation without USB attached.
The first observer stopped because it compared a hyphenated UUID to a normalized
UUID; preserve its summary/source and use `preflight/observer-review.json` for
the independently reviewed evidence. The review also checks the parser's actual
fault/suspect keys; no CPU fault was hidden by the observer's wrong key names.

Preflight raw journal contains one preexisting missing optional GPU firmware
error at source607.872728s, preceded by an exact qcom/a740_sqe.fw load errno-2.
Both current and legacy firmware paths are absent. AGENT already records the
GPU-firmware dependency and the separate-GPU/KMS production cmdline. This is a
known degraded rendering function predating this candidate, not a battery or
CPU failure. Record it separately without repairing GPU/firmware/rootfs or
changing the historical Test250 verdict. For candidate inspection only this
exact known error may be classified with the matching errno-2 context; any
new unexplained error or CPU/I2C/charge/USB fault still stops. Full journals,
not just filtered text, are evidence.

Before deploying: verify staged hashes, existing partition sizes/labels,
stock/TWRP SOC/voltage/pack temperature and the identified Debian microSD UUID
and machine-id. Rehearse module install/restore offline. Push this registration
and accepted preflight first. Deploy only boot plus the complete paired module
directory; preserve vendor_boot/init_boot/dtbo/vbmeta and verified external
Test249 boot/module rollback. Enter recovery via the tested label-addressed BCB
helper followed by plain reboot; never use Debian `reboot recovery`.

After candidate boot: verify exact candidate notes/config/181-module/boot hash,
all four preserved partition hashes, new boot attribution, DCC absence and
transport; then collect real supply properties and all kernel logs. No battery
or charging acceptance is claimed until the registered observations finish.
Charger/cable identity and user-confirmed physical attach/detach are part of
the evidence. Retain temporary original modules for immediate recovery; cleanup
requires later acceptance and an independent retention decision.
