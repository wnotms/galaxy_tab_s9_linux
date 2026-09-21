# Test 030 — both directions of the USB serial link, measured (2026-09-21T15:21:22Z)

The owner asked for the serial console fixed, so this run measures the link
instead of theorising about it.  The gadget runs as **CDC-ACM and mass storage
together** (`gts9_usb_gadget=both`), the console runs in the new `marker` mode
(four known lines written once, no shell), everything the host sends is recorded
to `/tmp/gts9-serial-in.txt` and copied next to the report on the card, and
`gts9_usb_wait=60` holds the boot for a minute so the host gets a window before
the report is collected.

Artifacts: `boot ba948a93…` (unchanged), `init_boot c52fcb36…`,
`vendor_boot 03933e33…` with `cmdline.txt`.

## Result: the link carries data in both directions

From `serial-test.log` (host side):

```
15:23:27 port open
15:24:26 READ  GTS9-SERIAL-MARKER ready
15:24:26 WRITE ok after 1 ms: PING-GTS9-030
15:24:26 READ  GTS9-SERIAL-MARKER uname=7.2.0-rc3-gts9wifi-dirty
15:24:26 READ  GTS9-SERIAL-MARKER uptime=65.67
15:24:26 READ  GTS9-SERIAL-MARKER end
15:24:26 READ  PING-GTS9-030
```

The device's markers arrive, the host's write completes in a millisecond, and the
tty echoes it back.  The card was collected over the USB mass-storage export in
the same boot (`bringup-report.txt`, 162931 bytes, sha256 `5073139a…`).

## Why "sending data hangs" was the wrong conclusion

The link was never the problem: a host write only completes while something on
the device side is `read()`ing `/dev/ttyGS0`, and in tests 021-027 nobody was:
`/init` never reached the console block at all (the RTC write blocked it), and
even in the console block the retry loop left five-second gaps with no reader.
The host's writes therefore NAKed until the USB stack gave up, which is what the
owner saw as "it hangs and the signal-light timeout expires".

So `/init` now hands the port straight to an interactive shell and nothing else
reads it, the kernel-log flood that used to fill the tty buffer is off by default
(`shell+kmsg` brings it back), and the shell prints how to get back to TWRP.

`gts9-serial-in.txt` never reached the card because the host's write landed six
seconds after the copy - a timing artefact of this run, not a link failure; the
echo above is the device->host proof and the write's completion is the
host->device proof.
