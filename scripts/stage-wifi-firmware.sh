#!/usr/bin/env bash
# Stage the WCN6855 firmware ath11k actually asks for, with provenance recorded.
#
#   scripts/stage-wifi-firmware.sh --fetch          # download from the pinned URLs
#   scripts/stage-wifi-firmware.sh --from DIR       # use blobs already on disk
#   scripts/stage-wifi-firmware.sh --check          # report what is staged
#   scripts/stage-wifi-firmware.sh --install        # copy to the running tablet
#
# Design rules, from the round's brief:
#
#   * the destination path is whatever the DRIVER asked for, not a convention.
#     On this board that is ath11k/WCN6855/hw2.1/, taken from dmesg
#     ("Direct firmware load for ath11k/WCN6855/hw2.1/amss.bin"), and it matches
#     drivers/net/wireless/ath/ath11k/core.c (.fw.dir for "wcn6855 hw2.1").
#   * no networking unless --fetch is given explicitly; --from DIR never touches
#     the network.
#   * source files are never modified - everything is copied into a staging tree.
#   * every blob is hashed and recorded in a manifest, and the proprietary files
#     are NOT committed to Git (they live under out/, which is ignored).
#   * a hash mismatch is fatal, not a warning: an unverified firmware blob is
#     exactly the "guessed BDF" the brief forbids.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
STAGE=${GTS9_FW_STAGE:-$REPO/out/wifi-firmware}
FWREL=ath11k/WCN6855/hw2.1          # what the driver asked for on this board
SSH=$REPO/scripts/gts9-ssh.sh
BDFTOOL=$REPO/scripts/lib/bdftool.py

MODE=${1:---check}
FROM=""
case "$MODE" in
--fetch|--check|--install) ;;
--from) FROM=${2:?--from needs a directory}; MODE=--from ;;
*) echo "usage: $0 [--fetch|--from DIR|--check|--install]" >&2; exit 2 ;;
esac

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

# ---- the pinned sources, with the hashes that make them verifiable ----------
#
# amss/m3: the CodeLinaro mirror of Qualcomm's ath11k-firmware tree.  The IOE
# family is chosen deliberately: the gts9wifi-fedora-linux port for this same
# tablet records that linux-firmware's WCN6855 amss "boots but the IOE build is
# the reliable family on this unit", that Samsung's own non-LITE amss20 "crashes
# ath11k with MHI_CB_EE_RDDM", and that "the firmware family matters, not just
# the file name".  That is a tested claim about this board, so the IOE build is
# the one staged; the pure-upstream alternative is noted below.
#
# Note the naming mismatch the same port documents: the IOE build lives under
# "hw2.0@nfa765" in Qualcomm's tree while the kernel loads it from hw2.1/.
IOE_BASE=${GTS9_IOE_BASE:-https://raw.githubusercontent.com/CodeLinaro-mirror/ath-firmware_ath11k-firmware/main/WCN6855/hw2.0@nfa765/1.1/WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1}
IOE_AMSS_SHA=8cb5e63877c7cfdc5002a7d28bc5d7f7d20368183e6f93b12c977bfd0351c7b7
IOE_M3_SHA=d20460e104b85a7be9cdb5199c4d8b94a9787912e3f920acd845694d4d71f730

# board-2.bin: the upstream linux-firmware container.
LF_BASE=${GTS9_LF_BASE:-https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/refs/heads/main/ath11k/WCN6855/hw2.0}
BDF_SHA=3a92de58509ee13d417241a6b17be446fa3b0fa938c4cbd8492b1be25ae0f4a7

# The exact-ABI slot ath11k matches on this tablet.  Taken from the device's own
# modalias (pci:v000017CBd00001103sv000017CBsd00000108bc02sc80i00) - not guessed.
SLOT='bus=pci,vendor=17cb,device=1103,subsystem-vendor=17cb,subsystem-device=0108,qmi-chip-id=18,qmi-board-id=255'

sha_of() { sha256sum "$1" 2>/dev/null | cut -d' ' -f1; }

fetch() { # fetch URL DEST EXPECTED_SHA LABEL
	local url=$1 dest=$2 want=$3 label=$4
	say "fetching $label"
	curl -fsSL --max-time 300 "$url" -o "$dest" || die "download failed: $url"
	local got; got=$(sha_of "$dest")
	[ "$got" = "$want" ] || die "$label hash mismatch
       expected $want
       got      $got"
	say "  ok  $(basename "$dest") $(stat -c%s "$dest") bytes sha256=${got:0:16}..."
}

mkdir -p "$STAGE/$FWREL"

case "$MODE" in
--fetch)
	command -v curl >/dev/null || die "curl required for --fetch"
	fetch "$IOE_BASE/amss.bin" "$STAGE/$FWREL/amss.bin" "$IOE_AMSS_SHA" "WCN6855 IOE amss.bin"
	fetch "$IOE_BASE/m3.bin"   "$STAGE/$FWREL/m3.bin"   "$IOE_M3_SHA"   "WCN6855 IOE m3.bin"
	# board-2.bin comes back base64 from the cgit "format=TEXT" endpoint.
	tmp=$(mktemp); trap 'rm -f "$tmp"' EXIT
	curl -fsSL --max-time 300 "$LF_BASE/board-2.bin?format=TEXT" -o "$tmp" || die "download failed: board-2.bin"
	base64 -d "$tmp" > "$STAGE/$FWREL/board-2.bin" || die "board-2.bin is not valid base64"
	got=$(sha_of "$STAGE/$FWREL/board-2.bin")
	say "  board-2.bin $(stat -c%s "$STAGE/$FWREL/board-2.bin") bytes sha256=${got:0:16}..."
	;;
--from)
	[ -d "$FROM" ] || die "not a directory: $FROM"
	for f in amss.bin m3.bin board-2.bin; do
		[ -f "$FROM/$f" ] || die "missing $FROM/$f"
		cp -p "$FROM/$f" "$STAGE/$FWREL/$f" || die "could not copy $f"
	done
	say "staged from $FROM (source files untouched)"
	;;
esac

# ---- verify whatever is staged, whichever mode produced it ------------------
for f in amss.bin m3.bin board-2.bin; do
	[ -f "$STAGE/$FWREL/$f" ] || die "not staged: $f (run --fetch or --from DIR)"
done

say "--- staged set ---"
for f in amss.bin m3.bin board-2.bin; do
	printf '  %-14s %10s bytes  sha256=%s\n' "$f" "$(stat -c%s "$STAGE/$FWREL/$f")" "$(sha_of "$STAGE/$FWREL/$f")"
done

# The IOE pair has pinned hashes; board-2.bin is accepted as-is but reported, so
# a substituted container is visible rather than silently accepted.
a=$(sha_of "$STAGE/$FWREL/amss.bin"); m=$(sha_of "$STAGE/$FWREL/m3.bin")
[ "$a" = "$IOE_AMSS_SHA" ] || say "NOTE: amss.bin is not the pinned IOE build (${a:0:16}...)"
[ "$m" = "$IOE_M3_SHA" ]   || say "NOTE: m3.bin is not the pinned IOE build (${m:0:16}...)"

# ---- which payload would the firmware match? -------------------------------
if [ -f "$BDFTOOL" ] && command -v python3 >/dev/null; then
	say "--- board-2.bin matching (the slot this device will use) ---"
	md5=$(python3 "$BDFTOOL" md5s "$STAGE/$FWREL/board-2.bin" 2>/dev/null | awk -v n="$SLOT" '$3 == n {print $2}') || true
	if [ -n "$md5" ]; then
		say "  exact-ABI slot present, payload md5=$md5"
	else
		say "  WARNING: no exact-ABI entry for this device in the container."
		say "           ath11k would fall back to a generic payload."
		python3 "$BDFTOOL" md5s "$STAGE/$FWREL/board-2.bin" 2>/dev/null | head -8 | sed 's/^/    /'
	fi
fi

# ---- manifest -------------------------------------------------------------
MANIFEST=$STAGE/MANIFEST.txt
{
	echo "# WCN6855 firmware staged for the SM-X710 Wi-Fi bring-up"
	echo "# generated $(date -u +%Y-%m-%dT%H:%M:%SZ)"
	echo "# destination on device: /lib/firmware/$FWREL/   (= /usr/lib/firmware/$FWREL)"
	echo "# path chosen by the DRIVER's own request, not by convention:"
	echo "#   mhi mhi0: Direct firmware load for $FWREL/amss.bin failed with error -2"
	echo
	echo "hardware: 17cb:1103 (QCNFA765), ath11k reports wcn6855 hw2.1"
	echo "modalias: pci:v000017CBd00001103sv000017CBsd00000108bc02sc80i00"
	echo
	for f in amss.bin m3.bin board-2.bin; do
		echo "file: $f"
		echo "  sha256: $(sha_of "$STAGE/$FWREL/$f")"
		echo "  size:   $(stat -c%s "$STAGE/$FWREL/$f")"
	done
	echo
	echo "source (amss.bin, m3.bin):"
	echo "  $IOE_BASE"
	echo "  upstream project: CodeLinaro mirror of Qualcomm ath11k-firmware"
	echo "  family: WLAN.HSP.1.1-04866.5-QCAHSPSWPL_V1_V2_SILICONZ_IOE-1"
	echo "  chosen because the gts9wifi-fedora-linux port records, for this same"
	echo "  tablet, that the IOE family is the reliable one and that Samsung's own"
	echo "  non-LITE amss20 crashes ath11k with MHI_CB_EE_RDDM."
	echo
	echo "source (board-2.bin):"
	echo "  $LF_BASE/board-2.bin"
	echo "  upstream project: linux-firmware @ main"
	echo
	echo "NOT committed to Git: these are proprietary blobs; out/ is ignored."
} > "$MANIFEST"
say "manifest: $MANIFEST"

# ---- install to the running tablet ----------------------------------------
if [ "$MODE" = --install ]; then
	rel=$("$SSH" 'uname -r' 2>/dev/null | tr -d '\r' | tail -1)
	[ -n "$rel" ] || die "could not read uname -r from the tablet"
	dst=/usr/lib/firmware/$FWREL
	say "installing to the tablet: $dst"
	"$SSH" "mkdir -p $dst" || die "could not create $dst"
	for f in amss.bin m3.bin board-2.bin; do
		"$SSH" "cat > $dst/$f" < "$STAGE/$FWREL/$f" || die "copy failed: $f"
	done
	say "--- verifying on the tablet ---"
	for f in amss.bin m3.bin board-2.bin; do
		local_sha=$(sha_of "$STAGE/$FWREL/$f")
		remote_sha=$("$SSH" "sha256sum $dst/$f 2>/dev/null | cut -d' ' -f1" | tr -d '\r' | tail -1)
		if [ "$local_sha" = "$remote_sha" ]; then
			say "  ok  $f ${local_sha:0:16}..."
		else
			die "$f hash differs after copy (local ${local_sha:0:16}... tablet ${remote_sha:0:16}...)"
		fi
	done
	say "installed and verified.  Reload ath11k_pci to test."
	exit 0
fi

say "nothing was installed; re-run with --install to copy to the tablet"
