# Test321 — pump-OFF continuous raw ADC observation

Purpose: determine whether eight bounded raw register reads complete in the
continuous OFF configuration used by the same-model references, after Test318
showed no READY. This is a new profile/question, not a replay or a waiver of
Test318. Raw reads can be stale: no freshness/current/coherence/OCP grant.

Reuse committed d2b4c127/b4f5c3e3 build and scoped qualification under
`reference/charging/sm5440-continuous-raw/`. Full host report is NOT PASS because
retired historical image prerequisites are absent; do not hide that or rebuild
expired images. New parser/lifecycle tests run locally; no kernel/full rebuild.

One candidate boot on unchanged PC USB fixed5V, no cable action. Native worker
performs one eight-read diagnostic,20ms first/50ms subsequent polling choices,
2000ms transaction budget, exact ADC restoration. READY optional and recorded.
Startup services may become ready within150s; explicit native ADC/I2C/faults
stop immediately before service-state classification, with raw evidence retained.
No replay, second candidate boot or manual diagnostic trigger. Successful
admission gets one15s same-boot rescue/health endpoint, then exact rollback.

Entry: accepted311 normal cmdline/config/notes, allfive partition hashes and181
paired module hashes checked once, healthy real pack20–<80% SOC/20–<38C,
ADB/deviceNCM/authenticated Wi-Fi rescue, Sink/Device and WindowsCode0/no43.
Kernel/config/notes/DTB/package hashes must match frozen RAW inputs. Publish
registration/package/runner/tests and accepted preflight before mutation.

Deployment changes boot and paired modules only through accepted TWRP helpers.
No rootfs/service/USB/Type-C charging-policy/DTS change, PPS, pumpON, current
increase, protection or ENHIZ write. Fixed5<=1.8A/fixed9<=1.5A/4.44V/thermal
fail-closed remain. First kernel/CPU/I2C/ADC/fault/rescue/Code43/identity/history/
evidence error stops. Raw VBUS4.5–9.5V, VBAT3.5–<4.44V, IBUS0,die<42C.

Unconditionally restore original accepted311 boot plus181 original modules,
verify allfive, clear BCB/unmount, then prove normal baseline boot/health/rescue.
If recovery is unreachable, stop and preserve mutation state; no blind retry.
Rollback artifacts are operational inputs assigned to this current round,
not a permanent historical-image exemption. Current retention window312–321.

Keep full kernel JSON at boundaries/first failure, original snapshots, command
metadata and machine-readable verdicts. Success proves OFF raw read transport
only. Full PPS/direct-charge port, calibration/current/cutoff/OCP, native active
worker/adapter and fallback/PM acceptance remain unfinished.
