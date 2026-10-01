# Test277 — device normal, acquisition refused, rollback completed

Registratione4d0a6d7 pushed before physical writes. Reused sealed272399eb497
provider/181modules/config/DTB/bootd837b52f and revised2767a887eab observer9aafabf6.
No rebuild/ADC/deadline/charging/USB/rootfs change.22local host tests and syntax
passed; unchanged272provider and2761481/W1/sparse qualification reused. Initial
host test caught inherited30s wait after8calls; corrected terminal-state handling,
original failed/timeout development evidence retained. No tests deleted/skipped.

One candidateboot1cb7050b9242406f9bdf7dd6826bacf0, one revisedobserver load on PC
SDP500mA/SinkDevice. First and only freshcall44343→44444ms, provider/consumer-110,
101ms elapsed, usable0/acquisitionstamp0/zeroed error fields. These are refusal
fields, not physical zeroV/zero temperature measurements.0.211s collection ended
on firstrefusal; no retry/reload/eight-success/30s stability or acquisition pass.
Do not relax100ms or change converter settings to obtain a passing result.

Cached terminal evidence preserved BEFORE unload. rmmod status0, host command
109.670ms, module/debugfs absent. Sameboot ADB, authenticated Wi-Fi10.125.29.81,
deviceusb0/sshd normal, no WindowsCode43. Full source-timestamp kernel JSON at
entry/end available, no new detected CPU/panic fault.20startupSMMU suspects
remain unresolved/diagnostic-only. Unload-after-refusal path was physically
validated once; this is not proof that every unload/CPU failure is now fixed.
Original275STOP and unknown freeze causation are unchanged.

Candidate pack76%/4.131V/32.4°C/Good; passivefault0/OFF01/01/IBUS0, actual cached
VBUS about4.912V. Net battery current negative under PC500mA budget; switching
charger STATUS Charging is not a measured net battery gain or PD power result.
No charger transition/PPS/pumpON/current increase/protection change occurred.

Per registration, restored exact263bootcc31efa0+181paired modules in TWRP; all
five hashes match accepted263, tested272 modules retained.gts9-test277-tested,
all older backups untouched, root unmounted/BCB cleared. One baseline reboot
cdce6deba2e04f3481679632e38ac997. Initial host readiness probe ended before
wlp1s0 appeared; original status1/raw messages and sameboot first-failure state
are preserved in rollback-boot. No reboot/reflash/cable/software retry followed.
Fresh rollback-endpoint-completion namespace supplies missing acceptance:
ADB/Wi-Fi10.125.29.166/deviceNCM normal/noCode43, sameboot attribution, config/notes
exact, DCC/observer/freshAPI absent, no failed units/new detected CPU faults.
Pack77%/4.140V/32.9°C/Good; passivefault0/OFF/IBUS0. Current baseline scan has
zero additional unresolved SMMU variants; candidate/historical suspects remain
unresolved and are not rewritten as fixed. One endpoint at uptime257.92s is not
continuous stability observation. No repeated full partition/module hashes.

See summary.json, raw observation/rollback folders and immutable per-phase
seals. Results-only validation executed:false for build/host/full/CI; reuse
existing qualification and verify evidence seals. Current device is263, not272.

Next offline work: distinguish request queue, converter-ready wait, publication
and delivery timing. Current API maps wait expiry and late delivery to the same
-ETIMEDOUT and clears output; cached publication advancing afterwards does not
identify the branch or prove converter duration. No physical acquisition retry,
ADC averaging/channel/poll cadence/deadline change, PPS or pumpON is part of277.
Independent ADC accuracy/nonzero-current/OCP/livePPS adapter/PM remain unqualified.
ActiveStage3 NOT READY.
