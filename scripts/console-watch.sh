#!/usr/bin/env bash
# Host-agnostic front end for scripts/console-watch.ps1.
#
# console-run.ps1 is "run these commands and return"; this is the opposite: hold
# the port open for a whole window, timestamp every line, and notice exactly when
# the USB gadget disappears.  That is what a shutdown test needs, because the
# tablet resets underneath the observer.
#
#   scripts/console-watch.sh -Out 'C:\tmp\w.log' -Seconds 900 -Port COM19
#   scripts/console-watch.sh -Out 'C:\tmp\w.log' -Seconds 120 \
#       -Command 'systemctl reboot' -CommandAtSeconds 15
#
# All arguments are passed through to console-watch.ps1 by name:
#
#   -Port -Out -Seconds -Command -CommandAtSeconds -PollMs -UsbInstanceLike
#
# `-Command ''` (the default) means listen only.  Host detection and the staging
# workaround live in scripts/ps-host.sh.
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=ps-host.sh
. "$here/ps-host.sh"

args=""
while [ "$#" -gt 0 ]; do
	case "$1" in
	-Port | -Out | -Command | -UsbInstanceLike)
		[ "$#" -ge 2 ] || { echo "console-watch.sh: $1 needs a value" >&2; exit 2; }
		args+=" $1 $(gts9_ps_quote "$2")"
		shift 2
		;;
	-Seconds | -CommandAtSeconds | -PollMs)
		[ "$#" -ge 2 ] || { echo "console-watch.sh: $1 needs a value" >&2; exit 2; }
		args+=" $1 $2"
		shift 2
		;;
	*)
		echo "console-watch.sh: unknown argument $1" >&2
		exit 2
		;;
	esac
done

gts9_ps_exec "$here/console-watch.ps1" "${args# }"
