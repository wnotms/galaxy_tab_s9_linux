# test-090 — the owner's event-startup candidate: flashed and verified, result pending console

- test window: 2026-09-22T13:02–13:12Z (pretest evidence collected by the owner's
  session at 13:02Z; flash performed here at 13:12Z)
- source commit: **`0f0b759`** ("input: service pogo announcements without blocking
  startup diagnostics"), the owner's own candidate
- authorization: `source.txt` — `刷入测试`, then `继续修复` and
  `修复键盘驱动，可以参考s9u的对应驱动或搜索其它开源仓库的实现`
- images: `boot.img a6fce2f9…` and `vendor_boot.img b5f3cda0…`, both written to
  their partitions and read back byte-for-byte before the boot
  (`flashed-image-sha256.txt`, `flash-transcript.txt`)

## Why this candidate matters

`docs/POGO_EVENT_STARTUP.md` and the commit record the defect this fixes: the
diagnostic `pogo_connect_work()` held `p->lock` across a 30 s observation window,
a rail cycle and up to 60 s of version polling, while `pogo_irq()` needs the same
mutex — so for the whole time the keyboard's application was asking for attention
the handler could not have served it. The new normal startup enables the rail,
settles 50 ms, arms DATA and drops the lock, makes the model handshake a single
version attempt, and keeps every intrusive experiment (the no-action window, bus
scan, rail cycle, NRET/bootloader visits) behind
`keyboard_samsung_pogo.startup_diagnostics=1`.

That defect is visible in test 087's log: the announce interrupt was delivered
**once** in a whole boot and the handler never put a byte on the bus.

## What was done

```
bash -n scripts/*.sh                                   -> ok
python3 -m unittest discover -s tests                  -> Ran 10 tests, OK
scripts/build-kernel.sh (0f0b759, out/boot-bundle-pogo-event)
adb push boot.img /tmp/boot.img;        dd -> /dev/block/by-name/boot
adb push vendor_boot.img /tmp/vendor_boot.img; dd -> /dev/block/by-name/vendor_boot
boot-readback a6fce2f9… == expected;    vb-readback b5f3cda0… == expected
dd if=/dev/zero of=/dev/block/by-name/misc bs=2048 count=1 conv=notrunc  (BCB cleared)
adb shell reboot system
```

`init_boot` and `dtbo` were left as they were (they already match the candidate);
`recovery` and `vbmeta` were not touched, and no backup, userdata, persist, efs or
partition-table write was made. Raw transcript: `flash-transcript.txt`.

## Result: measured — the interrupt never fires, so the driver never asks

The console came back and the running kernel answered. The candidate boots and
registers its input device, and the non-blocking startup works exactly as written:

```
[    4.098609] input: Book Cover Keyboard Slim (EF-DX710) as .../i2c-5/5-002a/input/input0
[    4.190272] samsung-pogo-keyboard 5-002a: keyboard powered; DATA IRQ armed, waiting for model packet
 170:          0  ...  msmgpio     75 Level     5-002a     <- announcements delivered: 0
 171:       2431  ...  msmgpio     62 Edge      pogo-connect
 188:          0  ...  msmgpio    107 Edge      Book Cover
dmesg | grep -c "event transfer failed"  ->  0
```

So over the whole ~2.5 minutes of uptime measured here: the DATA interrupt was
armed at 4.19 s and was **delivered zero times**, and because the new normal path
reads only in response to a packet, **no read of 0x2a was ever attempted**. Nothing
in this boot contradicts or confirms anything about the slave: the application was
never asked.

This is the mirror image of test 087, where the same interrupt was armed inside the
diagnostic path and delivered exactly once. Neither boot ever got the driver and the
announcement into the same room: in 087 the handler could not run because the
startup work held the mutex, and here it can run but the line stays quiet.

**Standing hypothesis, not yet a finding:** the application drives that line in a
train of transitions only in the first ~25 s after the MCU starts (tests 087 and
088 both measured the train), and the MCU is powered independently of gpio10 (test
082) and is not power-cycled by a Linux reboot - so a boot that misses the train
waits forever for an announcement that will not come again. In tests 087/088 the
train was visible because the diagnostic path armed nothing and merely watched; the
new normal path arms DATA at 4.19 s, which is earlier than the train's first
transition in either of those boots, so "armed too late" does not explain this boot
by itself. What is missing is any host transaction at all while the line is
asserted.

## Candidates this implies (one per test, cheapest first)

1. **Ask anyway after a short timeout.** Arm DATA as now, and if no packet arrives
   within ~1-2 s, make one version read of 0x2a regardless. It is a single safe read
   and it is the only way to learn whether the application's slave is listening when
   nothing has announced itself. This is also what makes the driver independent of a
   one-shot announcement.
2. **Reproduce stock's real power cycle before asking.** Stock's captured bring-up
   powers the accessory off, waits ~400 ms and brings it back with BOOT0 low *before*
   the application answers, and test 087 found the port's own rail disable had been a
   no-op ("unbalanced disables for pogo-vdd") - so the sequence stock actually relies
   on has never run here. The corrected cycle exists in
   `pogo_diagnostic_connect_work()`; test 088 measured it dropping the rail for real
   (`rail off: regulator off`), and only the diagnostic switch keeps it out of the
   normal path.
3. **Confirm the application is running at all**, by reading its line's *logical*
   level with the active-low descriptor over a few seconds (the pin-state dump prints
   register values and cannot answer this).

## Original expectation, for the record: not measured - the bench link dropped

The flash is verified; the boot outcome is **not**. 95 s after `reboot system` the
console capture was attempted and produced nothing, and the host then reported:

```
powershell [System.IO.Ports.SerialPort]::GetPortNames()  -> (empty)
adb devices                                              -> (empty)
```

No serial adapter is present on the host any more, so the tablet's console cannot be
read, and mainline's initramfs has no adbd, so adb is absent by construction. The
owner's own armed capture (`capture-armed.txt`, `host-capture-process.log`, 0 bytes)
hit the same wall. **No claim is made here about whether the announcement was
serviced, whether the model packet arrived, or whether 0x2a answered.**

## To finish this test, with the console back

Boot to recovery (`gts9-to-recovery` over the console), then read the ring buffer
that is still live in the running mainline kernel if it has not been rebooted, or
re-flash and capture from the start:

```sh
dmesg | grep -a "5-002a"            # model packet, version attempt, IRQ servicing
dmesg | grep -a -c "event transfer failed"
cat /proc/interrupts | grep -a "5-002a"   # DATA deliveries, now that the lock is free
```
