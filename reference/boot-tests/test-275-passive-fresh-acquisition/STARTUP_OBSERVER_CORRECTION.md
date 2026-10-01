# Preserved startup observer STOP; no physical retry

One candidate boot e7018be8b5254796a7512aefe531f27e reached healthy272config/notes,
Sink/Device/SDP500mA, passive fault0/OFF/current0, no failed units. Full journal
shows the unchanged driver's retained0x80 startup branch: waiting0.290698s,
rawfault0.290722s, confirmedinactive2.598256s (2.307534s), rawVBAT4.0565V/
VBUS4.881V/IBUS0/die27°C/OFF01/01/protectionf2/e7/37/fe. The existing kernel
classifier executed its two new safe confirmations within unchanged5s; raw
startup event remains visible, not erased. Current sample fault0 and startup
pending0. This differs from stopped/fullpack Test267 and does not replace it.

The host's extra substring gate classified every `fault bitmap=` line as a live
fault, overlooking that already-qualified kernel branch. Original stop/fullraw
preserved in candidate-boot. No observer load or request occurred. Correct only
host attribution: exactly one priority4 early0x80 matching OFF/protection/rawADC
with one waiting+priority6completion, confirmation<=5s, raw safe bounds and fresh
healthy snapshot. Missing/late/repeated/different/unsafe/live events still fail;
incremental journal faults never get this startup classification. No driver,
deadline, register, latch, averaging, current or startup voltage boundary changed.
The source log confirms driver's software branch, not independent ADC calibration.

DHCP assigned10.125.29.252 after this normal boot; old address77 was preflight
only. Read unique current wlp1s0 IPv4 from authenticated ADB then prove same boot
over authenticated SSH. No old-IP retry/network configuration change.

Affected host cases cover the exact branch plus missing/late/otherbit/voltage/
mode/protection/raw/repeat/ADCerror/incremental/CPUfault and DHCP ambiguity.
Push this correction before the single observer load in same boot; no repeat
boot/flash/physical window. Keep original registration and installation seals
against their recorded commits. All kernel/observer/full qualifications reused.
