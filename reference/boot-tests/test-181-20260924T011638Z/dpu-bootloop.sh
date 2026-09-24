#!/usr/bin/env bash
# test-181: cold-boot rounds with the DPU flight recorder armed from boot.
#
# Each round uses scripts/console-watch.ps1 to issue the reboot and to observe
# the USB gadget disappear and come back, so the follow-up probe cannot land in
# the session that is still shutting down (the first version did, and lost a
# round's results).  Then it records what that boot did: the panel-recovery
# outcome, the DPU error counters, and the trace summary the flight recorder
# persisted on the microSD.
#
# If a boot never returns, the round stops: the recorder writes its snapshot to
# the microSD, so a hang does not erase the evidence, and the tablet can be
# force-restarted without losing it.
#
#   reference/boot-tests/test-181-*/dpu-bootloop.sh [rounds]
set -uo pipefail

REPO=/home/ms/Samsung/galaxy_tab_s9_linux
D=$(cd "$(dirname "$0")" && pwd)
OUT=$D/bootloop.txt
CR="$REPO/scripts/console-run.ps1"
CW="$REPO/scripts/console-watch.ps1"
PS=powershell.exe
N=${1:-8}

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" | tee -a "$OUT"; }

for i in $(seq 1 "$N"); do
	say "=== boot round $i ==="

	# Issue the reboot and let the watcher observe the USB gap.
	timeout 400 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CW" \
		-Out "C:\\gts9-work\\bl-$i-watch.log" -Seconds 60 \
		-Command 'systemctl reboot' -CommandAtSeconds 10 \
		2>&1 | grep -aE "SENT|PRESENCE usb|watch done" | tee -a "$OUT"

	post=$(timeout 500 "$PS" -NoProfile -ExecutionPolicy Bypass -File "$CR" \
		-Out "C:\\gts9-work\\bl-$i-post.log" -WaitReadySeconds 180 -ReadSeconds 25 \
		-Commands 'echo POST;echo boot_id=$(cat /proc/sys/kernel/random/boot_id);cut -d" " -f1 /proc/uptime;systemctl is-system-running;echo panel_bad=$(dmesg | grep -ac "panel id: 00 00 00");echo panel_ok=$(dmesg | grep -ac "panel id: 80 00 04");echo recovery=$(dmesg | grep -ac "cycle 1 recovered");echo dpu_err=$(dmesg | grep -acE "frame.done.timeout|kickoff.timeout|vblank.wait.timed.out|workqueue.lockup|rcu_preempt");echo flight=$(systemctl is-active gts9-dpu-flight.service);F=/var/log/gts9-dpu-flight.txt;echo lines=$(wc -l < $F);echo "kickoff=$(grep -ac dpu_enc_kickoff $F) fd=$(grep -ac dpu_enc_frame_done_cb $F) pdone=$(grep -ac dpu_enc_phys_cmd_pdone_timeout $F) fdtimeout=$(grep -ac dpu_enc_frame_done_timeout $F) reset=$(grep -ac dpu_enc_prepare_kickoff_reset $F) rc0=$(grep -a dpu_enc_wait_event_timeout $F | grep -ac "rc=0,")"' \
		2>&1)
	echo "$post" | grep -aE "RECV  (POST|boot_id=|running|degraded|panel_bad=|panel_ok=|recovery=|dpu_err=|flight=|lines=|kickoff=|[0-9]+\.[0-9]+)" | tee -a "$OUT"
	if echo "$post" | grep -aq "shell never answered"; then
		say "NO CONSOLE after 180 s: hang suspected; stopping the loop here"
		break
	fi
done
say "boot loop done"
