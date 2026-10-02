# Test292 results — stopped before observer loading; exact baseline restored

**STOP_ADB_TRANSPORT_NO_OBSERVATION; exact263 rollback readback verified.**
Registration04eb8241 was pushed before mutation. Paired290 bootd268d702 and181
modules installed/readback verified; other4partitions unchanged. One candidate
bootb8945a982675454582302d26fbd232d4. Zero observer loads/calls/samples, no trace,
PPS, pumpON, current increase, legacy100ms waiver or charging grant.

## Startup and interruption

The host readiness predicate accepted three active services and a valid passive
sample before Wi-Fi DHCP completed. The original ADB packet/error remains in
candidate-admission: Wi-Fi address missing/ambiguous. A sameboot packet observed
Wi-Fi10.125.29.240 at77.285s after reboot, inside the registered180s readiness bound.
18portable tests including no-IP/duplicate-IP/read-failure cases qualify the
host-only predicate fix; it requires unique IPv4 before admission. No reboot or
acquisition was repeated. The original16test run and failure remain preserved.

Work was interrupted before completing the boundary. Upon continuation around
08:47UTC, strictauthenticatedWi-Fi still reported the same candidate boot, while
Windows ADB first failed daemon startup and then returned an empty device list.
Windows composite/ADB/NCM interfaces were Code0 and NCM Up; device adbd was active,
DWC3 configured and Sink/Device. This does not prove a CPU failure or TCPC cause,
and the elapsed interruption is not a registered stability observation.
Collection stopped before any module load. Fresh fulljournal/history, device adbd/
gadget state, host daemon path/starttime, Windows evidence and authenticated
sameboot are under candidate-supplement and stopped-endpoint. Full kernel scan
found no CPU fault signature; startup display diagnostics remain unresolved.
No userspace/service/gadget/Windows-driver repair or automatic acquisition retry.

## Recovery and final state

Because ADB was unavailable, the approved BCB helper check/request and ordinary
systemctl reboot were sent over strictly authenticated Wi-Fi. Native TWRP ADB
returned; all5partition hashes and181original module files were restored and
verified, old backups retained, candidate stored at .gts9-test292-tested,
BCB cleared and root unmounted. Raw ancillary availability is preserved at both
recovery boundaries. rollback-install records exact restoration, not inferred
from a successful reboot command.

Final Test263 bootb06bb6c2cac5481da40fe8d6c317b9e3, Wi-Fi10.125.29.6, exact263
notes/config/normalcmdline/DCCabsent, unique history, ADB/authenticatedWi-Fi/device
NCM/WindowsCode0, no failed units or CPU fault signature. Battery Good,52%,3.879V,
31.9C; SM5714 PCSDP500mA and4440mV design retained. Current-282mA is reported as
observed, not inferred from the charging status.

**Final passive health gate REFUSED**, not a successful acceptance. Captured
SM5440 snapshot latched fault1/startup_pending1 with stale last valid OFF sample,
VBAT3498500uV vs independent fuel-gauge3879000uV, IBUS0/mode01/01/protection
f2/e7/37/fe. Its power_supply reported Unspecified failure; old raw sample cannot
be reused as fresh. This discrepancy is not calibrated physical VBAT evidence
and its cause is unresolved. No threshold/fault reset/converter/power policy was
changed to manufacture a pass. The system/rescue endpoint is responsive, but
another passive or active test must not bypass this health refusal.

## Qualification and next work

Reused unchanged290 kernel/artifacts1494full and291 module26/full1520/W1/sparse.
Kernel build/full regression executed:false for this host-only/results work;
18portable tests executed once after readiness correction. No Actions/CI.
Grouped transfers, native recovery readiness, concurrent independent boundary
reads and exact rollback used; interruption and host readiness issue prevent
claiming an overall speed benchmark. No active100ms/ADC/calibration/OCP/PM/PPS
qualification follows from this test. Next analyze host USB transport and the
captured passive VBAT/health refusal offline before a new registered round.
**ActiveStage3 NOT READY; complete wired-charging port remains unfinished.**
