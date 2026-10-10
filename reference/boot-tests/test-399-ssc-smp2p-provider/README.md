# Test399 — native ADSP SMP2P provider observation

Purpose: observe native ADSP SMP2P negotiation/notifications together with the
existing GLINK transport during one exact398 RPC startup. This is a provider
observation, not a charging experiment or a claim to fix SSC initialization.

The only vendor-image difference over382 is boot trace enrollment: one isolated
`gts9_ssc_provider` instance, six GLINK and four SMP2P events,128KiB requested
per CPU with measured131KiB reporting. DTB, signed firmware ramdisk, bootconfig
and every other unpacked header argument are byte-for-byte unchanged. AVB footer
and payload SHA256 verified offline. Original report spacing assertion failure
retained separately; no second image build. Kernel/config/notes/181 modules,
stock assets,398 initialized-readdir daemon and companion library unchanged.

The exact370 baseline must pass one fresh full read-only preflight. Stage hashes
are checked at transfer/write boundaries. ADB is the control transport; device
NCM/SSH services are checked, no host Wi-Fi readiness loop. This registration
is committed/pushed before any recovery, vendor write or candidate reboot.

One early-ADSP text boot; exactly one sensor→root RPC start. Two previously
qualified PDR snapshots bracket the30s startup observation. Collect full raw
kernel/unit/GLINK/SMP2P evidence, all eight CPU trace statistics and QRTR history.
Record SSC400 and actual sample separately if available; do not infer rotation
acceptance from a working transport or successful file callbacks.

Capture all ten named events without a device filter, then derive ADSP-only
facts using the verified `smp2p-adsp` platform name. Preserve bounded other
processors' records. No shared-memory writes, sleepstate-bit update, DSP control
packet, diagnostic module, bus access, registry reset, firmware substitution,
role/USB/charging/OPP change or live ADSP/GNOME restart. The observer only stops
its boot-owned trace instance. No feature/mask messages are sent.

Raw trace ≤1MiB, complete JSON ≤2MiB, ≤4096 records,300s boot trace deadline.
Exact boot/config/notes/instance/event/filter/format/buffer gates apply. The host
independently recomputes device provider facts; raw/header/per-CPU counts and
zero loss must agree. Local timestamps support per-CPU ordering, not cross-CPU
causality. A missing negotiate event is `NEGOTIATION_NOT_OBSERVED`, not proof
of a failed negotiation. Native events cannot inventory unconfigured entries.

First unknown/fault stops immediately: CPU/panic/Oops/RCU/CSD, unexplained boot,
Code43/rescue loss, identity drift, battery/thermal/health/voltage boundary,
PDR/metadata/readdir/content/status failure, incomplete trace or severe failed
unit. Do not reattempt a failed completed trace collection, restart RPC or repeat
this unchanged startup. Preserve raw first-failure evidence and restore before
spending time on a push. PPS/pump/DCC OFF,4.44V float/thermal policy unchanged.

Always restore exact370 vendor and the nine owned overlay files plus isolated
assets, then ordinary normal GNOME with attributed boot/identity/rescue/health
and the existing15s return window. No permanent userspace change is accepted
by this diagnostic scope. Runtime packages remain qualified/passive/inactive.
Rollback writes only original vendor_boot; boot/init_boot/dtbo/vbmeta/modules
are not replaced. Keep ordinary fixed-PD fallback intact.

29 affected registration/runtime tests PASS0skip, including the actual nine-file
install/partial-fault restoration, host/device evidence agreement and first
non-clean stop/mandatory return. Reuse39 provider-component tests and unchanged
398 daemon/lifetime/readdir/ARM64 qualification. No kernel rebuild/full suite/
routing change/Actions. This file records a plan, not hardware results.

`registration.json`, `PACKAGE.json`, `BUILD.json`, `INPUTS.json` and registration
seal bind exact inputs. Retention390–399;382 image is still the explicit builder
input at registration,370 is the current rollback. Re-evaluate the expired382
image consumer after this completed scope; never copy/archive an expired image
to evade cleanup. Raw evidence and source/hash metadata remain retained.
