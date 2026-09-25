#!/usr/bin/env bash
# Wait for the tablet to appear, then capture the Wi-Fi cold-boot state the
# instant it does.  Read-only, like wifi-preflight.sh.
#
#   scripts/wifi-cold-boot-capture.sh OUTDIR [TIMEOUT_SECONDS]
#
# Why a separate script: a cold power-on is a one-shot event.  The interesting
# window is the first seconds after the kernel probes PCIe, and by the time a
# person notices the tablet is up and runs a probe by hand, the state being
# measured may already have moved on.  This polls for the tablet and captures
# immediately, so the cold result is not a late reading of a warm system.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
OUT=${1:?usage: $0 OUTDIR [TIMEOUT_SECONDS]}
LIMIT=${2:-1800}
SSH=$REPO/scripts/gts9-ssh.sh

mkdir -p "$OUT"
say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

start=$(date +%s)
say "waiting for the tablet to answer ssh (up to ${LIMIT}s) - cold power-on"

# Trigger: exit the moment the tablet answers.  No fixed sleep.
until timeout 8 "$SSH" 'echo UP' >/dev/null 2>&1; do
	if [ $(( $(date +%s) - start )) -ge "$LIMIT" ]; then
		say "TIMEOUT: the tablet never came up"
		exit 1
	fi
	sleep 2
done
say "the tablet answered after $(( $(date +%s) - start ))s"

# Capture immediately, then again a few seconds later: the first read is closest
# to the cold probe, the second shows whether an endpoint appeared late.
snap() {
	local tag=$1
	timeout 200 "$SSH" "
echo \"snapshot=$tag\"
echo \"captured_utc=\$(date -u +%Y-%m-%dT%H:%M:%SZ)\"
echo \"boot_id=\$(cat /proc/sys/kernel/random/boot_id)\"
echo \"uptime=\$(cut -d' ' -f1 /proc/uptime)\"
echo \"kernel=\$(uname -r)\"
echo \"cmdline=\$(cat /proc/cmdline)\"
echo '--- modules ---'
echo \"modules_installed=\$(find /lib/modules -name '*.ko' 2>/dev/null | wc -l)\"
for m in pci_pwrctrl_pwrseq pwrseq_qcom_wcn ath11k; do
  echo \"loaded_\$m=\$(lsmod | grep -c \$m)\"
done
echo '--- binding ---'
for d in 1c00000.pcie 1c06000.phy wcn6855-pmu 1c00000.pcie:pcie@0:wifi@0; do
  if [ -e \"/sys/bus/platform/devices/\$d/driver\" ]; then
    echo \"drv_\$d=\$(basename \$(readlink -f /sys/bus/platform/devices/\$d/driver))\"
  else
    echo \"drv_\$d=UNBOUND\"
  fi
done
echo '--- deferred ---'
cat /sys/kernel/debug/devices_deferred 2>/dev/null
echo '--- pci ---'
echo \"pci_count=\$(ls /sys/bus/pci/devices 2>/dev/null | wc -l)\"
for p in /sys/bus/pci/devices/*; do
  [ -e \"\$p/vendor\" ] || continue
  echo \"pci_dev \$(basename \$p) \$(cat \$p/vendor):\$(cat \$p/device) class=\$(cat \$p/class)\"
done
if [ -e /sys/bus/pci/devices/0000:00:00.0 ]; then
  LS=\$(setpci -s 00:00.0 0x72.w 2>/dev/null)
  echo \"link_status=0x\$LS\"
  echo \"dllla_bit13=\$(( (0x\${LS:-0} >> 13) & 1 ))\"
  echo \"cur_speed=\$(cat /sys/bus/pci/devices/0000:00:00.0/current_link_speed 2>/dev/null)\"
fi
echo \"endpoint_present=\$([ -e /sys/bus/pci/devices/0000:01:00.0 ] && echo YES || echo NO)\"
echo '--- gpio ---'
sed -n '31,250p' /sys/kernel/debug/gpio 2>/dev/null | grep -E '^ gpio(80|81|82|94|95|96|204) '
echo '--- pmu rails ---'
for want in vreg_l15b_1p8 vreg_s2g_1p012 vreg_s5g_0p966 vreg_s4e_0p952 vreg_s4g_1p352 vreg_s6g_1p904; do
  for r in /sys/class/regulator/regulator.*; do
    [ \"\$(cat \$r/name 2>/dev/null)\" = \"\$want\" ] && echo \"rail \$want=\$(cat \$r/state 2>/dev/null)\"
  done
done
echo \"pmu_internal_rails=\$(for r in /sys/class/regulator/regulator.*; do cat \$r/name 2>/dev/null; done | grep -c vreg_pmu)\"
echo '--- wireless ---'
echo \"wireless_phys=\$(ls -d /sys/class/ieee80211/* 2>/dev/null | wc -l)\"
echo \"wlans=\$(ip link 2>/dev/null | grep -cE '^[0-9]+: wl')\"
echo '--- pcie dmesg ---'
dmesg 2>/dev/null | grep -aiE 'qcom-pcie|17cb|pcieport|Device not found|ath11k' | tail -20
" > "$OUT/$tag.txt" 2>&1
	say "captured $OUT/$tag.txt"
}

snap cold-1-immediate
sleep 20
snap cold-2-settled
say "done"
