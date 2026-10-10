# Test385 results

**STOP_HOST_OVERLAY_FILESET_BEFORE_CANDIDATE_INSTALL_RESTORED370**.
Registration e86ffa40 pushed;86 affected host PASS/0skip, syntax, no new build/
full test/CI. Three same-root-TWRP boot76a79788 snapshots at8.47/12.62/16.79s
passed the new8.49s read-only transport admission. No ADB closure this round.

Exact328 stock assets copied without starting RPC/ADSP. Desktop install then
rejected the registered5-file manifest: its inherited ALLOWED set still had8
old RPC-inclusive paths. This is a host installer scope bug. No desktop files
were written, no candidate vendor write/boot/moduleload/DIAG request occurred.
It does not answer the handshake question and is not a device failure.
Mocks/scope-count host tests did not exercise the real installer allowlist;
new actual temporary-root transaction tests are required for the correction.

Mandatory cleanup restored all328 assets/originalfirmware, unchanged181modules
and five baseline partitions; desktop ledger absent. Normal return uniquely
attributed Test370 boot88dce57b-a010-47c3-bc3b-44be289242a1, config599ca47a/
notes5c0e8233, fullkernel/no newCPU/panic fault, GNOME/palm/rootADB/deviceusb0.
ADSP offline; no module/ready gate/Test385 rootfs ledger/files. No WiFiSSH/host
NCMTCP test under currentADB-only scope.17 staged Windowsduplicates verified and
removed, WSLsource/raw retained. First STOP and original scripts preserved.
Results-only executed:false, reuse prior qualification. No charging/USB changes.

Next Test386: exactlyfive minimal installer paths plus real install/rollback/
partial-fault/foreign-file/identity/escape tests, fresh registration before one
candidate. Do not rerun385 or claim zeroDIAGopens as a firmware rejection.
