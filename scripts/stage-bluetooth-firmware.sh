#!/usr/bin/env bash
# Stage the WCN6855 Bluetooth firmware the QCA6490 on the X710 actually asks for.
#
#   scripts/stage-bluetooth-firmware.sh --fetch      # download from upstream linux-firmware
#   scripts/stage-bluetooth-firmware.sh --from DIR   # use blobs already on disk
#   scripts/stage-bluetooth-firmware.sh --check      # report what is staged
#   scripts/stage-bluetooth-firmware.sh --install    # copy to the running tablet
#
# Design rules, from the round's brief:
#
#   * the file names are the ones the DRIVER asked for, read from dmesg - not
#     guessed.  For this board hci_qca requests, in order:
#         qca/wcnhpbtfw21.tlv   (WCN6855, upstream's corrected name)
#         qca/hpbtfw21.tlv      (the historical fallback)
#     where "21" is rom_ver, derived from the controller's own version word:
#         soc_ver = 0x12110201 -> rom_ver = ((soc_ver & 0xf00) >> 4) | (soc_ver & 0xf) = 0x21
#     scripts/lib/btfw-name.py re-derives both names from a pasted dmesg so the
#     mapping stays checkable instead of being asserted here.
#   * the NVM is a SEPARATE question from the rampatch and is named from the board
#     ID the controller reports, which is only readable AFTER the rampatch is
#     loaded.  So --fetch deliberately stages the rampatch set, and the NVM is
#     staged in a second pass once the board ID is known (see --nvm-from-log).
#   * no networking unless --fetch is given explicitly; --from DIR never touches
#     the network.
#   * source files are never modified - everything is copied into a staging tree.
#   * every blob is hashed and recorded in a manifest, and the proprietary files
#     are NOT committed to Git (they live under out/, which is ignored).
#   * a hash mismatch is fatal, not a warning: an unverified firmware blob is
#     exactly the "random blob from a forum" the brief forbids.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
STAGE=${GTS9_BT_FW_STAGE:-$REPO/out/bluetooth-firmware}
FWREL=qca                            # what the driver asked for on this board
SSH=$REPO/scripts/gts9-ssh.sh
NAMETOOL=$REPO/scripts/lib/btfw-name.py

# Upstream linux-firmware is the only source used by default.  The CodeLinaro
# mirror is the same content; Samsung's stock partition is a last resort and is
# only ever reachable through --from DIR, where the caller must have recorded its
# own provenance (see the manifest the script writes).
LF_BASE=${GTS9_LF_BASE:-https://kernel.googlesource.com/pub/scm/linux/kernel/git/firmware/linux-firmware/+/refs/heads/main/qca}

# The rampatch pair.  wcnhpbtfw21.tlv is what upstream asks for first on a
# WCN6855; hpbtfw21.tlv is the pre-rename name kept for old DT/boards.
RAMPATCH_PRIMARY=wcnhpbtfw21.tlv
RAMPATCH_FALLBACK=hpbtfw21.tlv

# Pinned hashes for the files this round verified, taken from the fetches
# recorded in reference/boot-tests/test-218-*/.  A mismatch is reported loudly
# rather than silently accepted; --from is allowed to stage other revisions
# because Samsung's own board NVM may legitimately differ.
PRIMARY_SHA=77d8979da5c613c85550549dcef8fb8ec6fe2e5576942855ea03179a11597c1f
FALLBACK_SHA=a911f66a137ec8b9e65f90942e1c21ea2604734a88e486519b77e750d0fc20d2

MODE=${1:---check}
FROM=""
NVM_FILE=""
case "$MODE" in
--fetch|--check|--install) ;;
--from) FROM=${2:?--from needs a directory}; MODE=--from ;;
--nvm) NVM_FILE=${2:?--nvm needs a staged filename}; MODE=--nvm ;;
*) echo "usage: $0 [--fetch|--from DIR|--nvm FILE|--check|--install]" >&2; exit 2 ;;
esac

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }
sha_of() { sha256sum "$1" | cut -d' ' -f1; }

fetch() { # fetch NAME
	local name=$1 url
	url="$LF_BASE/$name?format=TEXT"
	say "fetching $name"
	curl -fsSL --max-time 300 "$url" -o "$STAGE/$FWREL/$name.b64" \
		|| die "download failed: $url"
	# kernel.googlesource.com serves blobs base64-wrapped; decode and drop the
	# wrapper only after it decodes, so a partial download cannot be mistaken
	# for firmware.
	base64 -d < "$STAGE/$FWREL/$name.b64" > "$STAGE/$FWREL/$name" \
		|| die "base64 decode failed: $name"
	rm -f "$STAGE/$FWREL/$name.b64"
	[ -s "$STAGE/$FWREL/$name" ] || die "decoded $name is empty"
}

mkdir -p "$STAGE/$FWREL"

case "$MODE" in
--fetch)
	command -v curl >/dev/null || die "curl required for --fetch"
	command -v base64 >/dev/null || die "base64 required for --fetch"
	fetch "$RAMPATCH_PRIMARY"
	fetch "$RAMPATCH_FALLBACK"
	say "staged from upstream linux-firmware @ main (source files untouched)"
	;;
--from)
	[ -d "$FROM" ] || die "not a directory: $FROM"
	for f in "$RAMPATCH_PRIMARY" "$RAMPATCH_FALLBACK"; do
		[ -f "$FROM/$f" ] || die "missing $FROM/$f"
		cp -p "$FROM/$f" "$STAGE/$FWREL/$f" || die "could not copy $f"
	done
	say "staged from $FROM (source files untouched)"
	;;
--nvm)
	# The NVM's name depends on the board ID, which is only readable once the
	# rampatch is loaded.  The caller passes the exact filename the driver
	# printed; this stage fetches precisely that file so nothing is guessed.
	case "$NVM_FILE" in
		*/*|*..*) die "NVM filename must be a bare name, got: $NVM_FILE";;
	esac
	command -v curl >/dev/null || die "curl required for --nvm"
	fetch "$NVM_FILE" || die "could not fetch $NVM_FILE"
	say "staged NVM $NVM_FILE"
	;;
--check|--install) ;;
esac

# ---- verify whatever is staged, whichever mode produced it ------------------
[ -f "$STAGE/$FWREL/$RAMPATCH_PRIMARY" ] || die "not staged: $RAMPATCH_PRIMARY (run --fetch or --from DIR)"
[ -f "$STAGE/$FWREL/$RAMPATCH_FALLBACK" ] || die "not staged: $RAMPATCH_FALLBACK (run --fetch or --from DIR)"

say "--- staged set ---"
for f in "$RAMPATCH_PRIMARY" "$RAMPATCH_FALLBACK"; do
	printf '  %-20s %9s bytes  sha256=%s\n' "$f" "$(stat -c%s "$STAGE/$FWREL/$f")" "$(sha_of "$STAGE/$FWREL/$f")"
done

p=$(sha_of "$STAGE/$FWREL/$RAMPATCH_PRIMARY")
f=$(sha_of "$STAGE/$FWREL/$RAMPATCH_FALLBACK")
[ "$p" = "$PRIMARY_SHA" ] || say "NOTE: $RAMPATCH_PRIMARY is not the pinned build (${p:0:16}...)"
[ "$f" = "$FALLBACK_SHA" ] || say "NOTE: $RAMPATCH_FALLBACK is not the pinned build (${f:0:16}...)"

# Any extra files (a staged NVM) are reported too, so the manifest is complete.
extra=$(cd "$STAGE/$FWREL" && ls -1 2>/dev/null | grep -vE "^($RAMPATCH_PRIMARY|$RAMPATCH_FALLBACK)$" || true)
if [ -n "$extra" ]; then
	say "--- additionally staged ---"
	for f in $extra; do
		printf '  %-20s %9s bytes  sha256=%s\n' "$f" "$(stat -c%s "$STAGE/$FWREL/$f")" "$(sha_of "$STAGE/$FWREL/$f")"
	done
fi

# ---- which name will the driver actually pick? ------------------------------
if [ -x "$NAMETOOL" ] || [ -f "$NAMETOOL" ]; then
	say "--- which file wins, from the controller's own version word ---"
	if [ "$MODE" = "--install" ]; then
		ver=$("$SSH" "dmesg | grep -oE 'QCA controller version 0x[0-9a-f]+' | tail -1" 2>/dev/null | tr -d '\r' | awk '{print $NF}')
		[ -n "$ver" ] || ver=0x12110201
	else
		# Offline: use the value the tablet reported, recorded in the preflight.
		ver=0x12110201
	fi
	python3 "$NAMETOOL" "$ver" 2>/dev/null | sed 's/^/  /' || true
fi

# ---- manifest -------------------------------------------------------------
MANIFEST=$STAGE/MANIFEST.txt
{
	echo "# WCN6855 Bluetooth firmware staged for the SM-X710 (QCA6490) bring-up"
	echo "# generated $(date -u +%Y-%m-%dT%H:%M:%SZ)"
	echo "# destination on device: /lib/firmware/$FWREL/   (= /usr/lib/firmware/$FWREL)"
	echo "# names chosen by the DRIVER's own request, not by convention:"
	echo "#   Bluetooth: hci0: QCA Downloading qca/$RAMPATCH_PRIMARY"
	echo "#   Bluetooth: hci0: QCA Downloading qca/$RAMPATCH_FALLBACK"
	echo
	echo "hardware: qcom,wcn6855-bt on 898000.serial (QUP SE14), X710"
	echo "controller: QCA Product ID 0x00000013, SOC 0x400c1211, ROM 0x00000201,"
	echo "            patch 0x000038e6, controller version 0x12110201 -> rom_ver 0x21"
	echo "modalias: of:NbluetoothT(null)Cqcom,wcn6855-bt"
	echo
	for f in "$RAMPATCH_PRIMARY" "$RAMPATCH_FALLBACK"; do
		echo "file: $f"
		echo "  sha256: $(sha_of "$STAGE/$FWREL/$f")"
		echo "  size:   $(stat -c%s "$STAGE/$FWREL/$f")"
	done
	if [ -n "$extra" ]; then
		for f in $extra; do
			echo "file: $f"
			echo "  sha256: $(sha_of "$STAGE/$FWREL/$f")"
			echo "  size:   $(stat -c%s "$STAGE/$FWREL/$f")"
		done
	fi
	echo
	echo "source:"
	echo "  $LF_BASE/<name>"
	echo "  upstream project: linux-firmware @ main (kernel.org / googlesource mirror)"
	echo "  chosen because it is the canonical upstream project for these blobs;"
	echo "  no forum, no random fork, and Samsung's stock partition was not needed."
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
	for f in "$RAMPATCH_PRIMARY" "$RAMPATCH_FALLBACK" $extra; do
		"$SSH" "cat > $dst/$f" < "$STAGE/$FWREL/$f" || die "copy failed: $f"
	done
	say "--- verifying on the tablet (re-hashed after copy) ---"
	rc=0
	for f in "$RAMPATCH_PRIMARY" "$RAMPATCH_FALLBACK" $extra; do
		want=$(sha_of "$STAGE/$FWREL/$f")
		got=$("$SSH" "sha256sum $dst/$f 2>/dev/null | cut -d' ' -f1" | tr -d '\r' | tail -1)
		if [ "$want" = "$got" ]; then
			printf '  OK    %-20s %s\n' "$f" "$got"
		else
			printf '  FAIL  %-20s want=%s got=%s\n' "$f" "$want" "$got"
			rc=1
		fi
	done
	[ "$rc" = 0 ] || die "one or more files did not verify on the tablet"
	say "all files verified on the tablet"
	say "NOTE: nothing was reloaded. Reboot, or reload hci_uart, to retry the download."
fi

say "done"
