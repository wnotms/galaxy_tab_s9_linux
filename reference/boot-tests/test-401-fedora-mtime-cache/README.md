# Test401 — isolated Fedora config-mtime cache comparison

One early-text boot, one sensor→root RPC launch and one30s observation. Reuse
the exact complete Fedora52-file ADSP/DTB pair and matched Test400 vendor_boot;
the kernel/config/DT/181 modules/PD maps/daemon/library/provider/startup order
are unchanged. Only35 data values in the **copied** registry/sns_reg_config are
set from current matched1640995200 to the published Fedora0. All327 other asset
members preserve bytes/archive mode/mtime, including this device's calibration.
No physical Android persist access, registry deletion/reset or foreign calibration.

This follows Test400's observed35 config stat calls and no config-file open.
It tests a real published input difference; neither cache causality nor SSC
initialization/publication is assumed. Native SoC identity remains actual65536
platform_version, never Fedora's fake0. No unchanged Test400 replay.

The existing qualified installer produces mode0644 for its created files,
including archive members marked0600. Preserve that exact400 installation
behavior; `snapshot-manifest.json` explicitly records the applied0644 alongside
the unchanged archive manifest. Runtime preparation assigns the same fastrpc
owner. This metadata distinction does not change permissions as a new variable.
Config stat references describe unchanged physical config metadata, **not** the
new cached0 values. Do not relax old metadata or historical immutable parsers.

Capture bounded full sensor-prefix bytes/hash/mode/owner/mtime in the same boot:
before, after preparation but before any RPC launch; after, after both producers
are stopped. Both units must be inactive before and after each snapshot.
Limits128KiB/file,2MiB total,2048 regular non-executable files; symlinks and
cross-filesystem files stop. Before contents must exactly match independently
qualified installation. Stage and verify the snapshot helper **and** its unchanged
rpc_return_evidence.py buddy before use.

Save the complete raw unit journal at the observation boundary while RPC is
active. Then stop producers, take after snapshot and replay every acknowledged
open/read/write/append/seek/close/extended rename. Writable scope is sensor-unit
copied registry leaves or sns_reg_version. Reject unknown/short/unacknowledged/
failed writes, config/identity/library/outside writes, capacity mismatch, unknown
methods, mutable descriptors without close, and unexplained final bytes/metadata.
Retained read-only descriptors are reported without inventing a close. Generated
calibration stays in this disposable copy; do not adopt it into factory persist.

Unchanged source-bound framing/status/config-stat/readdir checks still apply.
One exact oemconfig missing-file status69 remains the only qualified exception.
Actual call totals and unrequested reference coverage are reported, not predicted
from historical35/178/220 counts. Valid file I/O is not proof of DSP parsing.
SSC service400 and an actual accelerometer sample are separate observations;
physical automatic rotation is not accepted by this test.

ADB-only control. One fresh readonly370 baseline admission combines kernel/config/
notes/allfive partitions/181 modules/original52 firmware absences/rescue/telemetry/
full kernel journal/boot history and Windows PnP/no Code43. Copy/hash boundaries,
durable firmware transaction, actual TWRP guard and owned read-only proc scratch
are retained. Push this registration before any recovery or device mutation.
Write only matched vendor_boot; no boot/module/kernel build or hardware changes.

Keep15s startup/return health windows,300s trace deadline, two standard2s PDR
cycles, full kernel/unit journal, native SMP2P/GLINK trace and per-CPU loss counters.
First unknown/fault stops: identity/drift/unexplained boot, new kernel failure,
Code43/rescue loss, ADSP authentication/crash, evidence/PDR/trace/snapshot/I/O
failure, failed units or battery bounds20–100%,10–<42°C,3.4–4.45V. The voltage
range is a passive observation bound; float4.44V/thermal fail-closed remain intact.
PPS/pump/DCC OFF. No late-live ADSP start/retry/guessed RPC/SMEM write.

Always deactivate, preserve first evidence and restore exact370 normal GNOME:
owned overlay/isolated tree, original52 firmware absences, terminal ledger and
owned scratch cleanup, vendor readback/allfive/181/config/notes, attributed
normal desktop/ADB/device NCM. Lost shell requires manual recovery, no blind
second boot. Do not wait for a commit to perform required recovery.

Host-only changed tests/syntax, unchanged build/source qualifications reused.
No full suite/routing/Actions. Retention392–401; existing370 runtime/rollback and
399/400 provider comparison images retain explicit401 consumers; no new image.
This registration contains no hardware result. Sensors/rotation are unfinished.
