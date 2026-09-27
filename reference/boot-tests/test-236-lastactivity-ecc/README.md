# Test 236: validate bounded CPU activity retention with ECC

Authorization: owner continues CPU diagnosis and previously authorized flashing
and physical testing. Test-235 proved exact known PMSG bytes after ECC corrected
246 symbols, but its level-6 console probe was filtered by loglevel=4. CPU
failures persisted, including CPUs 2/5 in a later manual boot. Production
partitions were restored; a subsequent production boot also wedged on CPU 5.
Do not infer a CPU fix, failure rate or crash-retention gate from PMSG alone.

Candidate combines existing opt-in patches 0022 (lastactivity) and 0024
(ECC=64). Use the already tested `boot/cmdline.lastactivity.example.txt`
profile from tests 230/231, including its independently checked watchdog
arming, not an assumed production baseline. No driver/power/frequency/voltage
change. Rootfs and USB NCM/ADB coexistence configuration stay unchanged.
Normal builds remain unaffected. Restore original boot/vendor_boot afterwards.

The actual snapshot uses **pr_emerg, level 0**, which passes loglevel=4. It
records positive last observed IPI/CSD activity, never full history. The maximum
58-line snapshot with maximum values and modeled prefixes is under 20 KiB;
ECC leaves 349,428 console bytes, or 218,356 after a 128 KiB crash reserve.
The same strict host parser/reference comparison used in tests 230/231 applies.

1. In TWRP verify device, all partition sizes/hashes and original backups.
   Save available recovery evidence. Build/test/package first; flash only
   boot/vendor_boot and require complete readbacks. No vbmeta/recovery write.
2. On the source boot capture immutable boot ID, cmdline, ECC=64, READY/capture
   ID and watchdog runtime 1/1/1/10. If a stall precedes the planned manual
   snapshot, preserve it and stop the healthy calibration; do not call an
   automatic later boot a clean source.
3. After at least 150 responsive seconds, manually dump once. Require all
   eight valid CPU records, 48 events and exact complete source markers. Save
   the source journal on the host and decoded snapshot hash before reboot.
   Confirm actual printk console threshold admits level 0. Preserve refusal
   of a second dump. No panic injection or repeated wedge trials.
4. Perform one direct ordinary Debian reboot with the same ECC candidate.
   Prioritize pulling raw console bytes before slower journal queries. Capture
   observer boot ID, file hash and ECC notice; repeat the pull/hash check.
   Require source/observer adjacency in retained boot history, zero
   unrecoverable blocks and byte-identical canonical markers using the source
   reference. An invalid/racing CPU remains invalid even if its text survives.
5. On transport failure recover through TWRP or a responsive owner restart.
   Preserve original pstore via the original observer journal's binary FILE
   field if a later boot replaces disk archives; match any previously captured
   raw hash. Include .journal~ files when retrieving unclean disk journals.
6. Restore original boot/vendor_boot with full five-partition hash checks.
   Validate final boot explicitly; command responsiveness alone is not a pass
   when its journal contains CPU non-response. Stop rather than repeat blind
   boots if recovery or a healthy final boot cannot be established.

A healthy manual-snapshot retention pass still does not prove automatic
crash-triggered capture. That is a separate gate before causal wedge trials.
