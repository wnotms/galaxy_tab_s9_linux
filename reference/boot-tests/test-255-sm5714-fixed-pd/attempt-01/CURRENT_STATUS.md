# Test255 attempt01 physical status

The owner authorized physical testing. The Stage2 candidate is installed and
booted on `a5b8b87f1487422a9035a1db74f85667`. TWRP readback and the first
Debian boot verified candidate boot `26ef6bd1…`, vendor_boot `d80d03cd…`,
config `cd7ec9cb…`, notes `fb3d2496…`, and the exact 181 matched modules.
Installed init_boot, dtbo and vbmeta match Test254. Exact Test254 boot and
vendor_boot images are staged in `D:\android\gts9-active\gts9-test255\`;
its 181 modules are retained under `.gts9-test255-original` beside older
Test252 and Test249 rollback directories. No rollback has been executed.

First-boot PC USB gate passed: TCPC registered, Type-C reports Sink/Device,
SM5714 ordinary charger input limit is 500 mA on the PC, Test253 adbd remains
active, ADB/NCM/Wi-Fi work, Windows reports no Code43, no failed systemd unit,
and source-time kernel analysis found no new fault or suspect. The historical
boot-register/SMMU startup variants and QCA setup warning remain bounded as
documented; the earlier clk-rcg2 and display warning also occurred on Test254.
At 991 seconds uptime, the same candidate boot remained responsive with no
new fault in the complete kernel journal.

The owner subsequently disconnected the PC cable. A fresh Wi-Fi SSH window
passed 155.473 seconds of continuous `usb_online=0`, Discharging, negative
pack current, Good health and stable 28.4°C temperature, on the same boot.
The complete ending kernel journal had no new fault or suspect and systemd had
no failed unit. The earlier 300-second monitor only records a wait for the
manual transition and is not counted as battery-only time. The tablet is now
unplugged and awaiting PC USB reconnection. Verify ADB/NCM/SSH on the same
boot for 150 seconds after reconnect. Do not connect the Lenovo 18W PD source
in this attempt: there is no independent VBUS meter or 5V-only source for the
registered voltage gate. Full Test255 fixed-PD acceptance is pending.

The candidate build's 1183 host tests passed before physical testing. A
subsequent changed-suite rerun on the WSL host was interrupted after a global
`sync` blocked for over 11 minutes in an existing rootfs test; it is not
recorded as a pass. The Test255 deployment scripts passed syntax checks, exact
181-file archive/manifest validation and a simulated module install/restore.
