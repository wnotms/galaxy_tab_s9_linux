# Test333 — charger-attached fixed-return OFF check

Workflow correction after Test332 never reached fixed9: install/readback while
PC-connected inTWRP, **remain inTWRP**. Owner disconnectsPC, attaches LenovoC2
18W/C1empty, selects Reboot→System once. No PC5 startup waiting window before
charger attach. Reuse exact48cc5d16 candidateboot3fe4adf1/notesff706409/config51/
DTB233a/181 module qualification; no source/build/power-policy change.

Source/native300s deadline, fixed9/1–1.5A/SOC20–<80/VBAT3.5–<4.3V/pack20–<38C,
OFF/knownADCchannelsdf/zero rawIBUS/three reads/≥100ms/range≤100mV/window
8.55–9.45V/source+lease+fresh proof remain. No reset/PPS/pumpON/current increase,
no retry. Native kernel gates own safe entry even before host attaches.

Preflight one allfive/181/Code0/ADB/deviceNCM/strictWiFi/thermal/healthyOFF/history;
fresh333 module slots,331 defaultOFF rollback and331-original323 secondary.
Register/test/push before one pairedinstall/BCBclear/unmount. Owner boots only
with C2 attached; do not manually power-cycle repeatedly. Host discovery probes
TCP22 only within the freshly enrolled private /24, then strict-enrolled hostkey,
machine-ID/config/notes binds the unique candidate. It never authenticates an
unknown hostkey or widens scanning. WiFi admissionmax90s after owner confirmation.
A new/unexplained boot, identity/source/temperature/pump/ADC/proof/I2C fault or
missing rescue/evidence stops. No timer reset/offset/threshold change.

Reuse corrected Test332 read-only observer, strict actual enrollment path,
word-boundary CPU fault pattern (ramoops is not Oops), complete source-timestamp
kernel JSON and unique proof/complete events; observe≥30s after admission and
proof receipt. This validates fixed-return with source alreadyfixed9, **not** a
PPS-to-fixed voltage transition, ADC calibration or high power. Capture the
actual early proof even if emitted before WiFi admission, preserving timestamps.
No ADB/PC enumeration requirement during charger-only boot; those were accepted
at current332PC startup and returnPC/restore remains mandatory.

After PASS or first refusal, owner disconnectscharger and returnsPC. Restore
exactTest331 OFF boot/paired181/allfive/BCBclear/normalstartup; no retained check
flag, no PPS/pump/current progression. If rescue lost askmanualTWRP, never blind
write an unknown layout. No Test332 replay or repeatedbuild/fulltest/Actions.
