#!/usr/bin/env bash
# Is the tablet's KERNEL alive, or is only its userspace and console blocked?
#
# This exists because on 2026-09-25T06:0xZ the tablet showed a stuck cursor and a
# dead keyboard, the operator could not restart it, the serial console refused
# writes ("WriteLine timeout") and ssh refused connections.  Every instrument this
# project had said "dead".  The kernel answered ICMP 3/3 at 2 ms.
#
# So "the console went silent" is NOT the same claim as "the kernel died", and the
# difference matters: the project has read console and journal silence as a
# system-wide freeze in several rounds.  A live kernel can present exactly like a
# dead one on console, journal and ssh, because all three depend on paths that the
# failure breaks - userspace for ssh, the tty/gadget path for the console, and the
# storage path for the journal - while the network stack needs none of them.
#
# Probes, cheapest and most independent first:
#
#   link     the NCM adapter is Up
#   arp      the tablet's MAC resolves at layer 2 (the gadget is enumerated)
#   icmp     the kernel's network stack answers          <- kernel liveness
#   ssh      userspace is far enough along to run sshd
#   console  the ttyGS0 shell EXECUTES a command, not merely echoes it
#
# Read-only: it pings, resolves ARP, opens a TCP connection and runs one echo over
# the console.  It writes nothing to the tablet and reboots nothing.
#
#   scripts/gts9-kernel-alive.sh            # key=value verdict on stdout
#
set -uo pipefail

repo_root=$(cd "$(dirname "$0")/.." && pwd)
target=${GTS9_TARGET:-169.254.42.1}
shell_port=${GTS9_SHELL_PORT:-COM17}
powershell=${POWERSHELL:-powershell.exe}
skip_console=${GTS9_SKIP_CONSOLE:-0}

ps() { timeout 60 "$powershell" -NoProfile -Command "$1" 2>/dev/null | tr -d '\r'; }

# `Status` comes back as an enum whose text form is what we want, but filtering on
# it in the same expression proved fragile; ask for it and compare here instead.
link=down
link_text=$(ps "(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object InterfaceDescription -match 'UsbNcm').Status" | head -1)
case "$link_text" in
	Up|up) link=up ;;
	*) link=down ;;
esac

arp=none
neigh=$(ps "(Get-NetNeighbor -IPAddress $target -ErrorAction SilentlyContinue).State")
case "$neigh" in
	*Reachable*|*Permanent*|*Stale*) arp=reachable ;;
	*) arp=none ;;
esac

icmp=0
if timeout 60 ping.exe -n 3 -w 1500 "$target" >/dev/null 2>&1; then
	icmp=1
fi

ssh=down
if timeout 45 "$repo_root/scripts/gts9-ssh.sh" 'true' >/dev/null 2>&1; then
	ssh=up
fi

console=blocked
console_note="skipped (GTS9_SKIP_CONSOLE=1)"
if [ "$skip_console" != "1" ]; then
	out=$(timeout 150 "$repo_root/scripts/console-run.sh" -Port "$shell_port" \
		-Out 'C:\Users\ms\AppData\Local\Temp\gts9-wedge\kernel-alive.log' \
		-WaitReadySeconds 20 -ReadSeconds 8 \
		-Commands 'echo GTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END' 2>&1)
	if grep -aqE 'GTS9_ALIVE_[0-9]+_END' <<<"$out"; then
		console=live
		console_note="$(sed -n 's/.*GTS9_ALIVE_\([0-9]*\)_END.*/\1/p' <<<"$out" | tail -1)s uptime"
	elif grep -aq 'WriteLine' <<<"$out"; then
		console=blocked
		console_note="the host could not write to the port at all"
	else
		console=blocked
		console_note="no command result; echoed or nothing"
	fi
fi

# The verdict is a pair, not a single state, because the whole point is that the
# two come apart.
if [ "$icmp" = 1 ]; then
	kernel=alive
else
	kernel=dead-or-unreachable
fi
if [ "$ssh" = up ]; then
	userspace=up
else
	userspace=blocked
fi

echo "link=$link"
echo "link_text=${link_text:-none}"
echo "arp=$arp"
echo "icmp=$icmp"
echo "ssh=$ssh"
echo "console=$console"
echo "console_note=$console_note"
echo "kernel=$kernel"
echo "userspace=$userspace"

if [ "$icmp" = 1 ] && [ "$ssh" != up ]; then
	echo "reading=the kernel is running and userspace is not usable"
	echo "         console and ssh cannot see this state; they are not liveness tests"
elif [ "$icmp" = 0 ] && [ "$link" = up ] && [ "$arp" = reachable ]; then
	echo "reading=the gadget is enumerated but the network stack does not answer"
	echo "         the kernel is not servicing its own network path"
elif [ "$icmp" = 0 ] && [ "$link" = down ]; then
	echo "reading=no link at all; the tablet is off, resetting, or the gadget is gone"
else
	echo "reading=normal: kernel and userspace both answering"
fi
