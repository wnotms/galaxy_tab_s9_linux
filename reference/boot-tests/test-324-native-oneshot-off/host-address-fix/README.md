# Post-series host address enrollment correction

Physical Test324 and its matched rollback used the original runner committed at
0725c5fa, whose registration INPUTS.json is preserved unchanged. This host-only
correction was applied after restoration and authorizes no further Test324 run.
Candidate Wi-Fi addresses are now authenticated against enrolled SSH trust and
exact candidate identity before atomically publishing the address. Refused,
partial or mismatched responses preserve preflight metadata; stopped series
cannot probe/update. No kernel/device configuration changes or repeated physical
observation. Six actual-function tests plus nine existing parser/lifecycle tests
are executed locally; original Wi-Fi stop remains a stop.
