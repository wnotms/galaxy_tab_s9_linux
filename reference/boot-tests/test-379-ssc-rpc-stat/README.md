# Test379 — sensorsPD RPC config metadata / SSC initialization

One independently registered attempt; no hardware result yet. Purpose: test the
isolated RPC stat cleanup and compare actual returned config size/mtime against
all35 entries in the unchanged X710 archive/cache, then obtain a real SSC sample
if publication succeeds. This is a new transport-boundary question, not another
retry of the unchanged Test378 binary or proof that its FD bug caused SSC absence.

Reuse accepted Test370 kernel/config/notes/181 modules, native input, default
GNOME, clock, exact passive packages and permanent USB lifecycle. Candidate writes
only the previously qualified early-ADSP vendor_boot and Test379-owned stock
asset/trace/text overlay; it does not build/install a kernel, alter DTS/modules,
install packages, clear/rebuild registry, change USB or charging. New isolated
hexagonrpcd e1e9faa4 is ARM64 compiled and host-tested; its library is byte-identical
to Test378. Both full daemon hashes and exact patch/build qualification are bound
in registration/PACKAGE/INPUTS. It preserves the96-byte successful stat ABI.

Admission requires same accepted boot/machine/kernel/config/notes, complete
partitions/modules, ADB/device NCM/authenticated wireless SSH, no Code43/new
kernel/failed-unit issue, good battery20–100%,10–<42°C,3.4–<4.44V, PPS/pump/DCC
OFF. A high SOC does not waive the voltage gate. Current pre-registration read
reported100% and4.444V: no deployment is allowed until a fresh normal read passes.
If a user reboot changes the admitted boot, stop/rebind with fresh evidence rather
than treating it as the planned transition or blindly restarting.

Register and push to origin/test before mutations. Stage once, then one fresh
read-only preflight (maximum age600s). One early-ADSP boot uses temporary text
mode to avoid late ADSP/GPU interactions; a log screen is expected *only during
this controlled test*. Startup30s, automatic wireless admission at most90s. Verify
one native mapper/domain answer and start rootPD then sensorsPD exactly once.
RPC lifetime120s/no restart/trace≤2MiB. SSC sample window60s; only after a real
sample may SensorProxy be started for15s. No physical rotation claim without its
separate user test. Complete raw journal JSON retains boot and source timestamps.

The host parser accepts metadata only from this boot's sensorsPD unit. Every
cached config must return its exact archive size and mtime1640995200.000000000.
Missing, malformed, mismatched or failed config stat/open stops; a later fault
cannot be hidden by an earlier success. Other-unit or previous-boot results
cannot fill missing evidence. A metadata-only pass is not SSC/sample acceptance.

Stop on first safety/identity/transport/kernel/ADSP/RPC/domain/evidence fault or
bounded missing SSC. Retain complete journals and first failure. Remove the
volatile gate, stop owned RPC/proxy, restore only Test379-owned assets/text/trace
and exact accepted vendor_boot, verify the unchanged181 modules/five partitions,
and finish in Debian's normal graphical.target/GDM. Never late-start ADSP on
live GNOME, enable PPS/pump, extend/repeat the failed attempt or change production
settings to force a pass. Manual TWRP is needed only if rescue cannot respond.

If metadata matches but SSC remains absent, stop investigating config timestamp
mismatch as the leading hypothesis and inspect the firmware initialization/
hardware-service publication boundary. Do not clear the registry. This test
alone does not establish whether firmware, hardware or userspace is causal.
