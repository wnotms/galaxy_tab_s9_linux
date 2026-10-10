# Test399 — native ADSP negotiation observed; SSC absent; desktop restored

One attributed candidate boot `24630e73-4186-4099-8531-80225306d38b` ran
the unchanged Test398 sensor→root RPC startup once. Kernel/config/notes/DTB,
181 modules, stock firmware/registry assets and initialized-readdir daemon/library
remained unchanged. Only isolated native boot-trace enrollment changed. No
SMEM write, DSP control packet, diagnostic module or charging change.

Complete raw trace contains 22 records: five native ADSP SMP2P records and
17 ADSP GLINK records. All eight CPU statistics agree with the raw header,
with zero overrun/commit-overrun/dropped/read events. Host independently
recomputed and matched the device provider facts. Trace was stopped at
74.82s uptime, within the registered 300s deadline.

On CPU7, `smp2p-adsp` negotiated open with `SMP2P_FEATURE_SSR_ACK` at
0.559857s. Four `slave-kernel` notifications followed: status/value 0/0,
2/2, 6/6, 6/6 at 0.632741, 0.633813, 0.647874 and 0.692869s. GLINK version
and IPCRTR/FastRPC opening are present. The trace uses local timestamps;
do not infer cross-CPU causality. No SSR-ack event was captured, which does
not itself imply failure. Native events do not inventory unconfigured remote
entries or establish a stock sleepstate provider requirement.

Both qualified PDR snapshots returned UP; same-client unregister/closure
completed. Both RPC units stayed active during the registered 30s window
(33.800s through collection). All 35 config metadata and 178 registry-content
checks passed. All 220 successful directory replies, including two EOF replies,
were initialized. One missing `oemconfig.so` call returned acknowledged status69.
SSC400 remained absent; no accelerometer sample or automatic-rotation acceptance.
No detected CPU/panic/Oops/RCU/CSD or new severe kernel fault. This directly
establishes native SMP2P negotiation in this boot, not SSC initialization.

Exact370 vendor, isolated assets and nine owned overlay files were restored.
Ordinary GNOME boot `1f8302ac-b357-4e48-8b26-d786bb0de2dc` is uniquely
attributed. All five partition hashes, 181 module hashes, config/notes,
GDM/palm/ADB/device NCM and 20.726s return observation passed. No failed unit
or new severe kernel fault. Final battery: 100%,32.8°C,VBAT4.445V within the
registered 4.45V observation bound; 4.44V float policy unchanged. PPS/pump/DCC OFF.
Original install and discovery runners exited0; no retry or second experiment.

29 affected scope/runtime tests passed before deployment, reusing39 provider
component tests and unchanged daemon/library ARM64 qualification. Results-only
tests executed:false; no kernel rebuild/full regression/Actions. Registration
seal unchanged; new evidence is separately sealed.

34 Windows stage files were hash-verified and deleted, retaining the ADB folder.
The superseded382 vendor image was hash-verified and retired after399 construction
and recovery completed: no active file user, all390–399 mutation ledgers terminal,
no current userspace/scripts/tests path consumer. Its source/components/build/hash
evidence remains. Current399 candidate and exact370 rollback remain; no moved or
archived image copy. Retention window390–399.

Sensor bring-up remains unfinished. The next source comparison should target
sensor firmware initialization and QMI publication prerequisites. Do not repeat
this unchanged startup or describe the missing SSC service as failed native
SMP2P negotiation; that negotiation is now directly observed.
