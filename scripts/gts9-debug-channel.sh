#!/usr/bin/env bash
# Set up and check the tablet's fast debug channel.
#
# Two subcommands, both idempotent:
#
#   install-key   install this host's public key into /root/.ssh/authorized_keys
#                 on the tablet, over the serial console (the key is ~100 bytes,
#                 which is the one thing the slow console is still good for)
#   check         report whether the whole chain is up: gadget function, address,
#                 ssh, adbd, and the measured rates
#
#   scripts/gts9-debug-channel.sh install-key
#   scripts/gts9-debug-channel.sh check
set -euo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
DEV=${GTS9_DEVICE:-169.254.42.1}
KEY=${GTS9_SSH_KEY:-$HOME/.ssh/gts9_ed25519}
SHELL_PORT=${GTS9_SHELL_PORT:-COM17}
SSH="$repo_root/scripts/gts9-ssh.sh"

usage() {
	sed -n '2,14p' "$0" | sed 's/^# \{0,1\}//'
	exit 2
}

install_key() {
	[ -f "$KEY.pub" ] || {
		echo "debug-channel: no $KEY.pub; create it with" >&2
		echo "  ssh-keygen -t ed25519 -N '' -f $KEY" >&2
		exit 2
	}
	local pub
	pub=$(cat "$KEY.pub")

	# This used to send the key to a shell on the COM17 serial console.  That
	# shell is gone - the autologin getty was deleted and the ttyGS kernel console
	# removed, both because they caused the boot and shutdown stalls
	# (docs/BOOT_CONSOLE_BLOCK.md, docs/SHUTDOWN_DELAY.md).  COM17 is still a
	# working serial port, but nothing reads it and nothing answers on it, so the
	# old command would fail silently: console-run.sh would simply find no shell.
	#
	# Refuse loudly rather than pretend.  A silent failure here is worse than an
	# error, because the operator's next step is to wonder why ssh still asks for
	# a password - and the real answer is that the key never left this host.
	if [ "${GTS9_ALLOW_SERIAL_KEY_INSTALL:-0}" != 1 ]; then
		echo "debug-channel: install-key cannot work any more" >&2
		echo "  The key was written over the COM17 serial console, and no shell runs" >&2
		echo "  on that port now: the autologin getty was deleted and the ttyGS kernel" >&2
		echo "  console removed, because both caused the boot and shutdown stalls." >&2
		echo >&2
		echo "  The port itself still works - it is simply unused - so this path can be" >&2
		echo "  revived deliberately, with a shell on it:" >&2
		echo "    initramfs: add gts9_usb_console=shell to the vendor_boot command line" >&2
		echo "    Debian:    put a getty back on ttyGS0 (not recommended - see" >&2
		echo "               docs/SHUTDOWN_DELAY.md for why it was removed)" >&2
		echo >&2
		echo "  What a fresh rootfs should use instead: install the public key into the" >&2
		echo "  rootfs at install time (install-debian-rootfs.sh --ssh-key), which needs" >&2
		echo "  no channel on the device at all.  See docs/FAST_DEBUG_CHANNEL.md." >&2
		echo >&2
		echo "  To override anyway for a boot that really does have a serial shell:" >&2
		echo "    GTS9_ALLOW_SERIAL_KEY_INSTALL=1 $0 install-key" >&2
		exit 3
	fi

	echo "debug-channel: installing $KEY.pub over $SHELL_PORT (serial, overridden)"
	# shellcheck disable=SC2016
	"$repo_root/scripts/console-run.sh" -Port "$SHELL_PORT" -ReadSeconds 20 \
		-Commands "mkdir -p /root/.ssh && chmod 700 /root/.ssh && touch /root/.ssh/authorized_keys && chmod 600 /root/.ssh/authorized_keys && grep -qF '$pub' /root/.ssh/authorized_keys || echo '$pub' >> /root/.ssh/authorized_keys; echo INSTALLED=\$(wc -l < /root/.ssh/authorized_keys)" \
		| sed -n 's/.*RECV  //p' | grep -a INSTALLED || true
}

check() {
	local ok=0
	echo "debug-channel: checking $DEV"

	if ping -c 2 -W 2 "$DEV" >/dev/null 2>&1; then
		echo "  link      ok   ($(ping -c 2 -W 2 "$DEV" 2>/dev/null | sed -n 's/.*rtt min\/avg\/max\/mdev = \([^ ]*\) .*/\1/p'))"
	else
		echo "  link      DOWN - no route to $DEV"
		echo "            the gadget needs /etc/gts9-usb-net and a re-run of gts9-usb-acm"
		ok=1
	fi

	if "$SSH" 'echo SSH_OK' 2>/dev/null | grep -q SSH_OK; then
		echo "  ssh       ok   ($("$SSH" 'uname -r' 2>/dev/null))"
	else
		echo "  ssh       DOWN - key not installed, or sshd not running"
		echo "            run: $0 install-key"
		ok=1
	fi

	local adbd
	adbd=$("$SSH" 'systemctl is-active gts9-adbd.service' 2>/dev/null || true)
	echo "  adbd      ${adbd:-unknown}"

	if [ -n "${ADB:-}" ] && [ -x "${ADB:-}" ]; then
		"$ADB" connect "$DEV:5555" >/dev/null 2>&1 || true
		echo "  adb       $("$ADB" devices 2>/dev/null | tail -n +2 | head -1)"
	fi

	return "$ok"
}

case "${1:-}" in
install-key) install_key ;;
check) check ;;
*) usage ;;
esac
