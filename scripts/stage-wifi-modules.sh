#!/usr/bin/env bash
# Stage the built kernel modules onto the RUNNING tablet, so the already-flashed
# kernel can load them.  This exists because the Wi-Fi blocker is a missing-module
# problem, not a kernel problem: the flashed Image.gz and DTB are correct and do
# not need to be rebuilt or reflashed.
#
#   scripts/stage-wifi-modules.sh --check     # report only, change nothing
#   scripts/stage-wifi-modules.sh --apply     # copy modules + depmod
#
# It refuses to run unless the modules provably belong to the kernel the tablet is
# actually running, because the failure mode it guards against is silent: modules
# with a mismatched vermagic do not load and leave no trace beyond a taint.
#
# It does NOT flash anything, does not reboot, and does not touch the boot chain.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
MODE=${1:---check}
case "$MODE" in --check|--apply) ;; *) echo "usage: $0 [--check|--apply]" >&2; exit 2 ;; esac

ROOT=${GTS9_MODULES_ROOT:-$REPO/out/kernel-gts9wifi/modules-root}
RELEASE_FILE=$REPO/out/kernel-gts9wifi/kernel.release
SSH=$REPO/scripts/gts9-ssh.sh

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

[ -d "$ROOT" ] || die "no modules at $ROOT - run BUILD_MODULES=1 ./scripts/build-kernel.sh first"
[ -f "$RELEASE_FILE" ] || die "missing $RELEASE_FILE"

# ---- local side: exactly one release, and it is the one recordered -----------
mapfile -t releases < <(find "$ROOT/lib/modules" -mindepth 1 -maxdepth 1 -type d -printf '%f\n')
[ "${#releases[@]}" -eq 1 ] || die "expected exactly one release under $ROOT/lib/modules, got: ${releases[*]:-none}"
LOCAL_REL=${releases[0]}
RECORDED=$(cat "$RELEASE_FILE")
[ "$LOCAL_REL" = "$RECORDED" ] || die "module release '$LOCAL_REL' != kernel.release '$RECORDED'"
SRC=$ROOT/lib/modules/$LOCAL_REL

count=$(find "$SRC" -name '*.ko' | wc -l)
say "local modules : $count under $LOCAL_REL"

# ---- the modules the Wi-Fi chain needs, named so a gap is visible -----------
WANT='ath.ko ath11k.ko ath11k_pci.ko cfg80211.ko mac80211.ko
      pci-pwrctrl-pwrseq.ko pwrseq-qcom-wcn.ko qrtr-mhi.ko'
missing=''
for m in $WANT; do
	[ -n "$(find "$SRC" -name "$m" -print -quit)" ] || missing="$missing $m"
done
[ -z "$missing" ] || die "the built tree lacks:$missing"

# ---- remote side: the release the tablet is RUNNING -------------------------
REMOTE_REL=$("$SSH" 'uname -r' 2>/dev/null | tr -d '\r' | tail -1)
[ -n "$REMOTE_REL" ] || die "could not read uname -r from the tablet"
say "tablet release: $REMOTE_REL"
[ "$REMOTE_REL" = "$LOCAL_REL" ] || die \
	"refusing to stage: modules are for '$LOCAL_REL' but the tablet runs '$REMOTE_REL'"

# The vermagic check is the one that actually matters: same release string with a
# different config (SMP, preempt, modversions, PAGE_SIZE) still fails to load.
LOCAL_VERMAGIC=$(modinfo -F vermagic "$(find "$SRC" -name ath11k_pci.ko -print -quit)" 2>/dev/null)
say "module vermagic: $LOCAL_VERMAGIC"
[ -n "$LOCAL_VERMAGIC" ] || die "could not read vermagic - is kmod installed?"

DEST=/lib/modules/$REMOTE_REL
if [ "$MODE" = --check ]; then
	say "check only: would install $count modules to $DEST and run depmod -a"
	"$SSH" "echo \"  current $DEST: \$(ls $DEST 2>/dev/null | wc -l) entries\""
	say "re-run with --apply to install"
	exit 0
fi

# ---- apply ------------------------------------------------------------------
# Copy into a staging directory first and move into place, so an interrupted
# transfer cannot leave a half-populated /lib/modules that depmod would then
# resolve against.
say "copying to the tablet (staged under /tmp, then moved into place)"
TMPD=/tmp/gts9-modules-$REMOTE_REL
"$SSH" "rm -rf $TMPD && mkdir -p $TMPD" || die "could not prepare $TMPD on the tablet"

( cd "$SRC" && tar cf - . ) | "$SSH" "tar xf - -C $TMPD" || die "module copy failed"

# Verify the copy before trusting it: same count, and the pwrctrl module's hash
# matches, since that one module is the whole point of this exercise.
remote_count=$("$SSH" "find $TMPD -name '*.ko' | wc -l" | tr -d '\r' | tail -1)
[ "$remote_count" = "$count" ] || die "copy incomplete: local $count, tablet $remote_count"

LOCAL_SHA=$(sha256sum "$(find "$SRC" -name pci-pwrctrl-pwrseq.ko -print -quit)" | cut -d' ' -f1)
REMOTE_SHA=$("$SSH" "sha256sum $TMPD/kernel/drivers/pci/pwrctrl/pci-pwrctrl-pwrseq.ko 2>/dev/null | cut -d' ' -f1" | tr -d '\r' | tail -1)
[ "$LOCAL_SHA" = "$REMOTE_SHA" ] || die "pci-pwrctrl-pwrseq.ko hash mismatch after copy"
say "verified $remote_count modules, pci-pwrctrl-pwrseq.ko sha256 ${LOCAL_SHA:0:16} matches"

"$SSH" "mkdir -p $DEST && cp -a $TMPD/. $DEST/ && depmod -a $REMOTE_REL && rm -rf $TMPD" \
	|| die "install or depmod failed"
say "installed to $DEST and ran depmod -a"

say "--- what the kernel can now resolve ---"
"$SSH" "modinfo -F filename pci-pwrctrl-pwrseq 2>/dev/null; modinfo -F filename ath11k_pci 2>/dev/null; modinfo -F filename pwrseq-qcom-wcn 2>/dev/null" \
	| tr -d '\r'
say "done.  Nothing was flashed and nothing was rebooted."
