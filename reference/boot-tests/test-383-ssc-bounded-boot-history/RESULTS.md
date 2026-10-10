# Test383 — complete bounded GLINK observation; SSC still absent

Registration8263ebe2 and admission revision2 3b84687d were pushed before the
first physical attempt. Initial read-only preflight STOP on one previously
unenrolled DWC3 EP0 dequeue error remains preserved; original manifests/seal
are in admission-revision-01. Revision2 enrolled only that exact historical
cursor-bound row after same-boot ADB/Windows/health assessment. No wildcard or
future kernel-error waiver. 55 affected host tests PASS,0 skips; no kernel build,
full regression or CI. Fedora's exact listener/registry patches already reused.

One candidate boot16d836fc-cf62-498a-8153-69162f346e54, boot history uniquely
attributed with the device8s/recent5 query. Kernel/config/notes/five partitions/
181 modules, Sink/Device, ADB, Windows/noCode43, ADSP and native mapper passed.
Host execution context interrupted after install/readiness00; missing process
handle and absent process were confirmed. Same responsive candidate at28s was
identified and resumed in a separate evidence directory, without another install
or reboot. Required rollback was retained. The resume process completed normally.

Native Servreg returned all6 domains, including msm/adsp/sensor_pd instance74.
Root-PD then sensor-PD started once/active. All35 actual config stat size/mtime
checks passed. At most60s SSC probe window (62.116s including final collection):
no service400, no accelerometer sample, no SensorProxy/rotation acceptance.
No new kernel fault/panic/CPU signature detected in the registered candidate.
The only logged RPC open error remains oemconfig.so absent; necessity unknown,
no fabricated stub or foreign firmware. Current sensor root cause is unproven.

Owned trace collected/stopped at171s boot uptime:2534bytes,17/17 events, all8CPU
loss counters0. Version1 negotiates features1. IPCRTR and FastRPC have complete
bidirectional OPEN/ACK and native bindings. Seven early remote channel names:
pcie_drv,mhi_sat,IPCRTR,sleepmonglink-apps-adsp,adsp_apps,
fastrpcglink-apps-dsp,LOOPBACK_CTL_LPASS. No additional channel events through
this ordered-RPC observation. No DIAG-named endpoint or QRTR4097; QRTR769 is
SLIMbus, not DIAG. This bounds the observation, not all firmware capabilities.
Local trace clock does not support exact cross-CPU duration claims. Complete
raw trace/JSON, loss counters, RPC/kernel journals and endpoint inventory kept.

Exact Test370 restored boot0047b944-8e83-42dc-9652-deae22df90c0, unique boot
attribution, all5 partition hashes/181 modules/config/notes/DCC/full kernel gates
passed. GNOME/palm/default graphical target and ADB normal. ADSP offline, RPC/
proxy inactive, gate/assets/observer/overlays removed. One empty ledger directory
was removed with rmdir after preserving initial cleanup check; no recursive
unknown-path deletion. SSH and host NCM TCP untested; device usb0 present.
All31 verified Windows staging copies removed225122350bytes; WSL sources retained.
The preflight USB service log exceeded GitHub100MiB, so raw bytes are retained
losslessly as gzip with verified uncompressed SHA-256; no diagnostic rows deleted.

Verdict: GLINK_DIAGNOSTIC_COMPLETE_SSC_ABSENT_RESTORED370. Sensor port incomplete;
no unchanged profile repeat. Fixed charging,4.44V/thermal safety, USB/adbd/input,
DTS/kernel/config/modules unchanged. PPS/pump/DCC OFF. Results-only tests
executed:false; reuse55-test qualification. Next source-supported boundary is
AP-initiated diagnostic endpoint access, not another stat/registry retry.
