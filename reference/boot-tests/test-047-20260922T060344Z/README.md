# Test 047 — bootloader version and GO accepted; application still silent

Owner request: `刷入测试`, continuing the keyboard test after test 046.
Source: `1d8a977` on `test`; candidate `out/boot-bundle-pogo-step3/`.
Only boot was written, with full-partition read-back verification. init_boot,
vendor_boot and dtbo already matched the candidate. vbmeta remains stock.
Current and original stock backups passed verification before flashing.

## Result

The candidate boots mainline and exposes the USB console and read-only microSD
report. This time the complete version exchange and both GO acknowledgements
succeeded. The reset after the unknown-command probe is therefore a useful
hardware-validated correction to bootloader communication. It does not establish
that the application ran or that the keyboard works.

`console-startup.log` contains:

```
[    4.299989] MCU bootloader took the 0xFF sync
[    4.312137] MCU bootloader version 0x12
[    4.325562] MCU bootloader accepted GO 0x08000000, application should be running
[    4.497567] application after GO: -6 (not running)
[    4.685084] application after the reset entry: -6 (still not running)
[    7.796288] no answer from the MCU after 40 resets (-6)
[    7.829153] i2c-5 answers at: (nothing)
```

The GO log's phrase "application should be running" is the driver's expectation,
not an observation. The subsequent application request NAKed. The test sampled
it 150 ms after GO and then reset it; it does not exclude a slower application
startup if the MCU were left undisturbed for longer. It also does not inspect the
installed application's vector table or establish the correct jump target.

The event IRQ on gpio75 was still zero at the later 06:06:31 UTC capture.
The owner confirmed `一直连接并展开`: the keyboard remained attached and unfolded.
The pretest TWRP dmesg identifies `EF-DX710_v1.4.1.0`, MCU firmware 34,
`con:1/1`, `rst:0`, and model 0x2 before this boot. The app thus worked in the
stock environment before the test. No successful mainline key input was observed.

The panel log recovered ID `80 00 04` at 7.387 seconds, on the retry path.
The owner's visual screen confirmation applies to test 046; test 047 has no
separate visual observation. The early microSD report was copied and verified
against its sidecar hash; later console logs contain the complete startup result.

## Final state and evidence

At 06:06:42 UTC the live console accepted gts9-to-recovery and reported its BCB
write. The tablet returned to TWRP. All four candidate boot-chain hashes matched
again after recovery, and vbmeta matched the original stock backup. The corrected
candidate remains installed; no stock restoration was performed.

Raw pre/post recovery dmesg, last_kmsg and the empty pstore listing are retained,
labelled separately from the live mainline log. Do not use recovery/ABL logs as
proof of mainline execution. Windows PowerShell emitted repeated closed-port
exceptions just after the requested reboot; its full process output is retained
in console-return-process.log. Those exceptions are host capture errors, not a
kernel crash. Serial output up to the reboot is in console-final.log.

The next investigation is application startup after an acknowledged GO: first
allow bounded polling without reset, then consider read-only identification or
vector-table inspection if still needed. Firmware erasure/writes are not part of
this test or an implied next step.

After recovery, posttest-stock-keyboard.txt again shows EF-DX710_v1.4.1.0,
firmware 34, con:1/1 and rst:0. Stock recognition survived both tests.
