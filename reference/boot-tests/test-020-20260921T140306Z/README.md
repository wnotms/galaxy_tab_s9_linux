# Test 020 — CONFIG_QCOM_PDC alone (2026-09-21T14:03:06Z)

One change: `CONFIG_QCOM_PDC=y`, asserted at build time.  The PDC is the
interrupt controller the SPMI arbiter hangs off (`spmi@c400000
interrupts-extended = <&pdc 1 …>`), and `usb@a600000` takes its dp/dm/ss PHY
interrupts from it as well.  The stock 5.15 seed leaves the driver out, so in
mainline the arbiter should be deferring forever — which would remove the whole
PMIC side of the board with it: the microSD card-detect line is **pm8550 GPIO
12**, and the PMK8550 **RTC** that carries the state word is SPMI too.

That single missing provider is the best explanation so far for all of tests
012-019: no `/dev/mmcblk*` even with the card inserted, no `/dev/rtc0`, no
gadget, and therefore no report anywhere.

The two SM-X910 PHY patches are deliberately **not** in this build
(`kernel/patches/pending/`): test 019 carried them plus this fix and was cut
short by hand, so it could not say whether they helped or hurt.

Artifacts: `boot e47e30b3…` (new kernel), `init_boot b13296a1…` and
`vendor_boot 139e0f5d…` (cmdline `gts9_proof_code=240 gts9_rtc_report=1`, so a
boot lasts 240-315 s instead of ten minutes).  `dtbo`/`vbmeta` untouched;
validator passed.

## What the run has to say

- power-off delay 240 s + 5 s per set bit of
  `1*RTC device + 2*RTC word written + 4*microSD + 8*UFS`:
  **275 s means RTC + card**, 315 s adds UFS;
- the RTC state word itself, read from `/proc/driver/rtc` (the registers, not
  `date`: recovery applies an offset mainline does not know about);
- the report, which should now reach the microSD card as exfat with a `.sha256`
  sidecar, and carries `devices_deferred`, the regulator summary and `dmesg`.

## Result

Pending.
