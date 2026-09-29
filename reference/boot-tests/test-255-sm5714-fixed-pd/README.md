# Test255: SM5714 Stage2 fixed-PD acceptance

**Offline candidate registration only. Not deployed or physically tested.**
Owner authorizes code/DTS/config/tests/build, explicitly forbids automatic
device commands, rootfs writes, flashing/modules/reboot or Stage3. Current
installed state remains Test254 with Stage1 and Test253 userspace adbd repair.
Read [Stage2 plan](../../../docs/SM5714_STAGE2_PD_PLAN.md),
[source audit](SOURCE_AUDIT.md), Test254 final CURRENT_STATUS/RESULTS/
PHYSICAL_SUMMARY and Test253 attempt04 before any future physical registration.

Purpose: prove basic fixed5V/9V Sink PD, ordinary SM5714 switching charge and
PC Sink/Device gadget continuity within bounded windows. Not a power benchmark,
universal safety/reliability proof or extension to powered dock/Host/DP/PPS.
Linux remains7.2-rc3; HVC_DCC off, Test254 container config preserved, no TCPM
core/DWC3/gadget/adbd/rootfs or OPP changes. Max9V input1500mA=13.5W;
5V input<=1800mA, charging input programming stays<=the positive TCPM budget. With budget0 or
<100mA, Q4 is open and the input register is at its100mA minimum; complete VBUS
isolation/zero system draw is not claimed. Stage2 probe starts inhibited even
before TCPC registration, so retained9V cannot use an unowned DCP1800mA policy. Pack2100mA/float4440mV/
pack thermistor/Stage1 thermal and suspend fail-safe retained.

## Future separately authorized physical attempt

Commit/push a dated fresh rescue registration and identity before maintenance.
Retain new Test254 rollback boot+exact181 files separately; do not overwrite
the retained Test252/Test249 directories. Same release string is insufficient.
Read back candidate and rollback hashes, five partition identities and rootfs
protected Test253/gadget/SSH files. Deployment should use the established
appended-DTB boot path only after confirming packaging/extraction identity;
the new DTB must be in both appended boot and vendor_boot copies. Keep extracted
Test254 vendor cmdline/bootconfig/empty ramdisk exact; preserve init_boot,dtbo,
vbmeta and charge/service settings. Confirm effective live Sink/Device/PDO/
GPIO133/peripheral topology, not only the packaged blob.

| Step | Window and evidence | Pass gate |
| --- | --- | --- |
| A rescue | Fresh ADB at D:\\android\\platform-tools, NCM SSH, Wi-Fi SSH; rollback, SOC/temp/current, stock battery identity | All rescue/identity intact; no charging anomaly |
| B identity | Exact boot/DTB/config/embedded config/notes/all paired files | DCC absent, Stage1+Test253+Test254 preserved |
| C battery only |150s, complete kernel journal and raw battery readings | Discharging, negative pack current/trend, normal temp |
| D PC USB | ADB shell+byte/hash transfer, NCM+Wi-Fi, Windows PnP, typec roles | Sink/Device, enumeration, no Code43/kernel fault |
| E5V | Known5V-only source;150s initial window | TCPM stable, charge sign/trend explained, pack normal |
| F9V | Known fixed-PD adapter; raw TCPM/typec/power_supply evidence and inline PD meter | Fixed9V Request/Accept/PS_RDY, no APDO selection |
| G9V |5min first; then20min only if first passed; sample>=every5s | VBAT/IBAT/SOC/temp/USBtype, contract+actual input current stable; no reset loop/I2C fault |
| H unplug |150s battery-only | online0/Discharging/negative current |
| I charger->PC | Same boot; nativeADB+NCM<=60s;>=150s responsive; preserve every initial failure | New Test255 reconnect evidence, no permanent offline/Code43 |
| final | Full five hashes/config/notes/modules/protected files/full journal/failed units/transports | No new fault or unexplained boot/config change |

Battery raw CURRENT_NOW is retained as measured. Charging status does not
guarantee positive net pack current under load; a mismatch is suspect until
SOC/current trend is understood. Do not invert readings to make a gate pass.
TCPM budget and its voltage_now are not independent measured VBUS: a suitable
inline USB-PD meter is required for the actual9.5V stop gate unless a separate
X710 ADC calibration is justified. Do not modify kernel just to get diagnostics.
Higher voltages/APDO may exist in source capabilities; they must never be requested.

## Stop and recovery

First non-clean stops all later stages. Immediately disconnect charger for
actualVBUS>9.5V, VBAT>4440mV design, pack>=45°C in first run or rapid abnormal
rise, clearly abnormal current, repeated I2C/TCPC failures, hard-reset or
attach/detach loops. Also stop on reboot/panic/Oops/soft/RCU/CSD lockup, loss
of both rescue channels, Windows Code43, requested PPS/APDO or SM5440 probe.
Preserve full raw source-timestamped journals, transport failures, readings and
Windows PnP evidence. No retry series, core patch, current increase or Stage3.
Do not heat/request high voltage/raise current to test protection limits.

After a stopped authorized attempt, rescue to TWRP using the existing proven
method and label/UUID-verified partitions/card. Restore exact retained Test254
boot ea73e65836ab316af658ed53273be0ec6351b335750978095e509054164509f7 and its
paired directory; read back hashes. Restore the original vendor_boot49ae21b3… if changed for Stage2 DTB. Preserve
init_boot/dtbo/vbmeta,
Test252 .gts9-test254-original and Test249 .gts9-test252-original pairs. No
automatic rollback is part of this offline task. Record fresh acceptance after
any separately authorized restoration. Battery-only/suspend/cold/dock behavior
outside these windows remains unverified.
