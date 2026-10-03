# Test317 current status

Candidate installed/read back once in freshly validated native TWRP. All five
partitions match the registered candidate layout; only boot changed. Exact181
paired modules installed, BCB cleared and Debian root unmounted. No candidate
reboot was issued: owner must attach Lenovo C2 18W before tapping Reboot System.

Rollback is still required. Candidate capture NOT EXECUTED; no hardware pass,
PPS/pump enable, current increase or ADC calibration/freshness grant. Continue
with `host_flow.py capture` after owner confirmation, preserve first refusal,
then reconnect PC and `host_flow.py restore` regardless of capture outcome.
If unreachable, manually enter TWRP and use `restore --from-recovery`; preserve
missing failed boot attribution rather than inventing a clean result.

Host73 PASS/no skip and exact316 build reused. No new kernel/full/Actions run.
Preflight authenticated Wi-Fi was10.139.153.84, pack28%/3.77V/31.7C.
Known passive startup confirmation refusal on accepted311 remains recorded.
HostNCM255 is separate; baseline deviceusb0/services/WindowsCode0 were normal.

Full charging port remains NOT READY. Fixed9 diagnostic is one bounded next
step; real ADC/protection/OCP/watchdog/ON/PPS/fallback/PM acceptance remains.
