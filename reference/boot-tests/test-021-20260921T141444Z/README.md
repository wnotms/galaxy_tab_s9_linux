# Test 021 — Samsung's eUSB2 init sequence, and it breaks USB here (2026-09-21T14:14:46Z)

Two changes: `/init` writes the RTC state word twice (before the report, so its
outcome lands in the dmesg the report carries, and after persistence), and the
SM-X910 port's eUSB2 PHY patch goes back in - the one that waits after POR and
programs CPBIAS to one.

Artifacts: `boot a2a9a504…` (eUSB2 patch), `init_boot 50725fa1…`,
`vendor_boot 139e0f5d…`; all flashed and read back.

## Result: the kernel never reached userspace, so the eUSB2 patch is wrong here

- No gadget appeared on the host (a 15-minute monitor saw nothing), where test
  020 with the same kernel minus this patch got a host-visible
  `VID_0525&PID_A4A7`.
- The tablet **never powered itself off** and was rebooted into TWRP by hand.
- The card still held test 020's report, byte for byte (`dfbabbe0…`, same size),
  so no new report was written either, and the RTC registers had simply
  advanced with real time.

Conclusion: CPBIAS=1 plus the post-POR delay is right for the X910's PHY
configuration and wrong for this one.  The patch moved to
`kernel/patches/pending/` with that evidence, and the lesson that matters more:
the gadget appearing is itself a reliable, host-side indicator of whether a boot
reached userspace.
