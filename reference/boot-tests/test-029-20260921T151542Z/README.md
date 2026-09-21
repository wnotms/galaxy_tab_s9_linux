# Test 029 — the microSD card over USB, read-only (2026-09-21T15:15:42Z)

The owner asked for the USB console first.  The decisive experiment is not the
CDC-ACM function but the bulk path itself, so this run switches the gadget to
**mass storage**, backed by the microSD partition and exported **read-only**:

    gts9_usb_gadget=msc        (new command-line option)

`/init` creates the function with no medium, binds the UDC as before, and only
after the report has been written and the card unmounted does it attach
`/dev/mmcblk1p1` to `lun.0`, so the host can mount the volume while this boot is
still running.  The proof is a 900 s safety net with the BCB action and no inline
handover, so the tablet stays up for 16 minutes and then takes itself to TWRP.

Artifacts: `boot ba948a93…` (unchanged), `init_boot 2d3c4dd6…`,
`vendor_boot 16374d27…` with `cmdline.txt` (kept next to this file; the validator
takes `--cmdline`).

## Result: bulk transfers work, and the card is readable while the tablet runs

Windows, on its own, with nobody touching the tablet:

```
2  Linux File-Stor Gadget USB Device   63861073920  USB
G:  2  (no label)                      63861424128  exFAT
```

`G:` is the tablet's microSD card, mounted read-only in Windows.  Copying
`G:\gts9-bringup-report.txt` (157477 bytes) off it and hashing it gives
`f6b62e0b…`, byte for byte what the initramfs wrote in its `.sha256` sidecar, and
the directory listing is the owner's own card contents - so nothing was modified.

That settles the USB question properly:

- the **bulk data path is fine** - the PHY, the PTN3222 redriver and the dwc3
  endpoints all carry a 157 KB file and an exFAT directory read without error;
- the CDC-ACM failure is therefore the **ACM function/descriptor**, not the link:
  the host sees the control interface and never the data interface, which is why
  COM17 opened and then stalled (tests 020, 022);
- and more useful than a console: **the log can be collected over USB while the
  tablet keeps running** - no TWRP, no power button, no owner.

## Notes

- The UDC section of the report says `state: not attached, current_speed:
  UNKNOWN` because it is collected a few seconds in, before the host enumerates;
  the enumeration is visible from the host side instead (`host-disks.log`).
- The card is exported read-only on purpose: it holds the owner's data, and a
  read-only LUN cannot corrupt it.
- A read-write export of a scratch partition (the 600 MB `cache`) would let the
  host push files to the tablet, which is the shortest path to a root filesystem.
