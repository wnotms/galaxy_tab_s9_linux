# test-061 — the application does not announce itself: it is not running

- started: 2026-09-22T08:10:00Z
- source commit: `64de05f` ("pogo: detect a live application passively on the announce line")
- images: `boot.img ad288ada…`; `vendor_boot 8d76f912…`, `init_boot 12b77d17…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-060

## What this separates

Test 060 left two possibilities: the application is not running at all, or it runs
and does not answer this host. The MCU asserts its own announce line (gpio75,
level-low IRQ) when it has something to report — stock's byte log shows the
keyboard announcing itself that way — so the interrupt can detect a live
application without putting anything on the bus. `connect_work` armed it for the
silent window, and the handler only counted.

## Result — no announce, so no application

```
[    4.081249] MCU rail on with BOOT0 low
[    4.103529] leaving the MCU alone for 30000 ms (announce line armed)
[   36.124155] silent window over; connect line 0, 0 announce IRQ(s)
[   36.143789] waiting up to 60000 ms for the MCU application
[   99.612028] no answer from the MCU application after 60000 ms (-6)   (test 060, same path)
```

Zero announce interrupts in thirty seconds of a completely silent bus, and no
answer in the sixty seconds that follow. A level-low line that the application
had asserted would have fired the moment the interrupt was armed, so the
application is **not running** under mainline — this is not a response-path
problem (address, framing, bus rate, side effects, timing and power-on order have
all been measured and excluded, tests 046-060).

## Two corrections to the working assumptions

`geni-driver-truth.txt`, both from the complete buildable tree the owner pointed
at (`/home/ms/Samsung/kernel_platform`):

1. **The two quirks have no consumer anywhere in the tree.** The only files that
   mention `samsung,reset-before-trans` or `samsung,stop-after-trans` are the four
   `gts9wifi_*.dts` files. The stock kernel that runs the keyboard correctly
   therefore ignores them too, so they cannot be what makes the application work —
   and P1/P2 of the plan (replicate Samsung's exact register-level semantics) is
   closed by evidence rather than left open.
2. **Stock does not use mainline's driver on this bus at all.** The stock build
   sets `CONFIG_I2C_MSM_GENI=m`, i.e. Qualcomm's downstream
   `msm-kernel/drivers/i2c/busses/i2c-msm-geni.c` (2993 lines), not
   `i2c-qcom-geni.c` (747 lines) which mainline uses. Every "stock and mainline
   behave the same on this bus" statement so far rested on the DT properties and
   on transfers succeeding, not on the two drivers agreeing.

## Next step

The remaining, now well-defined difference is the controller driver itself: read
`i2c-msm-geni.c`'s transfer path and list what it does per transfer that mainline
does not (resource/clock on-off around a transfer, SE command and cancel
sequencing, SCL counter and packing programming, STOP placement), then reproduce
the minimal subset for this one controller. That is the first candidate that
follows from evidence rather than from a guess about the MCU's state.
