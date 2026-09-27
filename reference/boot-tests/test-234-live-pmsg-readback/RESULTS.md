# Test 234: live RAM exact; data damaged across reboot

The source boot `6608a95d-e2ca-4da6-8073-874b67ee95bb` wrote capture
`89586fce-5e0c-40ce-accc-4badf0a131d9`, 33,005 bytes, SHA-256
`a5c9ed9d50744ae4305ea59de75b33f2fa89dbb7271b48e232a7dc02a505dbae`.
Two empty live-ring reads matched before the write. Two full 1 MiB reads after
the write matched each other and an independent device-side RAM hash. Decoding
the ECC=0 ring yielded the exact source bytes. A third read immediately before
reboot still matched, at source uptime 282 seconds. Raw ring SHA-256:
`115defbe6cb3d53bbf3158c731208c63702e530717b97eb353d407179833e023`.
No other PMSG writer was reported. Source health showed zero failed units.

A normal direct Debian reboot reached observer
`4c78d2cc-7ed8-4a33-be1c-05c2345f77c5`, the immediately next retained journal
boot. Its newly archived PMSG retained the exact header and length but changed
**251 bytes / 293 bits**. Device-side SHA-256 and two independent pulls agree:
`1162ab2a009df3d80ec0a8b91d6fd270dee986cb5210d4b03521b269eae53feb`.
See `observer/verdict.json` and `damage-summary.json`; raw bytes are preserved.

This establishes correct bytes in the existing persistent-RAM mapping before
reset, narrowing damage to the interval after that final live read and before
the observer's archived-file reads. It does not isolate reset, firmware,
physical RAM, next-boot pstore processing or archival, and does not establish
a shared cause with CPU non-response. ECC remained zero; reserved memory,
DTB, config, power/frequency settings and production watchdog profile unchanged.
No wedge series is ready.

## Observer failure and pending rollback

At uptime 54.35 seconds the observer answered boot ID/uptime, then the command
stalled at `systemctl --failed`. It timed out after 25 seconds. Subsequent USB
exec-out, USB journal pull and TCP ADB connection attempts also failed/timed out.
The early journal already captured on the host has no positive CPU non-response
signature. Classify this observation as **unattributed loss of responsiveness**,
not a clean boot or a demonstrated CPU-number-specific wedge.

Manual TWRP recovery was requested. **Original boot/vendor_boot have not yet
been restored**; the live-read diagnostic candidate remains installed. Next
save the failed boot's persistent journal from TWRP and restore the verified
test-230 production backups with full partition readbacks. USB/NCM rootfs
configuration was not changed. Keep this rollback status current.

Six focused probe tests, shell syntax checks, the ccache diagnostic build and
bundle validation passed before flashing. No full host suite was needed for
the isolated probe; a host pass does not establish hardware recovery.
