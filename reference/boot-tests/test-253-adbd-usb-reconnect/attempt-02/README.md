# Test253 attempt02 proposal: unchanged candidate plus userspace ADB repair

Pending owner adoption. Initial Test253 preflight remains stopped. The exact
compiled daemon/launcher/ExecStart and all physical reconnect steps in the
parent registration are unchanged; no new software variant is introduced.

A new read-only preflight records the existing UPower prerequisite failure
instead of requiring zero failed units. The only recognized baseline failure
is `upower.service loaded failed failed Daemon for power management`, with
Result=exit-code and ExecMainStatus=217, shipped PrivateUsers=yes, unchanged
unit bytes and candidate CONFIG_USER_NS disabled. If this unit executes and
fails differently, any other failed unit appears, or any CPU/kernel/USB,
identity/evidence gate fails, stop immediately. Do not modify, restart or
reset-failed UPower, or enable USER_NS. This independent UPower integration
issue remains unresolved and is never presented as repaired by ADB.

All kernel/config/DTS/modules/charge, gadget holder/guard/mount, NCM/SSH/key
identities remain exact. Keep native ADB offline only as the pre-deployment
repair target. Staging with continuous NCM SSH, one normal reboot, at least150s
new-boot observation, one connected host ADB reconnect with uninterrupted NCM
SSH,1MiB push/pull identity and three physical unplug/replug cycles with Wi-Fi
SSH,≤60s recovery and≥150s windows remain required. New failures stop the
attempt. Test252 stays stopped and Stage2/3 do not start. Commit/push adopted
registration/code/local tests before any write or reboot; record outcomes and
seals afterward. No kernel build or flash, no CI and no main merge.
