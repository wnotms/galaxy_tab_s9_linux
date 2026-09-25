#!/usr/bin/env bash
# Wi-Fi bring-up preflight: READ-ONLY, for the QCA6490 / WCN6855-class endpoint on
# the X710's PCIe0.
#
#   scripts/wifi-preflight.sh              # probe the tablet, print a report
#   scripts/wifi-preflight.sh --save DIR   # also keep the raw transcript
#
# This script never writes to the device.  It does not modprobe, does not bind or
# unbind drivers, does not toggle a GPIO or a regulator, and does not touch the
# firmware directory.  Anything that could change hardware state is deliberately
# left to a separate, explicit step, because the first question - "did the
# endpoint enumerate?" - has to be answered before anything is changed.
#
# The question it exists to answer, and refuses to assume:
#
#   Does this boot have a PCI device 17cb:1103, or only a `compatible` string in
#   the DTS?  A device tree node is not enumeration.  `pci17cb,1103` in the DTB
#   means the *binding* is declared; only /sys/bus/pci/devices/0000:01:00.0 is
#   evidence that a link trained and a config space was read.
#
# It classifies the result into the six states the bring-up plan branches on, so
# the answer is a named state rather than a wall of text.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
SAVE=""
[ "${1:-}" = "--save" ] && SAVE=${2:-}

SSH=$REPO/scripts/gts9-ssh.sh
[ -x "$SSH" ] || { echo "missing $SSH" >&2; exit 1; }

if [ -n "$SAVE" ]; then
	mkdir -p "$SAVE"
	exec > >(tee "$SAVE/preflight.txt") 2>&1
fi

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

# Every read below runs inside ONE remote shell invocation.  The probe must not
# open several console sessions: the ttyGS0 getty defect drops commands, and a
# half-run probe would silently report absence as a property of the hardware.
REMOTE=$(cat <<'REMOTE_EOF'
echo "### identity"
uname -a
echo "uptime=$(cut -d' ' -f1 /proc/uptime)"
echo "boot_id=$(cat /proc/sys/kernel/random/boot_id)"
echo "cmdline=$(cat /proc/cmdline)"
echo
echo "### pci_bus_present"
ls -d /sys/bus/pci >/dev/null 2>&1 && echo "pci_bus=yes" || echo "pci_bus=no"
echo "pci_device_count=$(ls /sys/bus/pci/devices 2>/dev/null | wc -l)"
echo
echo "### pci_devices"
for d in /sys/bus/pci/devices/*; do
  [ -e "$d/vendor" ] || continue
  v=$(cat "$d/vendor" 2>/dev/null); p=$(cat "$d/device" 2>/dev/null)
  drv=$(basename "$(readlink -f "$d/driver" 2>/dev/null)" 2>/dev/null)
  echo "pci_dev $(basename "$d") vendor=$v device=$p driver=${drv:-NONE}"
done
echo
echo "### pcie_controller"
for c in 1c00000.pcie; do
  if [ -e "/sys/bus/platform/devices/$c" ]; then
    if [ -e "/sys/bus/platform/devices/$c/driver" ]; then
      echo "controller $c driver=$(basename "$(readlink -f "/sys/bus/platform/devices/$c/driver")")"
    else
      echo "controller $c driver=UNBOUND"
    fi
  else
    echo "controller $c ABSENT"
  fi
done
echo "pcie_child_nodes=$(ls -d /sys/bus/platform/devices/1c00000.pcie:* 2>/dev/null | wc -l)"
ls -d /sys/bus/platform/devices/1c00000.pcie:* 2>/dev/null | sed 's/^/pcie_child /'
echo
echo "### pcie_phy"
for phy in 1c06000.phy; do
  if [ -e "/sys/bus/platform/devices/$phy/driver" ]; then
    echo "phy $phy driver=$(basename "$(readlink -f "/sys/bus/platform/devices/$phy/driver")")"
  else
    echo "phy $phy driver=UNBOUND"
  fi
done
echo
echo "### pwrseq_and_pmu"
echo "pwrseq_devices=$(ls -d /sys/bus/platform/devices/*wcn* 2>/dev/null | wc -l)"
ls -d /sys/bus/platform/devices/*wcn* 2>/dev/null | sed 's/^/pwrseq_dev /'
if [ -e /sys/bus/platform/devices/wcn6855-pmu/driver ]; then
  echo "wcn6855_pmu_driver=$(basename "$(readlink -f /sys/bus/platform/devices/wcn6855-pmu/driver)")"
else
  echo "wcn6855_pmu_driver=UNBOUND_OR_ABSENT"
fi
echo
echo "### deferred_probe"
cat /sys/kernel/debug/devices_deferred 2>/dev/null | sed 's/^/deferred /'
echo "deferred_count=$(cat /sys/kernel/debug/devices_deferred 2>/dev/null | wc -l)"
echo
echo "### modules"
echo "release=$(uname -r)"
echo "modules_dir=$(ls -d "/lib/modules/$(uname -r)" 2>/dev/null || echo NONE)"
for m in ath ath11k ath11k_pci cfg80211 mac80211 pwrseq-qcom-wcn qrtr-mhi mhi; do
  f=$(find "/lib/modules/$(uname -r)" -name "$m.ko*" 2>/dev/null | head -1)
  echo "module $m.ko ${f:-ABSENT}"
done
echo "lsmod_wlan=$(lsmod 2>/dev/null | grep -cE 'ath11k|cfg80211|mac80211')"
echo
echo "### interfaces"
echo "--- ip link ---"
ip link 2>/dev/null | sed 's/^/iplink /'
echo "--- iw dev (if present) ---"
command -v iw >/dev/null 2>&1 && iw dev 2>/dev/null | sed 's/^/iwdev /' || echo "iwdev iw-not-installed"
echo "--- wireless sysfs ---"
echo "wireless_phys=$(ls -d /sys/class/ieee80211/* 2>/dev/null | wc -l)"
echo "rfkill=$(command -v rfkill >/dev/null 2>&1 && rfkill list 2>/dev/null | wc -l || echo no-rfkill)"
echo
echo "### regulator_and_gpio_state"
echo "--- regulators named vreg_pmu (WCN PMU outputs) ---"
for r in /sys/class/regulator/regulator.*; do
  n=$(cat "$r/name" 2>/dev/null)
  case "$n" in
  vreg_pmu*) echo "reg $n state=$(cat "$r/state" 2>/dev/null) use=$(cat "$r/use_count" 2>/dev/null)";;
  esac
done
echo "--- gpio 80/81/82/94/96/204 (WLAN_EN, BT_EN, SWCTRL, PERST, WAKE, XO) ---"
if [ -d /sys/kernel/debug/gpio ]; then
  grep -E "gpio-(80|81|82|94|96|204)\b" /sys/kernel/debug/gpio 2>/dev/null | sed 's/^/gpio /'
else
  echo "gpio debugfs-unavailable"
fi
echo
echo "### dmesg_pcie"
dmesg 2>/dev/null | grep -aiE "pcie|qcom-pcie|qmp-pcie|17cb|1103|ath11k|wcn|qca|mhi|qrtr" | tail -40 | sed 's/^/dmesg /'
REMOTE_EOF
)

OUT=$("$SSH" "$REMOTE" 2>&1)
rc=$?
printf '%s\n' "$OUT"
[ $rc -eq 0 ] || { say "FATAL: the remote probe failed (rc=$rc)"; exit 1; }

# ---- classify, from the captured text only ---------------------------------
get() { printf '%s\n' "$OUT" | sed -n "s/^$1//p" | tail -1; }

count=$(get 'pci_device_count=')
qca=$(printf '%s\n' "$OUT" | grep -c 'pci_dev .* vendor=0x17cb device=0x1103')
qca_drv=$(printf '%s\n' "$OUT" | sed -n 's/^pci_dev .* vendor=0x17cb device=0x1103 driver=//p' | tail -1)
iwl=$(get 'wireless_phys=')
ath=$(printf '%s\n' "$OUT" | sed -n 's/^lsmod_wlan=//p' | tail -1)
moddir=$(get 'modules_dir=')
defer=$(printf '%s\n' "$OUT" | grep -c 'deferred 1c00000.pcie')

say "---------------------------------------------------------------"
say "RESULT"
say "  pci devices on the bus : ${count:-?}"
say "  17cb:1103 present      : $([ "$qca" -gt 0 ] && echo YES || echo NO)"
say "  17cb:1103 bound driver : ${qca_drv:-n/a}"
say "  cfg80211/mac80211/ath11k loaded : ${ath:-?}"
say "  ieee80211 phy devices  : ${iwl:-?}"
say "  /lib/modules/\$(uname -r) : ${moddir:-?}"
say "  qcom-pcie deferred ('cannot initialize host') : $([ "$defer" -gt 0 ] && echo YES || echo no)"

if [ "$qca" -gt 0 ]; then
	if [ -n "$qca_drv" ] && [ "$qca_drv" != "NONE" ]; then
		if [ "${iwl:-0}" -gt 0 ] 2>/dev/null; then
			say "STATE: E  wlan interface exists - go to association and traffic"
		else
			say "STATE: D  ath11k bound but no wlan interface - inspect firmware/QMI in dmesg"
		fi
	else
		say "STATE: B  17cb:1103 enumerated but unbound - modprobe ath11k_pci, do not rebuild"
	fi
else
	if [ "${count:-0}" -gt 0 ] 2>/dev/null; then
		say "STATE: A2 other PCI devices exist but not 17cb:1103 - link or endpoint problem"
	else
		say "STATE: A  no PCI devices at all - fix PCIe0/PMU/power sequencing"
		say "         host controller state is the place to look, not ath11k"
	fi
fi
say "---------------------------------------------------------------"
