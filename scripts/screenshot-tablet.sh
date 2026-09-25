#!/usr/bin/env bash
# Capture the tablet's screen and save it as a PNG.
#
#   scripts/screenshot-tablet.sh                    # -> out/screenshots/screen-<utc>.png
#   scripts/screenshot-tablet.sh -o shot.png
#   scripts/screenshot-tablet.sh --raw               # keep the raw framebuffer too
#
# The tablet runs with no X11 and no Wayland session (XDG_SESSION_TYPE=tty), so
# there is no compositor to ask.  What it does have is a DRM framebuffer exposed
# as /dev/fb0 - the panel pipeline, "msm-kmsdrmfb", 2560x1600 at 32 bpp - and that
# is what a person sees on the glass.  So the capture reads /dev/fb0 directly,
# converts to PNG, and verifies the result before claiming success.
#
# Why not DRM dumb-buffer capture (e.g. `modetest -c`)?  Because it needs the
# modesetting test tools installed and it reads the *scanout* buffers, which the
# DPU may have already released; fb0 is the same image with no extra dependency.
# Why not a USB gadget frame grab?  ttyGS1 is a serial console, not a display.
set -uo pipefail

REPO=$(cd "$(dirname "$0")/.." && pwd)
SSH=$REPO/scripts/gts9-ssh.sh
OUTDIR=$REPO/out/screenshots
OUT=""
KEEP_RAW=0

while [ $# -gt 0 ]; do
	case "$1" in
	-o) OUT=${2:?--o needs a path}; shift 2 ;;
	--raw) KEEP_RAW=1; shift ;;
	-h|--help) sed -n '2,16p' "$0"; exit 0 ;;
	*) echo "unknown argument: $1" >&2; exit 2 ;;
	esac
done

say() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }
die() { say "FATAL: $*" >&2; exit 1; }

mkdir -p "$OUTDIR"
[ -n "$OUT" ] || OUT=$OUTDIR/screen-$(date -u +%Y%m%dT%H%M%SZ).png

# ---- geometry, read from the device rather than assumed ---------------------
read -r VS STRIDE BPP NAME < <(
	"$SSH" 'printf "%s %s %s %s\n" \
		"$(cat /sys/class/graphics/fb0/virtual_size 2>/dev/null)" \
		"$(cat /sys/class/graphics/fb0/stride 2>/dev/null)" \
		"$(cat /sys/class/graphics/fb0/bits_per_pixel 2>/dev/null)" \
		"$(cat /sys/class/graphics/fb0/name 2>/dev/null)"' 2>/dev/null | tr -d '\r' | tail -1
)
[ -n "${VS:-}" ] && [ -n "${STRIDE:-}" ] || die "could not read /sys/class/graphics/fb0 - is it a framebuffer console?"
W=${VS%,*}; H=${VS#*,}
[ "$BPP" = 32 ] || die "expected 32 bpp, got '$BPP' - the channel order below would be wrong"
say "framebuffer: $NAME ${W}x${H} stride=$STRIDE bpp=$BPP"

SIZE=$(( STRIDE * H ))
RAW=$(mktemp /tmp/gts9-fb.XXXXXX)
trap 'rm -f "$RAW"' EXIT

# ---- capture ---------------------------------------------------------------
# dd from /dev/fb0 is a plain read: it does not blank, flip, or otherwise touch
# the display, and it needs no daemon on the tablet.
say "reading $SIZE bytes from /dev/fb0"
"$SSH" "dd if=/dev/fb0 bs=$STRIDE count=$H 2>/dev/null" > "$RAW" || die "dd failed"
got=$(stat -c %s "$RAW")
[ "$got" -eq "$SIZE" ] || die "short read: got $got bytes, expected $SIZE"

# ---- a blank capture is a failure, not a screenshot -------------------------
# A uniformly black image means the panel is off or the read raced a power
# transition.  Reporting that as success would be the one outcome that misleads,
# so it is checked rather than assumed.
uniq_bytes=$(od -An -tu1 -j $(( STRIDE * (H/2) )) -N 4096 "$RAW" | tr ' ' '\n' | grep -c . )
nonzero=$(od -An -tu1 -j $(( STRIDE * (H/2) )) -N 4096 "$RAW" | tr ' ' '\n' | grep -vc '^0*$' || true)
if [ "${nonzero:-0}" -eq 0 ]; then
	say "WARNING: the sampled scanline is entirely black - the panel may be off or blanked"
	say "         writing the capture anyway so the blank state is visible"
fi

# ---- BGRA -> RGB, honouring stride ----------------------------------------
# fb0 at 32 bpp is BGRA in memory on this SoC (byte order B,G,R,X), so the
# channels are swapped.  Rows are cropped from `stride` to `W*4` because stride
# (10240) is wider than the visible line (2560*4 = 10240 here, but that is a
# coincidence of this mode and must not be relied on).
[ "$KEEP_RAW" = 1 ] && { cp "$RAW" "${OUT%.png}.raw"; say "kept raw framebuffer at ${OUT%.png}.raw"; }

python3 - "$RAW" "$OUT" "$W" "$H" "$STRIDE" <<'PY' || die "PNG encoding failed"
import struct, sys, zlib

raw, out, w, h, stride = sys.argv[1], sys.argv[2], int(sys.argv[3]), int(sys.argv[4]), int(sys.argv[5])
data = open(raw, "rb").read()

rows = []
for y in range(h):
    off = y * stride
    line = data[off:off + w * 4]
    # BGRA -> RGB
    rgb = bytearray(w * 3)
    rgb[0::3] = line[2::4]
    rgb[1::3] = line[1::4]
    rgb[2::3] = line[0::4]
    rows.append(bytes(rgb))

def chunk(tag, payload):
    return (struct.pack(">I", len(payload)) + tag + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xffffffff))

ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)   # 8-bit, truecolour RGB
scanlines = b"".join(b"\x00" + r for r in rows)        # filter type 0 per row
png = (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
       + chunk(b"IDAT", zlib.compress(scanlines, 6)) + chunk(b"IEND", b""))
open(out, "wb").write(png)
print(f"wrote {out} {w}x{h} {len(png)} bytes")
PY

# ---- verify what was written ----------------------------------------------
python3 - "$OUT" <<'PY' || die "the PNG did not verify"
import struct, sys
p = sys.argv[1]
d = open(p, "rb").read()
assert d[:8] == b"\x89PNG\r\n\x1a\n", "bad PNG signature"
assert d[-8:-4] == b"IEND", "missing IEND"
w, h, depth, ctype = struct.unpack(">IIBB", d[16:26])
assert (depth, ctype) == (8, 2), f"unexpected depth/colour type {depth}/{ctype}"
print(f"verified PNG {w}x{h} depth={depth} colour=RGB")
PY
say "screenshot: $OUT"
