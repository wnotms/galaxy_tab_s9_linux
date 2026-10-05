# Current ordinary323 SM5440 context — read-only

After successful PC charging acceptance, one0.147s bounded sameboot/config/notes
capture; no ADC start/adoption/read-to-clearINT/register-data write/PPS/pump.
Provider ordinary323,fca646a8..., config31d5a941..., notesd8e5fcf3..., ID0x21,
MODE0x01 before/after (pumpOFF). Actual MSK1..4 all0x00; ADCCNTL1=0x0c,
ADCCNTL2=0xdf. Vendor audited initializationC0/F7/18/F8 therefore differs.

This fills the previously missing current ordinary mask comparison. It does
not prove Test318/321 timeout root cause, previous boots' masks, conversion
freshness/calibration/OCP, or permission to writevendorF8. Current normal poller
and read-to-clear ownership must be included in next source-backed comparison.
Cached telemetry is labelled cached; no fresh ADCexperiment. Prior failed318/321
and previous identity refusal remain unchanged. Reuse unchanged script12hosttests;
this result only: new tests/build executed:false. FullportNOTREADY.
