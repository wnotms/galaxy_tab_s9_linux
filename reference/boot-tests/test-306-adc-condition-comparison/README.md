# Test306 — one pump-OFF ENHIZ / ADC operating-condition comparison

Registered purpose: test the qualified Test305 one-conversion condition profile,
not PPS or direct charging. Compare the original vendor OFF/attached condition
from Test304 with one conversion after temporarily clearing ENHIZ bit7. Preserve
actual before/during/restored values, ADC/gauge windows and original faults.
A smaller discrepancy is evidence for this condition experiment, not calibrated
VBAT, causality proof or a100ms charging grant.

Software: source9dceb767, Test305 qualified kernel/config/modules. Reuse existing
build/static/1,749-test qualification while hashes stay identical. Only boot and
the matched181-file module directory are replaced. All other partitions, DTS,
SM5714 ordinary5/9V/current/4.44V/thermal, USB/adbd/rootfs remain unchanged.
The diagnostic profile publishes no ADC companion, requests no PPS, supports no
pump ON and executes no second conversion after the first worker finishes.

Current entry is **NOT READY: recharge pending**. Do not use the historical
0%/3.14V boot to start installation. A fresh normal baseline preflight must
prove accepted Test299 notes/config/allfive partitions/181modules, rescue,
Good pack health, SOC5..<80, VBAT3.5..<4.3V and pack temperature20..<38°C.
The previously accepted ordinary18W source is for recharge only; candidate
boot/conversion takes place with the PC data cable connected and charger absent.
Require WindowsCode0, ADB, Sink/Device, device NCM/sshd and real pack thermal
sensor, unchanged PC SDP500mA and4.44V design. One host NCM probe is recorded; a host-only timeout does not prolong
this OFF-only scope or authorize charging.

Sequence: preflight once; verify local/staged package; accepted BCB helper and
ordinary reboot to TWRP; verify allfive hashes/machine identity/181 originals;
unique306 module slots and boot write/readback; clear BCB/unmount; one candidate
boot; collect the single startup conversion and full kernel JSON;15-second
device-normal endpoint; restore accepted Test299 boot/original181 modules,
verify allfive hashes and restored identity. Rollback is unconditional because
this diagnostic image is not a new production baseline. No extra conversion,
observer module, tracing, APDO/PPS request, charger swap or current raise.

First new I2C/ADC error, restoration mismatch/pending, unexpected mode/current,
CPU/kernel fault, thermal issue, Code43, identity/attribution/evidence/rescue
failure stops observation. Save raw first-failure evidence and use verified
rollback; if rescue cannot execute, require manual TWRP instead of blind writes.
Known startup REVBLK evidence remains diagnostic and cannot be erased/promoted.
Read-validity flags and original ADC bits must be present; zeros are not proof.

Registration/package/runner must be committed and pushed before any physical
mutation. Preparation is offline; no physical command is executed merely by
importing a module or building the package. A later execution requires fresh
entry gates; this registration does not waive the pending battery recovery.

After battery recovery and PC reconnection are confirmed, the reviewed commands
are `python3 reference/boot-tests/test-306-adc-condition-comparison/host_flow.py
preflight` followed promptly by the same script with `run`. `run` includes
the endpoint and unconditional restore; it does not retain the diagnostic image.
Do not execute these commands merely because offline registration is ready.
If automatic restoration cannot finish, preserve its failure and use `restore
--from-recovery` only after manual TWRP entry. No rerun of the experiment is
allowed within this namespace.
