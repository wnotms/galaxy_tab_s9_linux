# Test329 — unchanged USB ordinary-boot recovery

Incoming Test327 Code43 survived one owner20s disconnect/direct alternative port;
Wi-Fi/sameboot/pack/pumpOFF remain healthy. Separate USB recovery, not PPS test.
Reuse existing gate/parser/Recorder, manually orchestrate one ordinary
`systemctl reboot` over strict Wi-Fi after registration/push and fresh sameboot
boundary. No flash, BCB, rootfs/service/gadget/driver/register changes, modules,
PPS or pumpON. No new runner/build/tests; qualifications reused.

SOC20–<95% here only permits an ordinary default-OFF restart, consistent with
accepted Test327 ordinary operation. Test328 PPS SOC<80 and all thermal/VBAT
ceilings remain unchanged. Recovery never qualifies PPS entry at83%.

Save unique boot attribution, exact config/notes/cmdline, native ADB shell,
Wi-Fi/device NCM, current WindowsCode0/no43, healthy pack/thermistor/roles/pumpOFF,
complete kernel journal and15s sameboot endpoint. Readiness bounded150s;
first non-clean stops and retains evidence, no second reset or blindwrite.
No rollback software replacement because software never changes. Rescue loss
requires owner assistance, not an automatic configuration change.
