# Test317 — fixed9 OFF-context retained, source gate stopped, accepted311 restored

One installed candidate boot cc6d3fae43e44b5e945a47f7f4260aa5 is uniquely
attributed to the accepted311 preflight via journal history. Running embedded
config/notes match the qualified Test316 candidate. ADB later recovered;
read-only salvage collected complete1111-row kernel JSON, boot list, retained
SM5440 context, native source, pack/roles/services and actual switching controls.
Current Wi-Fi10.139.153.59 authenticated as the same boot/machine.

The early-boot fixed9 diagnostic reached context_phase10, context_error0 and
cleanup_error0. Five actual OFF acquisitions are retained. Initial REVBLK was
an inactive read-to-clear latch with healthy live status; subsequent new
confirmations show no latch/live fault. All five registered sample-prefix gates
pass: mode OFF, fresh ADC_READY provenance, zero IBUS, VBUS below9.5V, checked
ENHIZ/control restoration. Final conditional ADC VBAT3.8415V vs adjacent fuel
gauge3.798V differs43.5mV, within the existing100mV diagnostic comparison bound.
Raw bytes and original source timestamps are preserved, not recalibrated.

The live source at collection had already changed to fixed5V/source generation13;
retained context is source generation9. Original current-source and fixed9
endpoint gates therefore refuse. Registered Wi-Fi capture was not executed,
and the15s same-fixed9 endpoint is not accepted retroactively. No substitute
source receipt, recaptured/replayed candidate boot or deadline relaxation.
This is an evidence/source continuity stop, not a newly detected CPU wedge.
No new CPU/panic/I2C failure is identified by the existing1111-row classifier;
known early display/SMMU diagnostics remain separate and retained.

Acquisition-to-ADC-read brackets are129,128,129,128,130ms; these software
intervals include I2C and scheduling, and do not prove intrinsic chip conversion
period. The diagnostic500ms bound passes, while these are **not** accepted
100ms active ADC/OCP samples. No pump enable, PPS Request, higher input current,
independent sensor calibration or software-OCP certificate is granted.

Unconditional exactaccepted311 rollback completed immediately after salvage:
original boot f4efa07e88ca3bc012b373827529fe4f92f35105e0040623da6486f1509fdacb,
original181 matching module files, allfive partitions verified. Native recovery
helper/BCB and normal reboot used; no recovery partition/bootloader/rootfs
configuration write. New final boot6f0d319be8bf487184a324c15560c304 is attributed,
config/notes/ordinary4.44V controls match accepted311, ADB/deviceNCM/hostNCM-SSH
and services/roles/DCC absence pass. Pack19%,3.709V,29.4C; no blind repeat boot.
Mutation state rollback_required=false; accepted311 is installed.

This results-only change runs no new build or regression. Reuse unchanged
Test31773 affected host tests and exact Test316 candidate qualification. No
GitHub Actions. Full charging port remains NOT READY: integrate real native
observation/pack/worker only after new qualification, resolve physical100ms
ADC/current/cutoff/OCP evidence, then separately accept ON/PPS/fallback/PM and
higher power. Do not replay this frozen diagnostic or enable pump based solely
on the retained OFF context. No new physical test is started here.
