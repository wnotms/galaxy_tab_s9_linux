# ADC completion context — read-only investigation

Actual first observation stopped before all register reads: requested ecaa3c64
boot was replaced by5e039c8f-c138-47d2-9629-3a07ae6162ff. Accepted311 embedded
config/notes match, but lpcharge=1 and1%/3.409V/29.2C/net−239mA PC SDP500mA.
No agent reboot command was sent. Manual/automatic restart attribution is unknown;
owner was asked. No flash, recovery, register write, ADC request, PPS or pump ON.
Physical mask values therefore **remain UNKNOWN**; no inferred masked-READY cause.

Vendor MSK1..4 C0/F7/18/F8 initialization is directly sourced and hashed.
READY timeout evidence318/321 lacks these masks. A different mask is a hypothesis,
not a demonstrated root cause or permission for a speculative register write.
Vendor200ms one-shot worker and Fedora continuous raw reads do not prove100ms
freshness/calibration/OCP. No deadline, READY requirement or calibration changed.

Prior kernel1131 rows exactly matches the preceding saved reconnect capture.
New kernel1080 and prior complete system2095 rows retained losslessly,
with journal source timestamps/commands. No detected new CPU-stall/panic/Oops
signature, but known MDSS/SMMU faults remain unresolved and no general clean result
is claimed. Late shutdown.target belongs to user@0.service/PID2614, not system
PID1 shutdown: do not misattribute it as a clean system reboot or battery poweroff.

New single-command read-only collector seals expected boot/config/notes, rejects
lpcharge/running pump/wrong chip/range/malformed output/drift, requests exact ordinary
register lines, and preserves cached telemetry as cached. No INT/read-to-clear,
write, new ADC or recovery operation. Every qualification/ON flag remainsfalse.
Host actual filesystem/generated-device-program/transport tests:
12 PASS/0.029s/zero skips. Full/buildexecuted:false; kernel/DT/
configuration/profiles are unchanged. No Actions or routing change.

Next recover battery on accepted18W C2 and confirm normal startup/owner attribution;
use one normal read-only context capture, then choose the next source-backed OFF
experiment from actual mask evidence. No automatic reboot, candidate deployment,
READY waiver or repetition of an unchanged failed profile. Full port NOTREADY.
