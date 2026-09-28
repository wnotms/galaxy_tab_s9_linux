# Local/preflight acceptance

Three isolated host-server lifecycle tests passed, including early failure
and rejection of device-command arguments. Final full host regression passed
1091 tests (85.040s), zero failures/errors/skips; report host-tests-all.json.
Shell syntax/whitespace checks pass. No device kernel build occurred.

Exact unchanged Test252/installed Test253 same-boot preflight passed: five
partition hashes, config/notes/181 candidate/181 original module hashes and
DCC/profile, no kernel fault or failed unit, source-bound NCM and Wi-Fi SSH,
no Code43, unchanged protected NCM/SSH files. Native serial is absent in the
host device table, the specific recovery target. Additional absent-target-daemon
capture verifies PID834, custom path and exact binary SHA. The observer now
requires that capture whenever --native-absent is used. No host server/device
service restart has yet occurred in attempt03. Do not interpret preflight as
native USB acceptance. This is an independent host recovery; attempt02 stopped.
