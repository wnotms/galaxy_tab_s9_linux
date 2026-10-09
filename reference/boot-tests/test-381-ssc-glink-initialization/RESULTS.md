# Test381 — ADB-only attempt stopped at trace admission; Test370 restored

Registration5585b2cf and owner-requested ADB admission amendmentecb0f2b4 were
pushed before deployment. Original Wi-Fi-stopped read-only preflight is retained
in preflight-1791562832399933513/. Fresh ADB-only preflight passed exact baseline,
root shell, five partitions/181 files, journal and Windows USB gates.

One controlled early-ADSP candidate boot:
178facf3-7e1e-4004-8041-cd70eb48df6d →
e1d13b92-bbe5-4306-ae4e-2e3ee79060d3 →
83f8c0a8-ae28-4642-a1fa-265905d78bf1 (restored Test370).

Candidate ADB recovered, but the owned GLINK watcher failed its combined
instance/buffer identity admission before any RPC/SSC launch. Exact persistent
watcher journal shows ValueError at glink_trace.py line63. Actual failing
instance/tracer/capacity values were not captured before rollback, so the precise
field cannot be declared observed. Independent pinned source analysis finds a
concrete observer defect: trace_buf_size=128K requests131072bytes, but 4KiB pages
with16byte buffer headers allocate33 payload pages and report131KiB, not128.
The synthetic fixture incorrectly modeled a displayed128. See postmortem/
buffer-source-analysis.json. Do not enlarge the trace budget or weaken ownership,
clock/event/boot/loss validation; a separate corrected observer must retain raw
identity values and validate the exact source-derived layout. No Test381 retry.

Raw candidate kernel journal1110rows preserved with explicit _TRANSPORT=kernel
and target _BOOT_ID. The initial journalctl -k plus a historical _BOOT_ID query
returned0rows because -k defaults to currentboot; that empty raw output is kept,
and is not accepted as complete evidence. Complete parser result has0 fault
counts/0 unclassified suspects. The clock update_config warning/backtrace is
also present in Test380; no new CPU stall/panic claimed. No GLINK trace/SSC
publication/accelerometer/rotation acceptance. This is an observer failure,
not proof of a sensor firmware root cause.

Exact rollback vendor_boot and eight owned files/assets restored. Original
rollback boots-after command exceeded10s after offline restore; its error is
retained in recovery-required.json. Subsequently readable ADB independently
confirmed unique normal boot attribution without another reboot, all five
accepted partition hashes, exact config/notes/181files, DCC absent, GNOME/palm
active, default graphical.target, ADSP offline, runtime gate/owned watcher/
assets absent and RPC/proxy inactive. Both final Windows ADB/NCM entries are
ProblemCode0, NCM adapterUp; rootADB works. Wi-Fi/SSH and host NCM TCP are untested.
No manual recovery is now required: see recovery-resolution.json and postmortem/
final-acceptance.json. PPS/pump/charging/thermal/USB/kernel code unchanged.

174 initial affected host tests PASS;40 transport-amendment affected tests PASS,
no skips. Result-only validation executed:false, qualified tests reused; no
kernel build/full rerun/CI. Verified31 Windows staging duplicates removed
(225119784bytes), retained WSL candidate/rollback sources verified.
Sensors/full port remain unfinished. Next is a corrected source-aware trace
observer, registered separately; no repeated metadata profile or registry reset.
