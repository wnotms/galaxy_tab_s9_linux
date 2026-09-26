#!/usr/bin/env bash
# Read-only Bluetooth preflight for the X710's QCA6490 / WCN6855.
#
#   scripts/bluetooth-preflight.sh            # collect from the running tablet
#   scripts/bluetooth-preflight.sh --local    # collect from this host instead
#
# This script exists to answer one question with evidence rather than inference:
# does the kernel's own power-sequencing path actually reach BT_EN (GPIO81), and
# how far does the controller get before something fails?
#
# It is strictly READ-ONLY on the tablet. It does not write a GPIO, unload a
# module (Wi-Fi shares the PMU and stays up), reset the PMU, touch SPMI, change a
# regulator, mount or write any Android partition, or modify firmware. The only
# remote commands it runs are reads: cat, ls, find, grep, dmesg, modinfo, and the
# two BlueZ query tools that report state (btmgmt info / bluetoothctl show).
#
# The bring-up order it reports against, from the round's brief:
#
#   LEVEL 0  config / modules          LEVEL 5  rampatch request
#   LEVEL 1  uart14 / serdev bind      LEVEL 6  NVM request
#   LEVEL 2  wcn6855 pwrseq match      LEVEL 7  hci0
#   LEVEL 3  BT_EN GPIO81 high         LEVEL 8  BlueZ power on
#   LEVEL 4  QCA ROM version read      LEVEL 9+ scan / pair / reconnect
#
# Nothing here decides pass/fail; it prints what the system says so the lowest
# failing level can be named from evidence.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
MODE=${1:-}

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

case "$MODE" in
""|--local) ;;
*) echo "usage: $0 [--local]" >&2; exit 2 ;;
esac

# Everything below runs through run(); --local swaps the transport so the same
# probe set can be captured from a saved environment or a development host.
if [ "$MODE" = "--local" ]; then
	run() { bash -c "$1" 2>&1; }
else
	command -v ssh >/dev/null || die "ssh required"
	[ -f "${GTS9_SSH_KEY:-$HOME/.ssh/gts9_ed25519}" ] || die "no ssh key (see scripts/gts9-ssh.sh)"
	run() { "$REPO/scripts/gts9-ssh.sh" "$1" 2>&1; }
	run true >/dev/null 2>&1 || die "tablet unreachable over the USB link"
fi

hdr() { printf '\n===== %s =====\n' "$*"; }

# A helper for the yes/no questions, so the output reads as answers and not as
# raw dumps. Each one is a read.
q() { # q LABEL COMMAND
	printf '%-34s %s\n' "$1" "$(run "$2" | tr -d '\r' | head -1)"
}

hdr "identity"
run 'uname -a; echo "cmdline: $(cat /proc/cmdline)"'
run 'echo "uptime: $(uptime -p)"; echo "boot_id: $(cat /proc/sys/kernel/random/boot_id)"'

# ---------------------------------------------------------------------------
# LEVEL 0 - configuration and modules
# ---------------------------------------------------------------------------
hdr "LEVEL 0 - modules and vermagic"
run 'lsmod | grep -Ei "bluetooth|btqca|btbcm|hci_uart|pwrseq|hci" || echo "(no bluetooth modules loaded)"'
echo
# The brief requires proving the loaded modules match the running kernel. A
# mismatched vermagic is the classic cause of a driver that "should" work.
run 'for m in bluetooth btqca hci_uart pwrseq_qcom_wcn; do
	if modinfo "$m" >/dev/null 2>&1; then
		printf "%-18s vermagic=%s\n" "$m" "$(modinfo -F vermagic "$m" 2>/dev/null)"
		printf "%-18s filename=%s\n" "" "$(modinfo -F filename "$m" 2>/dev/null)"
	else
		printf "%-18s NOT AVAILABLE\n" "$m"
	fi
done'
echo
q "running kernel release" 'uname -r'

# The config symbols that make this path possible at all.
hdr "LEVEL 0 - kernel config symbols (from the running kernel)"
run 'for s in BT BT_QCA BT_HCIUART BT_HCIUART_SERDEV BT_HCIUART_QCA SERIAL_DEV_BUS POWER_SEQUENCING POWER_SEQUENCING_QCOM_WCN BT_HCIUART_H4; do
	if [ -r /proc/config.gz ]; then
		zcat /proc/config.gz | grep -E "^CONFIG_${s}=" || echo "CONFIG_${s} (absent)"
	elif [ -r "/boot/config-$(uname -r)" ]; then
		grep -E "^CONFIG_${s}=" "/boot/config-$(uname -r)" || echo "CONFIG_${s} (absent)"
	else
		echo "(no readable kernel config on the device)"
		break
	fi
done'

# ---------------------------------------------------------------------------
# LEVEL 1 - uart14 / serdev bind
# ---------------------------------------------------------------------------
hdr "LEVEL 1 - serdev and uart14 (QUP SE14, 0x898000)"
run 'echo "--- /sys/bus/serial/devices ---"; ls -l /sys/bus/serial/devices/ 2>/dev/null || echo "(none)"'
echo
run 'for d in /sys/bus/serial/devices/*; do
	[ -e "$d" ] || continue
	printf "%s\n" "$(basename "$d")"
	printf "  driver   : %s\n" "$(basename "$(readlink -f "$d/driver" 2>/dev/null)" 2>/dev/null)"
	printf "  modalias : %s\n" "$(cat "$d/modalias" 2>/dev/null)"
done'
echo
run 'echo "--- platform devices matching 898000 / uart ---"
for p in /sys/bus/platform/devices/*; do
	case "$(basename "$p")" in
		*898000*|*uart*|*serial*) echo "  $(basename "$p") -> $(basename "$(readlink -f "$p/driver" 2>/dev/null)" 2>/dev/null)";;
	esac
done'

# ---------------------------------------------------------------------------
# LEVEL 2 - pwrseq provider and consumer
# ---------------------------------------------------------------------------
hdr "LEVEL 2 - pwrseq provider (wcn6855_pmu -> pwrseq-qcom-wcn)"
run 'echo "--- /sys/bus/pwrseq/devices ---"; ls -l /sys/bus/pwrseq/devices/ 2>/dev/null || echo "(no pwrseq bus)"'
echo
run 'echo "--- pwrseq driver bound ---"
for d in /sys/bus/platform/devices/*pwrseq* /sys/devices/platform/*pmu*; do
	[ -e "$d" ] || continue
	printf "  %s\n" "$d"
	printf "    driver: %s\n" "$(basename "$(readlink -f "$d/driver" 2>/dev/null)" 2>/dev/null)"
	printf "    of:     %s\n" "$(cat "$d/of_node/compatible" 2>/dev/null | tr "\0" " ")"
done'
echo
run 'echo "--- module refcounts (a held pwrseq means a consumer exists) ---"
grep -E "pwrseq_qcom_wcn|hci_uart|btqca" /proc/modules 2>/dev/null || echo "(none)"'

# ---------------------------------------------------------------------------
# LEVEL 3 - BT_EN, the control that matters most
# ---------------------------------------------------------------------------
hdr "LEVEL 3 - control GPIOs (owner / direction / value)"
# The four pins from the board DTS: 80 WLAN_EN, 81 BT_EN, 82 SWCTRL, 204 XO.
# requested = a driver owns it; out high = the sequencer drove it.
run 'if [ -r /sys/kernel/debug/gpio ]; then
	grep -E "gpio(80|81|82|204) " /sys/kernel/debug/gpio || echo "(pins not listed)"
else
	echo "(debugfs gpio not readable - mount debugfs or check permissions)"
fi'
echo
run 'echo "--- gpio debugfs header (shows the chip layout) ---"
head -3 /sys/kernel/debug/gpio 2>/dev/null || echo "(unavailable)"'

# ---------------------------------------------------------------------------
# LEVEL 4 - how far did the controller get
# ---------------------------------------------------------------------------
hdr "LEVEL 4-7 - hci_qca / btqca trace"
run 'dmesg | grep -Ei "bluetooth|hci0|btqca|hci_uart|hci_qca|qca |wcn|898000|uart14|pwrseq|serial0-0" | tail -60'
echo
run 'echo "--- /sys/class/bluetooth ---"; ls -l /sys/class/bluetooth/ 2>/dev/null || echo "(no hci device)"'
echo
run 'echo "--- deferred probes (a deferred hci_qca means provider ordering) ---"
cat /sys/kernel/debug/devices_deferred 2>/dev/null || echo "(none / not readable)"'

# ---------------------------------------------------------------------------
# firmware: what the driver asked for, and what is present
# ---------------------------------------------------------------------------
hdr "LEVEL 5-6 - firmware requests and what exists"
run 'echo "--- files the driver requested ---"
dmesg | grep -Ei "Direct firmware load|QCA Downloading|Failed to request file|QCA Failed" | tail -20'
echo
run 'echo "--- what is actually installed ---"
ls -l /lib/firmware/qca/ 2>/dev/null | head -30 || echo "(/lib/firmware/qca does not exist)"
echo
echo "--- firmware search path ---"
cat /sys/module/firmware_class/parameters/path 2>/dev/null | sed "s/^/  firmware_class.path = /"'

# ---------------------------------------------------------------------------
# BlueZ view
# ---------------------------------------------------------------------------
hdr "LEVEL 7-8 - controller as BlueZ sees it"
run 'command -v btmgmt >/dev/null && btmgmt info 2>&1 | head -20 || echo "(btmgmt not installed)"'
echo
run 'command -v rfkill >/dev/null && rfkill list 2>&1 || echo "(rfkill not installed)"'
echo
run 'command -v bluetoothctl >/dev/null && bluetoothctl show 2>&1 | head -20 || echo "(bluetoothctl not installed)"'
echo
run 'command -v hciconfig >/dev/null && hciconfig -a 2>&1 | head -20 || echo "(hciconfig not installed - it is deprecated; btmgmt is authoritative)"'
echo
q "bluetooth.service active" 'systemctl is-active bluetooth.service 2>/dev/null || echo unknown'
q "bluez version" 'bluetoothd --version 2>/dev/null || dpkg-query -W -f="\${Version}" bluez 2>/dev/null || echo unknown'

hdr "done"
say "preflight complete - nothing was written to the tablet"
