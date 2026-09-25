#!/usr/bin/env bash
# Host-agnostic front end for scripts/sysrq-over-console.ps1.
#
# ============================================================================
# UNSUPPORTED ON GTS9 TTYGS.  This is a NEGATIVE TEST, not a debugger.
#
# Serial SysRq cannot work over ttyGS1/COM19, for two independent reasons:
#   1. the USB adapter refuses to assert BREAK - setting BreakState raises
#      "the device does not have permission to send a break" - and serial SysRq
#      requires a BREAK;
#   2. ttyGS1 is a USB gadget tty, not a uart_port, so serial_core's SysRq path
#      never runs for it.
# Measured on 2026-09-25, recorded in
# reference/boot-tests/test-194-20260925T0906Z/README.md.
#
# It refuses to do anything unless given --probe-unsupported-path, so that it
# cannot be mistaken for a way to interrogate a wedged boot.
# ============================================================================
#
#   scripts/sysrq-over-console.sh -Port COM19 -SysRq l -ReadSeconds 20
#
# See the .ps1 for why this exists: a boot whose kernel answers ICMP and RSTs
# TCP while its userspace is gone leaves no other way to ask what is stuck.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ps-host.sh
. "$here/ps-host.sh"

port="COM19"; baud=115200; sysrq="l"; read_s=20; probe=0
out='C:\Users\ms\AppData\Local\Temp\gts9-sysrq.log'
while [ "$#" -gt 0 ]; do
	case "$1" in
	-Port) port="$2"; shift 2 ;;
	-Baud) baud="$2"; shift 2 ;;
	-SysRq) sysrq="$2"; shift 2 ;;
	-ReadSeconds) read_s="$2"; shift 2 ;;
	-Out) out="$2"; shift 2 ;;
	--probe-unsupported-path) probe=1; shift ;;
	*) echo "sysrq-over-console.sh: unknown argument $1" >&2; exit 2 ;;
	esac
done

if [ "$probe" != "1" ]; then
	cat >&2 <<'EOF'
UNSUPPORTED ON GTS9 TTYGS: serial SysRq cannot work on this port.
  * the USB serial adapter refuses to assert BREAK;
  * ttyGS1 is a USB gadget tty, not a uart_port, so serial_core's SysRq path
    never runs for it.
So this cannot interrogate a wedged boot, and pstore remains the only instrument
that survives one.  See reference/boot-tests/test-194-20260925T0906Z/README.md.
Re-run with --probe-unsupported-path to reproduce the failure deliberately.
EOF
	exit 3
fi

args="-Port $(gts9_ps_quote "$port") -Baud $baud -SysRq $(gts9_ps_quote "$sysrq")"
args+=" -ReadSeconds $read_s -Out $(gts9_ps_quote "$out") -ProbeUnsupportedPath"
gts9_ps_exec "$here/sysrq-over-console.ps1" "$args"
