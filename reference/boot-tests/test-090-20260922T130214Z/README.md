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

## Result: not measured — the bench link dropped

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
