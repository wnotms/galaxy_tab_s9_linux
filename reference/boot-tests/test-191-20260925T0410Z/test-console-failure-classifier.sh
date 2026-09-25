#!/usr/bin/env bash
# Regression test for wedge-rate.sh's console-failure classifier.
#
# Why this exists: the rate series scores cycles by whether a boot answered, which
# makes the *reason* it did not answer load-bearing.  The harness got that reason
# wrong once, in a way that would have invented a stall:
#
#   06:59:17Z  cycle 1  the harness could not open COM17 at all - nothing was ever
#                       asked of the tablet - and it recorded "console silent and
#                       ssh unreachable: treating it as a stall", because ssh was
#                       only consulted when the console had managed to report a
#                       missing shell.
#
# The classifier is a pure function of the PowerShell output, so it can be tested
# on this host with the real strings and no tablet attached.  Every sample below is
# a real line from a real run, except the two that say otherwise.

set -uo pipefail

here=$(cd "$(dirname "$0")" && pwd)
harness=$here/wedge-rate.sh

if [ ! -r "$harness" ]; then
	echo "cannot read $harness" >&2
	exit 2
fi

# Pull the classifier out of the harness exactly as it is defined, so this test
# cannot drift away from the thing it tests.
classify=$(sed -n '/^probe_console_uptime() {/,/^}/p' "$harness")
if ! grep -q 'CONSOLE_STATE=console-port-failed' <<<"$classify"; then
	echo "could not extract the classifier from $harness" >&2
	exit 2
fi
eval "$classify"

CR=fake-console-run
CONSOLE_PROBE_TIMEOUT=60
WINDIR='C:\fake'
CONSOLE_GOT=""
CONSOLE_STATE=""
PROBE_OUTPUT=""
probe_rc=0

# The stub the classifier calls.  Note the shape it has to imitate: the port-open
# failure is a plain stdout line that exits nonzero and nothing else - that is the
# whole 06:59:17Z capture - so the real classifier distinguishes "never asked" from
# "asked and silent" by reading its own exit code and the text it got back.
timeout() {
	shift			# the duration
	printf '%s\n' "$PROBE_OUTPUT"
	return "$probe_rc"
}
say() { :; }

pass=0
fail=0

# check <expected-state> <expected-uptime|-> <rc> <label>
check() {
	local want_state=$1 want_got=$2 rc=$3 label=$4
	# "-" in the table means "no uptime", which is the empty string.
	[ "$want_got" = "-" ] && want_got=""
	PROBE_OUTPUT=$(cat)
	probe_rc=$rc
	CONSOLE_GOT=""
	CONSOLE_STATE=""
	probe_console_uptime sample >/dev/null 2>&1
	if [ "$CONSOLE_STATE" = "$want_state" ] && [ "$CONSOLE_GOT" = "$want_got" ]; then
		printf 'PASS %-34s state=%-20s uptime=%s\n' "$label" "$CONSOLE_STATE" "${CONSOLE_GOT:--}"
		pass=$((pass + 1))
	else
		printf 'FAIL %-34s want state=%s uptime=%s, got state=%s uptime=%s\n' \
			"$label" "$want_state" "${want_got:--}" "$CONSOLE_STATE" "${CONSOLE_GOT:--}"
		fail=$((fail + 1))
	fi
}

# --- the exact failure that motivated the classifier -------------------------
# Real: one line, exit nonzero, and nothing was asked of the tablet.
check console-port-failed - 1 "port could not be opened" <<'EOF'
2026-09-25T06:59:17Z could not open COM17
EOF

# --- the timeout: the port opened, the console said nothing, we gave up -------
# The real run exits via `timeout`, whose 124 distinguishes this from the capture
# above.  Not a real capture; constructed from console-run.ps1's output shape.
check console-timeout - 124 "port open, probe timed out" <<'EOF'
2026-09-25T07:10:00Z console open on COM17
2026-09-25T07:10:30Z console run done (ready=False)
EOF

# --- a real successful probe (04:48:39Z, the 53.70 s boot) -------------------
check ok 53 0 "real successful probe" <<'EOF'
2026-09-25T04:48:32Z console open on COM17
2026-09-25T04:48:33Z RECV  echo READY1
2026-09-25T04:48:33Z RECV  [?2004lREADY1
2026-09-25T04:48:33Z shell answered after 1 poll(s)
2026-09-25T04:48:39Z RECV  [?2004lGTS9_ALIVE_53.70_END
2026-09-25T04:48:39Z console run done (ready=True)
EOF

# --- the getty defect: the port opened, the shell answered, no result ---------
# Real, from the healthy test-191 boot.  This is the reading that must be
# attributed against ssh before it is allowed to count as anything.
check console-no-result - 0 "shell answered, no result" <<'EOF'
2026-09-25T04:47:49Z console open on COM17
2026-09-25T04:47:49Z RECV  echo READY2
2026-09-25T04:47:49Z RECV  [?2004lREADY2
2026-09-25T04:47:49Z shell answered after 2 poll(s)
2026-09-25T04:47:54Z RECV  [?2004lGTS9_ALIVE_$(cut -d" " -f1 /proc/uptime)_END
2026-09-25T04:47:54Z console run done (ready=True)
EOF

# --- port opened, nothing ever answered --------------------------------------
check console-no-shell - 0 "port open, nothing answered" <<'EOF'
2026-09-25T04:47:49Z console open on COM17
2026-09-25T04:47:52Z console run done (ready=False)
EOF

# --- the decimal point: an integer-only pattern matches nothing ---------------
# Not a real capture: this is the regression the pattern exists to prevent.
check ok 889 0 "fractional uptime keeps its point" <<'EOF'
2026-09-25T04:48:33Z shell answered after 1 poll(s)
2026-09-25T04:48:39Z RECV  [?2004lGTS9_ALIVE_889.01_END
EOF

echo "---"
echo "console-failure classifier: $pass passed, $fail failed"
[ "$fail" -eq 0 ] || exit 1
