# Test384 results

**STOP_RECOVERY_ADB_CLOSED_BEFORE_CANDIDATE_INSTALL_RESTORED370**.
Registration ac338abb/formatting-seal 2aa764bc pushed before mutation. Fifty
affected host tests passed, zero skips; no new kernel build/full regression/CI.

One recovery entry from Test370 boot 0047b944. Recovery identity, package hashes,
read-only root mount, five baseline partitions and 181 module files passed.
At 02:16:53.858600 UTC the remount command received `error: closed` (status1).
No asset-install, overlay-install or candidate partition-write command ran.
No candidate Debian boot and no rpmsg_ctrl load/DIAG create/open/protocol write.
The initial mandatory cleanup could not find the TWRP serial; its original
recovery-required record is retained. The physical process was subsequently
confirmed absent, and TWRP ADB present again. No retry of installation or probe.

Fresh recovery cleanup verified all five partitions still exact Test370, 181
modules unchanged and no candidate asset/overlay ledger; it cleared the owned
recovery request and unmounted. Normal return then uniquely attributed baseline
boot 56bddde7-029e-496a-a0a3-f26a0491e5ad from the preflight boot history.
Config599ca47a/notes5c0e8233, all partitions/modules, full kernel journal,
GNOME/palm/default graphical target/root ADB/device usb0 passed. ADSP offline,
no temporary module, ready gate, endpoint ledger or Test384 rootfs files.
No detected kernel CPU/panic signature in return window. Wi-Fi SSH/host NCM TCP
were not tested under the owner's ADB-only scope.

This is a recovery transport failure, not a negative DIAG handshake or sensor
result. USB interruption cause is unproven; no CPU crash is inferred from an ADB
command closure. The earlier enrolled EP0 row remains exact historical evidence;
no new-error waiver was added. Both first errors/raw commands stay immutable.
17 Windows staged duplicates (225176082 bytes recorded exactly in STAGE_CLEANUP)
were hash-verified and removed; WSL source artifacts and raw evidence retained.

Next: improve recovery transport admission/first-failure evidence before a new
registered attempt. Do not rerun Test384 or deploy the unchanged failed runner.
No PPS/pump/charging/USB driver or permanent modules changes. Sensors and
rotation are still incomplete; results-only host/build execution is false.
