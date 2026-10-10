# Complete Fedora X710 ADSP comparison profile — offline, not deployed

The Fedora origin HEAD was freshly checked and remains
ab123e7d1dbc0cbcd35661f9761197e977b15aa9. Its release asset
[firmware-samsung-gts9wifi-v2.tar.gz](https://github.com/nacht20-de/gts9wifi-fedora-linux/releases/tag/kernel-7.2.0-rc3-gts9wifi-2)
was downloaded as a byte source:24,607,076bytes, SHA256
30cace40556fdaf1577c76bedc1b1a6236f4acc23e9300253b3834fa7ed4bab5,
matching the GitHub asset digest. ASSET.json preserves its provenance.
No release script, Android executable or firmware code was executed.

Both current and Fedora archives provide the same52 ADSP/ADSP-DTB filenames,
but19 differ, including the sensor executable segment18 and the paired MDTs.
ADSP_COMPARISON.json records every file. The shared ADSP build-path string
does not establish identical executable bytes. This is a real input difference
from the otherwise already-adopted Fedora software/config/DT implementation;
it is not proof that firmware version explains missing SSC.

`userspace/sensors/fedora_adsp_profile.py` prepares the complete52-file pair
from the one pinned Fedora release, including its byte-identical segments.
It preserves all276 other accepted asset members byte/mode/mtime exact:
factory calibration, registry cache/config, DSP libraries and PD maps. It
does not import Fedora Wi-Fi, Bluetooth, CDSP, audio topology or other blobs.
No partial MDT/segment mixing, modified signature metadata or real persist access.

Existing Linux7.2 MDT validation verifies split-segment completeness, metadata
and sizes. Both images remain within the exact existing X710 reserved regions:
ADSP0x9ea00000/0x59b4000, ADSP-DTB0x9e980000/0x80000. This is structural
validation; PAS authentication, runtime compatibility and actual sensor samples
remain untested. The first two new host gates wrongly assumed root ownership
for the downloaded source and a Hexagon machine tag for the opaque DTB envelope.
Their failures/corrections are retained in INITIAL_GATE_FAILURES.json; no output
or device modification preceded them. The source owner is explicitly1000/1000;
the generated archive is0/0. ADSP machine164 and ADSP-DTB envelope1 match both
qualified inputs and are separately checked. Other identity/safety gates remain.

Generated private asset archive:
`out/ssc-fedora-adsp-profile/sensor-assets.tar.gz`, SHA256
d647dcdf5ecc010080dbd057cec2c9cc66368d9e241cc3883a532e3f648177b3.
All328 root-owned regular output members were independently reopened and
compared. Deterministic gzip header; original source bytes remain unchanged.
PROFILE.json binds full file hashes/modes/mtimes, both MDT reports and the
remaining deployment requirements. Firmware binaries stay out of Git.

33 affected host tests PASS0skip:16 new profile tests and17 unchanged MDT/stock
asset tests. Coverage includes exact real52/19/276 composition, missing/extra
or short segments, machine/carveout drift, unrelated blob exclusion, unsafe
path/duplicate/link/ownership/hash rejection, reopened output ownership,
deterministic regeneration and refusal to overwrite an existing output.
Syntax checks passed. No kernel build/full regression/routing change/Actions.

This profile is **NOT DEPLOYMENT READY**. Next prepare a separately numbered
one-boot comparison with an early ramdisk containing this exact52-file pair and
a qualified recovery-only firmware transaction. The current assets installer
correctly refuses differing existing firmware: do not bypass that guard. A new
transaction must first hash/freeze exact originals, journal partial-copy intent,
verify both write and restore boundaries, and always restore exact370/current
firmware and normal GNOME. Keep current device calibration and the existing
daemon/library/start order/30s window/provider evidence. No PAS bypass, guessed
sleepstate update, repeated unchanged399 startup or live ADSP restart.

Device operations:none. Kernel/config/DT/modules/USB/charging/input unchanged;
PPS/pump/DCC OFF,4.44V float/thermal safety unchanged. No Test400 registration
or deployment yet; retention stays390–399. This is concrete preparation toward
the requested Fedora reuse, not sensor acceptance or automatic rotation PASS.
