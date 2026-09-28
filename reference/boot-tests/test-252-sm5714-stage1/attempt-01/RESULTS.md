# Test252 attempt01: charging observations passed; USB gate stopped

Authorized physical run on2026-09-28. The three registered battery/ordinary
charge observation stages completed, but **Stage1 full physical acceptance
is stopped, not passed**: native USB ADB remained offline after reconnecting
the computer. No further physical experiment, service restart, gadget reset,
configuration change or kernel change was made after that first anomaly.

| Stage | Registered / observed | Observation samples | Actual result |
| --- | --- | --- | --- |
| Battery-only |150 /151.021s|16|online0, Discharging, current−1.326..−0.755A; SOC92;29.8..30.0°C|
| Lenovo YG65G USB-C2 ordinary charge |1200 /1201.035s|121|online1, Charging; all121 measured currents positive,+0.432..1.381A; SOC92→97;30.6..31.2°C;4.330..4.418V|
| Charger plug-out |150 /151.127s|16|online0, Discharging, current−1.253..−0.548A; SOC97;30.2..30.5°C|
| Computer USB reconnect |Final transport gate|—|Windows interfaces present/ProblemCode0; USB ADB offline; NCM and Wi-Fi SSH working|

Every observation sample retains the complete kernel journal JSON and supply
uevents. There are155 raw snapshots:16 battery-only,121 charging and18 plug-out;
the first two plug-out snapshots precede physical detach and are excluded from
its16 observation samples. The independent raw-evidence audits reconcile all
telemetry, boot IDs, command statuses, source timestamps and kernel journals.
All phases share boot `fcb9a367-fa8e-43df-afb1-08db722ff2f1`. No unexpected reboot,
CPU-stall/panic signature, new unexplained kernel fault, I2C/charge fault or
failed systemd unit was detected within the captured windows. The final
post-stop kernel JSON contains1100 rows and no fault or suspect message.
TWRP supplied the independent pre-deployment SOC91 reference, versus candidate
SOC92. Official8400mAh typical/8160mAh rated minimum design metadata remains
unchanged; TWRP's different9800mAh vendor-reported value is preserved as separate
evidence, not used to recalibrate the gauge or change the design capacity.

The selected charger is USB-C2, rated18W, with labelled5V3A/9V2A/12V1.5A
outputs. The owner confirmed that connection and subsequent detach; USB-C1
was instructed to remain unused, not independently inspected. Cable make and
rating were not supplied. The device reported BC1.2 DCP and programmed1.8A
input limit during charging. This is not measured IBUS. Actual VBUS, a PD
contract and SM5440 direct-charge telemetry are unavailable; no particular
negotiated voltage or18W charging power is claimed. The driver has no new
TCPM/PPS/direct-charge path. Computer SDP before/after the wall-charge stage
programs500mA and does not overcome system load; its Charging label with
negative pack current is not charging acceptance.

## First non-clean evidence

Computer reconnect was confirmed by the owner. Windows recognizes the
composite device, ADB interface and NCM interface, each with ProblemCode0;
no Code43 was captured. Repeated bounded read-only ADB detection captures and
the post-stop snapshot show `gts9wifi-0001 offline` on transport36. Device
adbd34.0.5-12 logged at20:41:04 local time:

```
UsbFfs: connection terminated: read 554 failed with error Cannot send after transport endpoint shutdown
UsbFfs: offline
destroying transport UsbFfs
UsbFfsConnection being destroyed
```

adbd remains active. The post-stop process snapshot has no UsbFfs-worker;
the main and endpoint-open threads wait in futex, while the monitor thread
remains present. These observations identify the failed channel, not a proven
deadlock cause. The source-bound Windows NCM socket uses interface11 and
`169.254.191.237` to reach `169.254.42.1:22`; both its SSH banner and authenticated
NCM shell return successfully, and Wi-Fi SSH returns the same boot ID.
This is not evidence of a CPU wedge or proof that the SM5714 candidate caused
the USB failure. The unchanged profile already documents possible USB ADB
transport failure with next-boot recovery in `docs/FAST_DEBUG_CHANNEL.md`.
That documentation does not turn this failed final gate into a pass.

Full raw Windows PnP, adbd/service and device-side kernel evidence is under
`usb-reconnect/`, with a separate complete `post-stop/` identity capture.
The first console display of Windows PnP bytes encountered a UTF-8 decoding
error; raw command output/status had already been saved. Decode the preserved
ACP output appropriately; post-stop captures remain independent, not overwritten.
An optional initial process lookup used unavailable device `rg`; the later
direct `ps -L` snapshot supplies the process evidence. Both limitations remain
visible in raw outputs, with complete replacement evidence and no verdict change.
The separate full final-gate
helper was not run because its USB prerequisite failed. Identity reconciliation
uses captured Wi-Fi data and normalizes Windows CRLF/SSH LF for cmdline tokens.

## Current device and preserved scope

The candidate remains installed for offline analysis, **not promoted to an
accepted production baseline**. Post-stop read-only checks independently verify:

- exact embedded config `410e4fe28f6fcc25950aba0029f8cda310b39ddbf1653f3eaa7b334e62f3b722`;
- raw kernel notes `fc35e05b1f8ddaf38faf228cd4aa7f02408e15d92beb908077c979536f99f0ed`;
- candidate boot `5402b7c45c06568591a86cce807af0820fddb23c03a1d9a49cec780dd7e45ec0`;
- all four other partitions unchanged, including accepted device vbmeta;
- all181 matched candidate module files and all181 retained Test249 original files;
- DCC absent from config, device/sysfs/getty/write symbols; unchanged CPU
  watchdog/panic/ECC profile, cmdline and live splash-region property;
- persistent boot attribution, no failed unit and no new kernel fault.

No rootfs/service/USB/DTB/CPU setting was changed during this test. Deployment
changed only boot plus the complete paired module directory. The on-device
`.gts9-test252-original` and verified external Test249 boot/modules remain
available; no rollback or cleanup was needed to collect evidence through the
working SSH channels, and none was performed. The wall charger is disconnected.
Initial and final pstore were empty; no post-failure recovery boot/last_kmsg
capture was attempted because the device remained responsive.

The same-model repository at `/home/ms/Samsung/gts9wifi-fedora-linux` was
rechecked after charging: clean at `ab123e7d1dbc0cbcd35661f9761197e977b15aa9`,
all eight reference files byte-identical to that commit, and candidate driver
source unchanged. The earlier conversion/float/current/thermal/protection
comparison remains in `SAFETY_REVIEW.md` and `validation/same-model-review.json`.
The physical current sign and charge trend now have evidence; source review and
this bounded observation cannot guarantee absence of hardware damage or prove
long-term reliability. Hot/cold protection trips, suspend, cold/power boot,
other chargers, PD/PPS and SM5440 were not physically tested.

Local `bash scripts/check-stall-offline.sh --changed --base HEAD~1` selected
all1067 retained tests through the unknown-archive-path fallback:1067 passed,
0 failures/errors/skips in77.241s, plus shell syntax checks. Its raw host-only
log and executed:true record are under `validation/`; mock fault fixtures in
that log are not device faults. No GitHub Actions was started.

Next scope is independent offline USB ADB/FunctionFS reconnect analysis.
Keep this attempt stopped and sealed; do not silently restart adbd, reset the
shared gadget, reinterpret it as a full pass, or advance to Stage2/Stage3.
`summary.json` and `usb-reconnect/post-stop/summary.json` are the machine-readable
result/current identity. Original prepared registration/build seals remain intact.
