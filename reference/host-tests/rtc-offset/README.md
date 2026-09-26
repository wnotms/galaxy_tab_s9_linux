# Host verification of the RTC offset helper and its /init wiring

Run 2026-09-26T10:24:29Z on Linux x86_64, against the working tree.

No tablet was involved, and no clock was set: the host build never calls
clock_settime (GTS9_HOST_TEST in boot/gts9-rtc-offset.c). What is exercised
is the real helper source and the real shell functions extracted from
boot/minimal-rootfs-init.sh, with mount/umount/timeout stubbed and the device
paths redirected into a temporary tree.

```
$ ./gts9-rtc-offset-host        # real device values: ats_2=1767701103844, raw=22638758
rtc-offset: status=applied source=persist/time/ats_2 offset_ms=1767701103844 raw_ms=22638758000 realtime_epoch=1790339861
exit=0

$ sh flow.sh                   # real /init logic, stubbed mount/umount/timeout
--- calling minimal_apply_rtc_offset ---
rtc-offset: status=applied source=persist/time/ats_2 offset_ms=1767701103844 raw_ms=22638758000 realtime_epoch=1790339861
rtc-offset: helper_rc=0
--- trace ---
MOUNT CALLED: -t ext4 -o ro,noload /tmp/rtcflow/dev/sda5 /tmp/rtcflow/persist-ro
UMOUNT CALLED: /tmp/rtcflow/persist-ro

$ sh flow.sh   # with the persist partition absent (no PARTNAME=persist)
rtc-offset: status=partition-missing label=persist (UFS up after 5s)
```

Expected: `status=applied`, `offset_ms=1767701103844`,
`raw_ms=22638758000`, and `realtime_epoch=1790339861` = 2026-09-25T12:37:41Z,
which matches the capture time of reference/boot-tests/test-198-20260925T1235Z/.
The mount is `-t ext4 -o ro,noload` on the partition whose PARTNAME is
`persist`, unmounted again before switch_root; when the partition is absent
the status says so and the boot continues.
