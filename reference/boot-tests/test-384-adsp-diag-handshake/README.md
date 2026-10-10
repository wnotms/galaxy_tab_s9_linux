# Test384: one AP-initiated ADSP DIAG handshake

Purpose: determine whether X710 ADSP accepts one locally initiated DIAG channel,
a capability not tested by Test383's remote-initiated GLINK inventory. This is
not SSC discovery, physical rotation or sensor acceptance.

## Frozen baseline and changes

Accepted Test370: exact boot/config/notes/DTB/181 modules and permanent USB
lifecycle. Reuse Test382/383 qualified early-ADSP vendor_boot and zero-loss
six-event GLINK observer (`gts9_test382`). No Image/config/DTB rebuild. Five
owned text/observer overlay files and transactional stock assets are restored
through the existing offline ledger. Root/sensors RPC services stay inactive.

The one temporary `rpmsg_ctrl.ko` is unmodified Linux7.2-rc3 code, matched to
Test370 provider and all 32 imported symbol CRCs. Loading explicitly changes
runtime and causes normal external-module taint; it is not unchanged production.
No installation under the production module directory and no force-load.

## One physical attempt

Register and push before mutation. Fresh root ADB, exact five partitions/181
modules/kernel identities, safe battery, unique boot history (last five boots),
no new kernel/USB faults or failed units admit one candidate boot. Five seconds
of ordinary startup health; trace collection must finish before uptime 300s.
One uniquely unbound X710 ADSP control parent; no adopted endpoints or overrides.
One native CREATE_EPT/OPEN for DIAG, source/destination ANY. Device timeout 15s,
host timeout 19s. At most one 1s poll and one 64KiB passive read. Zero payload
writes, feature negotiation or masks; no DIAG_CNTL/DIAG_CMD or RPC launch.
A successful OPEN/ACK with no packet proves handshake only, not decoded logs.

Any first identity/CPU/panic/new severe kernel/USB/battery/evidence failure,
module/control error, endpoint error or deadline stops; never retry in this boot.
Preserve ledger before blocking OPEN plus whole kernel journal and raw GLINK.
Always restore exact Test370 vendor/owned overlay/assets and boot normal GNOME.
Normal reboot clears temporary module/endpoint state: NEVER live rmmod/unload,
including cleanup failure. If transport prevents recovery, request TWRP rather
than send blind boots. No PPS/pump/charging/DCC/GPU/USB kernel changes.

## Closed pre-existing USB observation

Registration enrollment found one EP0 cancel message in accepted Test370 boot
0047b944, at 583.682456s; lifecycle unbind/cable detached followed at
583.682509671s. The source calls usb_ep_dequeue unconditionally on FunctionFS
unbind; DWC3 logs and returns -EINVAL if already absent. This supports a cancel
context, not a proven caller stack or USB fix. Same-boot root ADB recovered,
no failed unit/new severe row at assessment. Preserve the complete enrollment
journal, exact cursor and unit window. Only that closed historical row is
enrolled; no waiver for a future identical message, Code43 or transport loss.
No physical mutation occurred during this assessment.

## Qualification and rollback

Run affected helper/runner/geometry host tests and syntax checks. Reuse existing
kernel/vendor/module build qualification, no full kernel or unrelated regression.
No GitHub Actions. PACKAGE and INPUTS pin all consumers and deployment artifacts;
REGISTRATION_SHA256 pins registration/evidence. Restore exact Test370 through
TWRP/vendor readback and owned ledgers; unchanged 181 modules verified.
Follow-up depends on new raw handshake evidence; no automatic DIAG router/mask
activation and no unchanged retry. Charging and rotation remain untested here.
