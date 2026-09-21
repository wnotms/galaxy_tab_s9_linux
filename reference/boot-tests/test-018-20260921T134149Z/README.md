# Test 018 — exfat-aware report writer, and the RTC state channel (2026-09-21T13:41:51Z)

Two changes against test 017: the report writer now mounts exfat (the owner's card
is exfat, so the previous mount list could never have taken the report) and writes a
`.sha256` sidecar next to it, and `/init` writes a 16-bit bring-up state word into the
PMK8550 RTC as the date 2031-01-01 + code, so the storage/USB state can be read back
from recovery without anyone timing a power-off (`docs/RTC_REPORT.md`).

Artifacts: `boot 457f276e…` (unchanged), `init_boot 77779f24…` (new, RTC channel),
`vendor_boot 8bc0ad1b…` (cmdline gained `gts9_rtc_report=1`), both flashed and read
back; `dtbo`/`vbmeta` untouched.  Validator passed.

## Result: nothing enumerated, and the RTC word was not written

`observation.txt` has the details.  In short:

- no report anywhere: not the raw block in `cache`, not the file in a mounted
  `cache`, and nothing on the microSD;
- the RTC still holds the real time, so the state word never landed - which the
  delay telemetry of test 019 was then extended to explain;
- **the card and the slot are fine**: recovery mounts `/dev/block/mmcblk1p1` at
  `/external_sd` as exfat, and `/proc/partitions` there lists the complete UFS LUN0
  table.  Both are stock-kernel facts, and they say the hardware is not the problem.

No gadget appeared either (the monitor that was already running logged nothing for
this boot window).
