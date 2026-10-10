# Test389 — complete bounded RPC return-content observation

Test388 stopped at512KiB and had a host-only input-capacity parser defect.
Correct offline replay recovered130 exact registry hashes with48 missing; original
STOP unchanged. New v2 daemonbf0a9fa1 changes only logging budget to1MiB/process;
strict RX parser now accounts for exact uint32 output capacities. All wire/file/
callback/ioctl policy and library unchanged. This is a changed evidence boundary,
not a retry of the old failed observer, nor a claimed sensor repair.

One candidate boot/ordered root+sensors startup, maximum60s SSC/sample observation.
Require all178 positive stock registry return hashes and35 stat metadata. Record
pending replies separately; matching content/next2 does not prove DSP parsing.
Reuse370 kernel/config/DTB/181 and382earlyvendor; no kernel build/module/DIAG/
registry reset/selector/firmware replacement. Explicit trace opt-in/defaultOFF,
8192B/frame,1MiB/process,8MiB unitjournal,2MiB GLINK/300s boot deadline unchanged.

ADB-only admission: fresh baseline identity, five partitions/181, kernel journal,
healthy battery20–100%,10–42C/VBAT3.4–4.45V and noCode43. Three TWRP root samples
across8s before transfer. Native Servreg64/257 sensor_pd74. First limit/evidence/
identity/CPU/kernel/USB/battery failure STOP, no physical retry. No sample is STOP.
Always remove owned runtime/8overlay/328assets, restore exact370 five/181 and
normal GNOME/palm; no automatic repeated reboot or live module unload.

Qualified80 source/parser checks plus27 new namespace overlay/runtime checks;
2upstream+6 real-listener ARM64QEMU,56 source hashes. Registration/stage exact
inputs then commit/push origin/test before mutation. No full regression/Actions.
Retention380–389; no new Image. PPS/pump/DCCOFF. Sensor/rotation incomplete.
If complete content matches without SSC, stop transport observation and inspect
firmware sensor-initialization from pinned vendor/Fedora sources.

Initial registration enrollment used an unnecessary unbounded historical boot
listing and exceeded8s. The original command/error is retained, zero mutation.
A fresh short sameboot/GDM/ADB check passed; bounded recent boot listing passed.
The actual runner already uses `timeout 8 journalctl --list-boots -n 5 --no-pager`;
that registered command and all boot attribution checks are unchanged. This is
a host-only enrollment defect, not an unexplained reboot or CPU failure. No
candidate was started during enrollment; no physical retry or timeout waiver.
