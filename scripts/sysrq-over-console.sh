#!/usr/bin/env bash
# Host-agnostic front end for scripts/sysrq-over-console.ps1.
#
#   scripts/sysrq-over-console.sh -Port COM19 -SysRq l -ReadSeconds 20
#
# See the .ps1 for why this exists: a boot whose kernel answers ICMP and RSTs
# TCP while its userspace is gone leaves no other way to ask what is stuck.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ps-host.sh
. "$here/ps-host.sh"

port="COM19"; baud=115200; sysrq="l"; read_s=20
out='C:\Users\ms\AppData\Local\Temp\gts9-sysrq.log'
while [ "$#" -gt 0 ]; do
	case "$1" in
	-Port) port="$2"; shift 2 ;;
	-Baud) baud="$2"; shift 2 ;;
	-SysRq) sysrq="$2"; shift 2 ;;
	-ReadSeconds) read_s="$2"; shift 2 ;;
	-Out) out="$2"; shift 2 ;;
	*) echo "sysrq-over-console.sh: unknown argument $1" >&2; exit 2 ;;
	esac
done

args="-Port $(gts9_ps_quote "$port") -Baud $baud -SysRq $(gts9_ps_quote "$sysrq")"
args+=" -ReadSeconds $read_s -Out $(gts9_ps_quote "$out")"
gts9_ps_exec "$here/sysrq-over-console.ps1" "$args"
