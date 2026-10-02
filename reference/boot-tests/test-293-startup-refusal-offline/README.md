# Test293 — offline passive startup refusal attribution

Purpose: explain the first Test292 final-baseline monitor failure from preserved
bytes and immutable Test263 C code, without a new device round or altered gate.
No device command, kernel/config/DT/ADC/current/USB/rootfs change, build or PPS.
Design: strict cached-profile/raw ADC/fault checks, exact boot/config/notes and
source-timestamp correlation, then explain every unchanged startup predicate.
The output is a diagnostic explanation and can never grant charging/admission.

Inputs are referenced and hashed in INPUTS.json; original raw journal/snapshot
and Test292 refusal remain untouched. The source oracle is immutable Test263
commit ea938b245bff3ae9e3c1828751ea149a90337992. Tests compile its actual struct,
header and startup functions; they do not lock future driver source to old text.
At this review the two current predicate functions are byte-identical, recorded
in summary.json. New records do not duplicate the full historical raw journal.

Run the parser using identity.json, the three recorded Test292/config paths and
an unused --output filename. It refuses mismatched bytes/boot/config/notes,
missing/duplicate transitions, unrelated refusal profiles, unexcluded deadline/
wrap, conflicting uevent fields and inconsistent ADC/fault decoding. Identical
POWER_SUPPLY_TYPE repetition is a real Linux uevent occurrence, not corruption.
