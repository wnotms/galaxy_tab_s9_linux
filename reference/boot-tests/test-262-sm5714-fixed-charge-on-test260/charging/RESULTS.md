# Attempt01: host parser stopped before charger attachment

Initial sameboot/health/kernel/startup gates passed and the collector printed
ARMED. The first incremental sample then raised KeyError `failed`: splitting
at the journal separator removed the newline after an empty `@@failed` marker,
so the parser requiring a terminating newline did not recognize that section.

No charger-connection prompt was sent, no charger observation started, no
charging sample was accepted, and no device configuration/reboot/flash action
occurred. The generated STOP summary, initial capture, first sample and complete
first-failure journal are retained unchanged. This is a host evidence parser
failure, not a measured charging failure or a CPU fault.

A narrow EOF-marker parsing correction is qualified with four exact saved-capture
replays: empty EOF, empty newline, missing section (still fails closed), and an
actual failed-unit line (still stops). Forty-four affected tests and syntax pass.
Fresh attempt02 starts in a separate directory with identical hardware/software
and limits; no old evidence or stopped result is relabeled clean.
