# Test 235: PMSG ECC passes; CPU failures remain

The diagnostic Image.gz matches the earlier unmodified production rebuild.
Decoded DTB differs only by ecc-size=64; config, reserved region/zone sizes,
mem_type=0 and CPU/power settings are unchanged. Source
`059c1400-1ccf-4861-9590-1fe2592611b7` confirmed runtime ECC=64 and remained
responsive beyond 151 seconds with no failed units or detected CPU stall.
First-boot header errors refer to incompatible older ECC=0 data.

## Known PMSG bytes passed this direct warm reboot

Capture `55366034-ba7d-490e-a130-564f3956bd37` contains 33,005 bytes,
SHA-256 `7322a93f988d377a96d4ea2df30d092cbadbee4304e3538332a605104b35be01`.
After successful device-file hash verification and PMSG write, a direct reboot
reached `bd682a9a-82c5-4955-8f5e-b5777f67b559`, immediately after the source in
retained history. At uptime 6.53 the observer returned a new 33,055-byte PMSG
archive hash `9032410eaa7666d8d0622afa00adee3ba34081607116c330816afeb5544399a4`.
It then lost responsiveness before live file retrieval completed.

TWRP later retrieved that exact same file twice, matching its device-side
hash and the original observer hash. The original observer journal's binary
`FILE` field independently contains identical bytes. The full unique source
payload matches at offset zero; the remaining bytes are:

```
ECC: 246 Corrected bytes, 0 unrecoverable blocks
```

This is one successful PMSG integrity observation under ECC=64, following
corrupt ECC=0 observations in tests 233/234. It does not prove every reset,
crash-triggered capture, every sink or a CPU cure. No wedge series is ready.

## Console probe was invalid; preserve that limitation

The observer also archived a 5,076-byte console with SHA-256
`7fd0a63545d7a7e74672980685e8b5191733c1c895fe5449585c600f68ccd55f`.
Later manual boots replaced the disk console. Its **original bytes** were
recovered from the original observer journal's `FILE` field and match the
previously captured hash. It reports 36 corrected bytes / 0 unrecoverable
blocks, but none of the 16 intended test markers is present.

The host trial mistakenly emitted those markers at level 6 while production
uses loglevel=4. Pinned printk.c filters levels >= console_loglevel before
console sinks; the PStore console has ordinary console flags. The markers
appear in the source journal but were ineligible for this console. Thus their
absence is an **invalid console probe**, not evidence of retention loss or a
console integrity pass. Keep the machine-readable absent-marker result and
this explanation. The next console calibration must use level 0, as the
existing lastactivity pr_emerg instrument does, and verify source eligibility.
Do not repeat the level-6 harness.

## Failure attribution and recovery

The immediate observer's recovered journal ends near 10.22 seconds without a
positive CPU non-response signature. Its failed boot-list/USB/TCP captures stay
unattributed. The owner manually restarted to
`c1027ef1-e680-425b-b6fc-6d7819800639`; that boot also lost responsiveness.
Its recovered disk journal positively identifies **CPU 2 and CPU 5** failing
to answer backtrace IPIs with RCU stalls at about 48.4 seconds. The NMI wording
is an ordinary IPI path with pseudo-NMI disabled. Concurrent non-response does
not establish independent causes or exact failure onset. ECC did not resolve
CPU failures; the absence of diagnostic C code in this candidate is recorded.

A further owner restart reached responsive boot
`74f93f21-eff1-4360-b1a4-88593da4951e`. At uptime 57.61 the normal BCB helper
and systemctl reboot successfully entered TWRP. Disk archives were mounted
read-only with noload. Initial collection of system.journal omitted earlier
unclean files; that failed query is preserved. The relevant **.journal~** files
were then retrieved, hashed and decoded by exact boot ID. Raw journal copies
are losslessly gzip-compressed in recovery-disk; no disk journal was repaired.

Original boot/vendor_boot were restored with complete readbacks and all five
partition hashes match production. Rootfs/USB configuration was unchanged.
Restored production boot `2d1619e1-3130-418c-b5d3-af51b14e9280` has ECC=0,
SSH/adbd active and usb0 at 169.254.42.1/16. The later retained journal shows
it remained in service until an orderly poweroff at about 247 seconds.

After an owner restart, production boot
`f4d0de47-11eb-4aa5-a19e-9263ed385a31` answered a 200-second check and showed
zero failed units, but its journal positively records CPU 5 non-response,
workqueue stalls and DPU overflows. Therefore the closing boot is **not healthy**.
Firmware appended lpcharge=1 on this boot; that observation is not a causal
claim. Attempting the standard recovery helper at 237.81 seconds timed out
in its read-only BCB check, before any write or reboot command. Manual recovery
is pending; original images are installed. The closing-current initial WSL
socket failures are host sandbox errors, not device failures; the outside-
sandbox retry supplied the actual device evidence.

## Next discriminating step

Keep the production kernel and power defaults. Use the isolated ECC candidate
with a console-eligible, identified bounded lastactivity snapshot for one
retention calibration. Require exact recovered canonical source bytes and
zero unrecoverable blocks, then separately validate crash-triggered capture.
Only after those gates pass should automatic CPU last-activity evidence guide
a causal change. Broad trace dumping, voltage guesses and repeated blind warm
boots remain unsupported.
