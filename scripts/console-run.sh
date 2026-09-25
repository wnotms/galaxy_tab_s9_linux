#!/usr/bin/env bash
# Host-agnostic front end for scripts/console-run.ps1.
#
# Usage - the same options console-run.ps1 takes:
#
#   scripts/console-run.sh -Port COM17 -Out 'C:\tmp\x.log' \
#       -WaitReadySeconds 60 -ReadSeconds 5 -Commands 'uptime' 'dmesg | tail -3'
#
# `-Commands` must come last: every argument after it is one command.  An empty
# command string means "listen only, send nothing".  Host detection and the
# staging/array workarounds live in scripts/ps-host.sh.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ps-host.sh
. "$here/ps-host.sh"

port="COM17"
out='C:\Users\Public\gts9-console-run.log'
wait=120
read_s=4
poll=1000
baud=115200
cmds=()

while [ "$#" -gt 0 ]; do
	case "$1" in
	-Port) port="$2"; shift 2 ;;
	-Out) out="$2"; shift 2 ;;
	-WaitReadySeconds) wait="$2"; shift 2 ;;
	-ReadSeconds) read_s="$2"; shift 2 ;;
	-PollMs) poll="$2"; shift 2 ;;
	-Baud) baud="$2"; shift 2 ;;
	-Commands)
		shift
		while [ "$#" -gt 0 ]; do cmds+=("$1"); shift; done
		;;
	*)
		echo "console-run.sh: unknown argument $1" >&2
		exit 2
		;;
	esac
done

if [ "${#cmds[@]}" -eq 0 ]; then
	echo "console-run.sh: at least one -Commands value is required" >&2
	exit 2
fi

args="-Port $(gts9_ps_quote "$port") -Out $(gts9_ps_quote "$out")"
args+=" -WaitReadySeconds $wait -ReadSeconds $read_s -PollMs $poll -Baud $baud"
args+=" -Commands $(gts9_ps_array "${cmds[@]}")"

gts9_ps_exec "$here/console-run.ps1" "$args"
