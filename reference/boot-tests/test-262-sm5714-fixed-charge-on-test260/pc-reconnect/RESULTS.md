# PC reconnect endpoint check

After the owner confirmed PC USB attachment, native Windows ADB lists
`gts9wifi-0001 device`, actual UDCa600000.usb is configured, adbd remains
PID862/NRestarts0. Sink/Device and PC SDP input limit500mA are retained.
The same boot18bce160 remains installed Test260; full embedded-config hash
f2891de2b636820c8ad10b8682d7e68a9f4447c4af70cdfcd2b953de942f40b5 and kernel
notes5425adeadc1c07b2eea7fc2869b5a884eba4c3ad0406b7c217dbe91dc8ef116b match.
/dev/hvc0 and tty/hvc0 are absent; hvc0 getty inactive.

One NCM readiness sample verifies Windows NIC9/source169.254.59.206 matches
WSLeth2/direct route; one source-bound SSH authentication returns the same boot.
Readiness metadata capture16.107s is not physical recovery time. No unready
sample, authentication retry or Code43 is observed. Wi-Fi authentication/health
passes; pack29.4C/Good, SOC65%, passiveSM5440 Good/Not charging/IBUS0.
PC supply is500mA: battery net current-0.404A while the USB charging path is
online; this is not independent18W charging or a positive-current acceptance.

Full kernel and USB-service journals retained, no new detected kernel/passive
fault or failed unit; initial startup warning unchanged. No reboot/configuration,
flash, module replacement, PPS or pumpON. Unchanged Test260 partition/module
identity qualification is reused; current config/notes/boot verified live.
This is a post-attachment endpoint check, not a timed physical reconnect test
or proof that the earlier audible Windows issue is permanently repaired.
