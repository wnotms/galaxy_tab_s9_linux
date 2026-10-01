# Same-attach source observer correction

Original source/ STOP/fixed PD unavailable/zero-window is retained. Device initial
state was healthy fixed9V/1500mA/ONLINE=1, actualSM5714input1500mA, pack29.9°C,
SM5440Good/fault0/OFF/IBUS0/physical cachedVBUS9.136V. Not an active PPS failure.

Pinned TCPM tcpm_pd_select_pdo sets USB_TYPE=PD_PPS when pps_data.supported,
regardless of pps_data.active. tcpm_psy_get_online uses FIXED=1/PPS=2/AVS=3.
Correct the host protocol check to ONLINE=1; actual voltage/current/SM5714USBtype/
thermal/OFF gates remain. ActiveONLINE2/3 are explicitly rejected. Do not modify
TCPM, kernel or device. Generic source-capabilities/power/ sysfs directory is not
PDO; exact counted TCPM frame/currentpartner comparison remains mandatory.

First new C1 TCPM ring was archived once in source-diagnosis (sameboot prefix):
6 objects, fixed5/9/12/15/20V plus PPS5-11V/3A. ActualRequest PDO1 (zero-based)
was fixed9V1500mA, not Requesting APDO. Do not infer physical draw from capabilities.

Fresh source-completion namespace uses that first archived ring plus unread tail,
requires unchanged current source/boot, refuses actual reset/detach/new faults,
and observes30s on this same physical attach. This supplements missing observation;
no reattach/retry/reboot/flash/PPS/pumpON/current increase. Original STOP is not
rewritten CLEAN. Owner device-normal completion criterion applies. Parser31 and
collector18 affected tests/syntax pass, build/full executed:false/reuse unchanged272.
Historical SOURCE_OBSERVER_SHA256 verified againste019d1b3. Code before this fix
archived in observer-before-capability-fix; active hashes in CAPABILITY_OBSERVER_SHA256.
