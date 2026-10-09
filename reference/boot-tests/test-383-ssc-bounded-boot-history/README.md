# Test383 — bounded SSC boot-history admission

Registration only; not deployed. Previous Test382 STOP and original history-query
errors remain unchanged. Test382 proved live trace geometry and early native
QRTR/FastRPC handshakes; it stopped before RPC and does not prove SSC availability.

## Question and single change

Can one ordered root-PD → sensor-PD startup publish SSC and additional GLINK
channels after bounded boot-history admission? Replace the full history query
with `timeout 8 journalctl --list-boots -n 5 --no-pager`, under the existing
10-second host deadline. Installed systemd 257 supports this form; the stopped
Test382 recovery verified immediate output. Do not use a wall-clock cutoff.

Keep strict attribution: the preceding boot must appear, the last prior ID must
match, and exactly one unique successor must equal the new boot. Unchanged IDs,
missing history, duplicate IDs, extra boots or an old ID outside these five
entries stop the test. Truncation is not permission to omit the preceding boot.
Use this same bounded command for admission and required rollback.

## Frozen artifacts and ownership

Reuse the exact Test382 vendor_boot (SHA-256
`37178ba27129d31d12331e4f7f8e67dc318a8732b1bb1b8daa2b6b5387d08f29`),
`userspace/sensors/glink_trace_382.py`, kernel, config, DTB and all 181 modules.
No kernel build or vendor repack. The kernel trace instance intentionally remains
`gts9_test382`, matching that image and qualified helper. Test383 uses separate
owned rootfs paths and units; shared instance name is not a second observer.
Before enabling/collecting, require exact boot/config/notes, instance ownership,
no symlink, all six registered events, nop tracer, local clock, 4 KiB subbuffer,
16-byte header and 131 KiB displayed capacity on all eight CPUs.

Request stays 128 KiB per CPU; ring-buffer page rounding produces 33 pages and
134640 payload bytes. Preserve actual fields, raw control trace and loss counters;
require zero loss on every CPU. Raw trace cap 1 MiB, JSON cap 2 MiB; watcher stops
by boot uptime 300 seconds or collection, whichever occurs first. Local clocks
do not establish exact cross-CPU elapsed times. No payload tracing or DIAG packet,
binding, reset, registry wipe, foreign firmware, hardware or charging change.

## One bounded device attempt

Fresh read-only preflight must match accepted Test370 and current enrollment.
Owner-selected temporary ADB-only transport: root ADB, device USB state and
Windows no-Code43 are required. Wi-Fi SSH and host NCM TCP are untested, not PASS.
Install only the registered vendor_boot and eight owned overlay files plus the
qualified stock asset transaction. Preserve boot IDs and complete raw kernel
journals. One early ADSP boot, 15-second initial observation, unique native
Servreg endpoint/domain, one root-PD then one sensor-PD launch; wait at most
60 seconds for SSC. Preserve all 35 actual config metadata checks and registry
read evidence; no daemon restart to manufacture a result. Existing runtime
lifetime remains 120 seconds.

Stop on the first identity/attribution, transport, battery safety, kernel fault,
firmware, geometry/loss, domain, metadata or evidence failure. No same-profile
retry. Capture the first failure and required cleanup without turning it into a
PASS. Always restore exact Test370 vendor_boot and only owned overlays/assets;
verify kernel/config/notes/five partitions/181 modules, full journal, default
GNOME and palm handling. Leave normal Debian, not TWRP. If ADB is lost, retain
failure and request manual recovery rather than sending a blind reboot.

PPS, pump and HVC_DCC remain OFF; charging current, thermal policy, USB/adbd,
network configuration and input drivers are unchanged. A complete trace is a
diagnostic endpoint; SSC publication, accelerometer sample and automatic screen
rotation are independent acceptance items. Do not claim a root-cause fix from a
host admission change. Follow-up depends on new channel evidence.

## Offline validation and execution

Run the new bounded-history scope suite and qualified geometry-helper suite;
retain prior 158-test qualification for unchanged dependencies. Syntax-check
new host Python and mount shell. No full regression, kernel build or CI launch.
Hash-bind registration, stage and verify offline; commit and push origin/test
before any physical preflight/install. This registration does not execute a
second candidate attempt after Test382's stop.
