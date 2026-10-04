# Fresh startup and historical photo attribution

Owner reports powered on. New boot `ac442c81-d5f1-4dc1-8991-82210d1cae3e`
has embedded config/notes matching accepted311. ADB and authenticated Wi-Fi SSH
respond; device usb0 is UP, host NCM TCP not checked. Current pack zone37 is
`sm5714-battery`, enabled at 30.7°C and matching battery TEMP. SM5440 is Not
charging. SOC9%, VBAT3.670V and IBAT-405mA were captured together; initial
interactive read was30.6°C. PC ordinary input can leave net negative current;
enabled switching charging does not mean PC input covers system load.

The photo's224.226049s message is retained in historical boot
`acdd2dfc7f8a4970aa57d71edab99df6`. Prior Test299 full thermal enumeration
identifies old zone37 as **sm5440-passive**, with real pack zone38 enabled.
Accepted Test300 `.no_thermal=true` prevents the noncontinuous passive cache
from registering as a thermal sensor; TEMP errors and pack safety remain.
Zone numbering is dynamic. Current full journal has no temperature disable
message. This reconfirms the retained registration fix; it does not qualify
continuous SM5440 temperature/OCP or authorize active direct charging.

Current, previous and photo-boot full kernel JSON bytes are retained in lossless
gzip, preserving source timestamps. Filtered history is only a lookup. The old
`/tmp` known-host file was missing; a fresh public host key obtained through
ADB was used for strict Wi-Fi SSH, confirming the same boot/machine. No device
configuration, mode, register, flash, reboot, PPS or pump action was made.
Tests/build executed:false for evidence only; no new regression claim. Full
charging port NOT READY. Next remains an independently qualified OFF continuous
ADC timing diagnostic, not replay of the frozen one-shot experiment.
