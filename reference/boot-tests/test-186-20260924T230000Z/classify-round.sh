#!/bin/sh
# classify-round.sh - apply the pre-agreed decision tree to one capture.
#
# Usage: classify-round.sh LOG [LOG ...]
#
# The tree is fixed in docs/NEXT_STALL_DEBUG_PLAN.md §8; this script only reads
# it back.  It exists so the branch is decided by the log rather than by whoever
# reads it afterwards.
#
# Prints key=value lines and one branch= line:
#
#   no-anomaly                     nothing recognisable happened
#   rpmh-not-programmed            a timeout with no matching send in the ring
#   rpmh-programmed-no-completion  programmed, never completed  -> RSC/TCS/hw/IRQ
#   rpmh-irq-pending               IRQ status bit set, TCS still in use, no done
#                                  -> IRQ delivery / masking / CPU stall
#   rpmh-completed-late            LATE COMPLETION seen -> request-lifetime hazard
#   rpmh-timeout-otherwise         timeout with a completion already observed
#                                  -> completion/lifetime matching
#   victim-<name>                  another anomaly precedes the first RPMh timeout
#
# Every branch is a statement about the log, not about a cause.
set -u

first_ts() {
	# first numeric monotonic timestamp (seconds) on a line matching $1
	grep -a -m1 -E "$1" "$2" 2>/dev/null |
		grep -a -o -E "^\[ *[0-9]+\.[0-9]+" | tr -dc '0-9.'
}

earliest() {
	# earliest non-empty value among the remaining arguments
	best=""
	for v in "$@"; do
		[ -n "$v" ] || continue
		if [ -z "$best" ] || [ "$(printf '%s\n%s\n' "$v" "$best" | sort -g | head -1)" = "$v" ]; then
			best=$v
		fi
	done
	printf '%s' "$best"
}

for log in "$@"; do
	[ -f "$log" ] || continue
	echo "log=$log"

	rpmh_ts=$(first_ts "gts9-rpmh: TIMEOUT" "$log")
	lockup_ts=$(first_ts "soft lockup" "$log")
	wq_ts=$(first_ts "workqueue: .*stall" "$log")
	rcu_ts=$(first_ts "rcu:.*detected stall" "$log")
	dpu_ts=$(first_ts "frame done timeout" "$log")
	mmc_ts=$(first_ts "mmc.*[Tt]imeout" "$log")

	echo "rpmh_timeout_ts=${rpmh_ts:-none}"
	echo "soft_lockup_ts=${lockup_ts:-none}"
	echo "workqueue_stall_ts=${wq_ts:-none}"
	echo "rcu_stall_ts=${rcu_ts:-none}"
	echo "dpu_timeout_ts=${dpu_ts:-none}"
	echo "mmc_timeout_ts=${mmc_ts:-none}"

	summary=$(grep -a -m1 'gts9-rpmh: ring_summary' "$log" 2>/dev/null)
	holder=$(grep -a -m1 'gts9-rpmh: holder_tcs' "$log" 2>/dev/null)
	irq=$(grep -a -m1 'gts9-rpmh: irq_status' "$log" 2>/dev/null)
	late=$(grep -a -c 'gts9-rpmh: LATE COMPLETION' "$log" 2>/dev/null)
	irq_pending=$(grep -a -c -E 'gts9-rpmh: in_use tcs=[0-9]+ irq_bit=1' "$log" 2>/dev/null)

	echo "ring_summary=${summary:-none}"
	echo "holder=${holder:-none}"
	echo "irq=${irq:-none}"
	echo "late_completions=${late:-0}"
	echo "irq_pending_tcs_lines=${irq_pending:-0}"

	if [ -z "$rpmh_ts" ]; then
		other=$(earliest "$lockup_ts" "$wq_ts" "$rcu_ts" "$dpu_ts" "$mmc_ts")
		if [ -n "$other" ]; then
			echo "first_anomaly=other at $other"
			echo "branch=no-rpmh-timeout"
		else
			echo "first_anomaly=none"
			echo "branch=no-anomaly"
		fi
		echo
		continue
	fi

	# Is another anomaly earlier than the RPMh timeout?
	other=$(earliest "$lockup_ts" "$wq_ts" "$rcu_ts" "$dpu_ts" "$mmc_ts")
	if [ -n "$other" ] &&
	   [ "$(printf '%s\n%s\n' "$other" "$rpmh_ts" | sort -g | head -1)" = "$other" ]; then
		echo "first_anomaly=other at $other"
		echo "branch=victim-other-anomaly-earlier"
		echo
		continue
	fi

	matched_send=$(printf '%s' "$summary" | sed -n 's/.*matched_send=\([0-9]*\).*/\1/p')
	matched_done=$(printf '%s' "$summary" | sed -n 's/.*matched_done=\([0-9]*\).*/\1/p')
	holder_tcs=$(printf '%s' "$holder" | sed -n 's/.*holder_tcs=\(-\?[0-9]*\).*/\1/p')
	irq_bit=$(printf '%s' "$irq" | sed -n 's/.*irq_status=0x\([0-9a-fA-F]*\).*/\1/p')

	echo "matched_send=${matched_send:-unknown} matched_done=${matched_done:-unknown}"
	echo "holder_tcs=${holder_tcs:-unknown} irq_status=0x${irq_bit:-unknown}"

	if [ "${late:-0}" -gt 0 ]; then
		echo "first_anomaly=rpmh-timeout at $rpmh_ts (late completion seen)"
		echo "branch=rpmh-completed-late"
	elif [ "${matched_send:-0}" = 0 ] 2>/dev/null; then
		echo "first_anomaly=rpmh-timeout at $rpmh_ts (no matching send)"
		echo "branch=rpmh-not-programmed"
	elif [ "${matched_done:-0}" != 0 ] 2>/dev/null; then
		echo "first_anomaly=rpmh-timeout at $rpmh_ts (completion was seen)"
		echo "branch=rpmh-timeout-otherwise"
	elif [ "${irq_pending:-0}" -gt 0 ] 2>/dev/null && [ "${holder_tcs:-0}" != -1 ] 2>/dev/null; then
		echo "first_anomaly=rpmh-timeout at $rpmh_ts (IRQ bit set, TCS still in use)"
		echo "branch=rpmh-irq-pending"
	else
		echo "first_anomaly=rpmh-timeout at $rpmh_ts"
		echo "branch=rpmh-programmed-no-completion"
	fi
	echo
done
