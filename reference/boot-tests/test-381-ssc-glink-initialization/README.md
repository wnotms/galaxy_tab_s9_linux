# Test381 — early SSC GLINK channel initialization

One independent diagnostic boot, registered before deployment. Test380 actual
metadata/read-length pass and SSC absence remain unchanged. The question is
whether early ADSP GLINK control negotiation/channel opening exposes the next
firmware publication boundary, including native RPMSG/DIAG inventory. This is
not another metadata fix attempt, sensor acceptance or electrical bus proof.

Reuse accepted Test370 Image/config/notes/DTB/181 modules, frozen early-ADSP
ramdisk and matched stock DSP assets. New vendor_boot differs only in two
trace boot arguments (BUILD.json contains the exact old/new strings and
identical ramdisk/DTB/bootconfig hashes). No kernel/config/DTS/charging/USB,
watchdog/panic, hardware register or DIAG control changes. No registry reset,
late ADSP start on GNOME, endpoint binding or data-payload tracing.

The named gts9_test381 instance records six existing qcom_glink version/open/
close control events from early boot. Buffer:128KiB per CPU (8 CPUs, about1MiB
ring storage, not a total RAM overhead claim). Actual local clock and raw
per-CPU statistics are saved; no precise cross-CPU timing claim. The owned
watcher stops tracing by boot uptime300s or when collected. It never enables
or alters a global trace. Raw trace limit1MiB, complete JSON limit2MiB; any
loss, missing ADSP event, stale identity or incomplete evidence stops.

Preflight is read-only and fresh≤600s, proving exact five partitions/181 files,
config/notes, DCC absent, ADB/device NCM/authenticated Wi-Fi and current sameboot
journal. ENROLLMENT.json records only exact pre-existing rows; every new severe
error/CPU signature still stops. No future error waiver. Battery Good/present,
SOC20–100%, temperature10–<42°C, VBAT3.4–4.45V measured observation bounds;
4.44V float/charging current/thermal safety unchanged. PPS and pump remainOFF.

One candidate boot,15s startup observation, then one native mapper inventory,
one2s Servreg query, one ordered rootPD/sensorsPD launch and60s SSC window.
Require exact35 config stat entries as the unchanged runtime qualification.
Record SSC400 presence independently from a real finite accelerometer sample;
no sample alone is not proof that SSC400 is absent. Sample permits a15s
SensorProxy check; channel-trace completion alone never passes sensors/rotation.

Any first unexpected fault stops, preserves raw evidence and restores exact
Test370 vendor_boot plus only Test381-owned asset/text/RPC/watcher files. Also
restore on diagnostic completion or sensor success. Eight transaction-owned
regular files; temporary text mode only, then normal default GNOME. No repeat
candidate/reflash/restart, no permanent sensor/DIAG service, no CI. Reuse exact
ARM64 library/daemon and kernel qualification; only affected host tests/syntax
and offline vendor packaging validation are executed.
