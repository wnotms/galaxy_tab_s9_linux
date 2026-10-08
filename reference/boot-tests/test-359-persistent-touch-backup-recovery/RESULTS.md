# Test359 — optional component installed; current-boot no-op passed

On exact331 boot1adc0f13, the one scoped backup-state acknowledgement and normal
backup completed successfully (Result=success, ExecMainStatus=0). No timer,
RTC/NTP/clock policy changed. Original358 stop and its rapid-trigger discrepancy
remain recorded; its cause has not been established.

Three hash-bound files were installed outside the181 module directory. The
optional gts9-touch.service is enabled through **gdm.service.wants**. One start
returned already-loaded/zero-insmod; no new driver probe or hardware write.
Sameboot/GDM/SSH remained responsive; battery75%,32.3°C,Good/Discharging.
All three persistent GDM masks/default target unchanged; no failed unit.
Complete kernel journal before/after has1143records in each, identical cursors,
zero new records/faults. Installation device duration2.875s; host8.163s includes
transfer/evidence. Full raw JSON gzip and hashes preserved.

After the completed operation, the owner paused work and manually shut down/
restarted. Resume read-only check found25ff0ad0; owner confirms manual reboot/
opening. Prior journal has orderly poweroff/SIGTERM/journal stopped. Same331
config/notes/module hashes and Good73%31.8°C; currently Charging. GDM/touch are
inactive as expected for retained **text-only** startup, optional unit still
enabled; loader check reports ready without insmod. Prior/current full kernel
journal/history/pstore saved, no recorded severe signature or pstore entry.
Do not call automatic desktop/touch loading validated. Current GUI is inactive,
unlike the successful installation endpoint in the prior boot.

Initial prior-boot collection with a hyphenated UUID failed; original raw is
retained and corrected explicit compact UUID query succeeded. Analysis also
uses word boundaries for Oops/BUG, avoiding an ordinary ramoops registration
false positive. These are evidence corrections, not repeated hardware tests.

17loader tests and original8actual-C/W1/37CRC qualification reused unchanged;
results-only tests/build executed:false. SHA/JSON/journal attribution and source
protection reviewed. No kernel/config/DT/battery/TCPC/SM5440/USB/ADB/181-dir
change, flash, reboot command or suspend/firmware/doubletap/Spen experiment.
3481200s grant remains unused; future fresh desktop-inactive admission and
original331/finalTWRP endpoint preserved.

Next independent desktop test can start installed unit/GDM once in this
owner-confirmed new boot; normal loader and raw evidence are still required
before claiming the real persistent load path is functional.
