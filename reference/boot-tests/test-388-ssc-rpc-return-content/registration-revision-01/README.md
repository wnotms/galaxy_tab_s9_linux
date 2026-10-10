# Test388 — actual RPC return/content observation

New boundary after Test387: do listener2 encoded replies contain exact stock
registry bytes and return successfully through the host transport? SSC/sample
acceptance remains separate. One candidate only; reuse Test370 Image/config/DTB/
181 modules and Test382 early vendor/GLINK. Fedora0.4/wire/stat/library unchanged;
new daemon9e988475 adds listener/header trace only, explicit opt-in in two owned
files. No callback/file/encoding/ioctl policy change. No registry reset, selector
changes, DIAG/control/masks, PPS/pump, kernel/module/USB/charging/input change.

Fresh ADB-only baseline boot/config/notes/five partitions/181/journal/battery
20–100%,10–42C, observedVBAT3.4–4.45V, Windows noCode43; no future error waiver.
Three TWRP root/sameboot samples across8s before transfer/remount. One attributed
candidate boot,15s health,native Servreg64/257 sensor_pd74,ordered root/sensors RPC
once,maximum60s SSC/sample observation. No sample is STOP, never sensor PASS.

Record TX/next2-return/RX exact context/scalars/bytes. Cap8192B per frame,512KiB
per daemon; explicit limit/error stops, total unitjournal2MiB. Preserve full raw
unit/kernel/QRTR and loss-free GLINK; observer deadline300s/geometry unchanged.
Strict parser rejects sequence/process/attribution/context/length gaps or limits.
Compare all178 nonempty stock registry files from actual linear open/read/close
replies; hash reported written bytes only, require each response acknowledged
at the host transport. A final blocked call remains pending. No DSP parsing or
SSC publication proof is inferred from next2 success or returned content match.

First CPU/kernel/USB/battery/identity/evidence/SSC failure stops; remove gate/owned
runtime and restore exact Test370 vendor,8overlay and328 isolated assets, then
normal GNOME/palm with five/181/config/notes checks. No live module unload/blind
reboot; manual recovery only if unreadable. Historical results stay immutable.

70 source/parser/profile tests and2 upstream+6 real-listener ARM64/QEMU cases
qualified offline. Review21 owned runtime/overlay/scope tests plus integration.
No new kernel/full regression/Actions. Freeze/stage/commit/push origin/test before
physical run. Archive first result/cleanup verified Windows staging. Retention
Test379–Test388; no new Image. This is a changed evidence boundary, not another
unchanged Test387 hypothesis or startup retry. Default GNOME is restored.
