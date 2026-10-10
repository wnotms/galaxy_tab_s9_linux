# Test386 results

**STOP_DIAG_RECIPROCAL_OPEN_ABSENT_RESTORED370**.
Registration80754a63 pushed first;83 affected host PASS/0skip including12 actual
minimal-overlay transactions. No kernel/module rebuild/fullregression/CI.
Recovery8s/root/sameboot passed; exact328 assets and corrected5-file overlay
installed/readback, one qualified earlyvendor boot. Candidate26ad9a13 attributed,
config599ca47a/notes5c0e8233/181/fivepartitions/nativeADSP/rootADB/usb0 passed.
No RPC launch/ready gate; no prior transport failure replay.

Matched native rpmsg_ctrl module loaded once and bound the unique X710 ADSP
control parent. Live build-ID/kernel/config/boot identity admitted. One native
DIAG device created; its one open returned EINVAL after approximately5.22s host
command interval. Ledgerbeforeblockingopen retained; endpoint not opened or
destroyed, requires registered reboot. Zero protocol writes/masks/read packets.
No force-load, live unload, reopen or retry.

**New raw evidence**: AP→ADSP `OPEN DIAG[3/0]`, ADSP→AP `OPEN_ACK DIAG[3/0]`.
No reciprocal remoteOPEN DIAG within collected boot window. Complete2754B raw
trace19/19 events, all8CPU overrun/commit-overrun/dropped-events0. `local` trace
clock: no precise crossCPUlatency assertion. StockLinux7.2 create_local first
waits5s forACK then5s forremoteOPEN; it needs both. Timeout→ERR_PTR→NULLendpoint;
rpmsg_char logs `failed to open DIAG` and returnsEINVAL. This supports second
wait timeout rather than an ioctl encoding failure. Originaljournal scan's one
priority3 failed-open suspect/error is preserved, not rewritten as CLEAN. No
CPU/panic fault signature detected. ACK alone is not a usable endpoint, decoded
DSPlog/SSC service or proof of permanent firmware channel absence/rootcause.

Mandatory normal recovery restored exact370/vendor,328 assets/originalfirmware,
5 overlay files and unchanged181modules. Baseline bootd8654881-69bd-4603-92ee-
8e14a3f81ad9 uniquely attributed; fivepartitions/config/notes/fullkernel/failed
units/rootADB/usb0/GNOME/palm/defaultgraphicaltarget pass, ADSPoffline. Reboot
cleared temporary rpmsg_ctrl/endpoint/ledger; no live rmmod.17 verified Windows
staging duplicates removed, WSLsource/raw kept. WiFiSSH/hostNCMTCP untested under
ADB-only scope. Results-only executed:false; prior83 qualification reused.

Next: compare exactfirmware DIAG/SSC initialization and nativecontrol lifecycle
with Fedora/stock primary sources. No identical DIAG probe retry, genericrouter
or mask negotiation. Sensor samples/rotation still incomplete; this result
changes the next diagnostic choice but does not complete the sensor port.
