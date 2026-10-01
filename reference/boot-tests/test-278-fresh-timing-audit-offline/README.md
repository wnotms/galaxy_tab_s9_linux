# Test278 — offline fresh-request timing audit

Current device restored263; no physical commands or kernel modifications.
Frozen272 provider and276observer, failed275 and device-normal/refused277 evidence
remain unchanged. Answer what timing facts are actually established, which API
branches produce-110, how25ms jiffy polling fits100ms, and what observation is
still needed. Do not repair by changing converter mode/average/poll/deadline.

Source provenance INPUTS includes pinned7.2-rc3 timer/workqueue files, frozen
provider and same-model vendor/Fedora controls. Verify hashes before deriving a
report; save analysis/host tests/qualification reuse. Exact config/DT/hardware/
rootfs source unchanged. No kernel build/full/CI for pure host analysis; affected
host tests and syntax only. No routing or historical test changes.

Never turn missing timestamps into0 durations, error output into measurements,
cache publication age into conversion duration, or ULONG jiffies into absolute
BOOTTIME without a captured clock anchor. Preserve275freeze cause UNKNOWN;
277unload-after-refusal succeeded once, acquisition failed100ms criterion.

Future minimal attribution plan only: inspect available tracing/symbols offline,
prefer symbolic resolution of existing request/worker boundaries and filtered
workqueue events. No tracefs write/probe registration/module load is executed.
Full converter phase needs its own paired timestamps; missing optimized function
symbols cannot be worked around with guessed machine-code addresses. Tracing
perturbs timing and cannot be treated as a production realtime qualification.
ActiveStage3 NOT READY; no PPS/pumpON/current permission.
