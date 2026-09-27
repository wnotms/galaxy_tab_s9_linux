# Test 234: distinguish live persistent-RAM integrity from reboot retention

Authorization: owner “继续解决cpu卡死问题”, continuing the previously authorized
controlled physical diagnostic workflow. Test-233 established 464 changed bytes
in a known pmsg record. A successful write did not inspect the RAM itself.

Only added kernel behavior is opt-in diagnostic patch 0023 and the cmdline
ramoops.gts9_live_read=1. It exposes the existing PMSG mapping as a root-only
read-only binary sysfs file, drained on removal before freeing the mapping.
No extra memory mapping, RAM writes/resets, layout/ECC/config/frequency/voltage
change; normal production watchdog settings remain unchanged. No CSD probe or
lastactivity instrument is added in this candidate. Do not infer crash recovery.

1. Save healthy current boot/recovery evidence and all five partition hashes.
   Backups are the verified original boot/vendor_boot from test-230. Verify
   artifact sizes and hashes, flash only boot/vendor_boot, read back completely.
   init_boot/dtbo must match current partitions; vbmeta/recovery untouched.
2. Require a responsive boot, unchanged ramoops geometry/ECC=0 and the new live
   attribute. Read RAM twice; require equal copies and an empty valid header
   before writing, or stop to investigate other writers/data.
3. Generate a new identified known payload; verify source device hash; write
   once via /dev/pmsg0. Quiesce writers, read the live ring twice. Decode only
   the pinned ARM64 ECC=0 ring layout and require exact payload bytes. Preserve
   both raw captures, source/boot IDs and hashes. A live mismatch stops reboot.
4. If live exactness passes, issue one direct normal Debian reboot; capture
   raw pstore and compare with the exact source. This narrows the interval of
   corruption without presuming reset/firmware/RAM/archival cause.
5. Restore original boot/vendor_boot via TWRP with full readbacks; retain USB
   ADB/NCM rootfs and verify the final production boot. No wedge series.

If the device stops responding, collect available channels and ask for manual
TWRP recovery. No repeated blind boots. The live view is not an atomic snapshot;
two identical reads and quiesced PMSG writers are required.
