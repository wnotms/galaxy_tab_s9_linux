# Owner changes the post-test endpoint

Owner: “后续不要求停在twrp，继续推进”. This supersedes only the prior
instruction to stay in TWRP. It does not grant a second Test348 pump attempt,
change the 1.8 A stop ceiling, or turn the non-clean observation into a pass.

Exact Test331 boot and all 181 original modules have been restored and all
five partitions verified, as recorded in `rollback-install/summary.json`.
After this registration is committed/pushed, issue one ordinary recovery
`adb reboot`, then attribute the restored Debian boot and verify baseline
config/notes, DCC absence, rescue transports and battery/kernel health.
No charging opt-in, firmware/service change or new pump activation is included.
The frozen Test348 runner and original registration remain unchanged.
