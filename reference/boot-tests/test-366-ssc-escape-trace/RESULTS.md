# Test366 — stopped in read-only preflight, not deployed

The independently registered sensor/native Escape candidate was not flashed.
The existing accepted Test331 boot `78ec1906-4713-4837-9acc-fe245647d7cf`
contained two GMU HFI bandwidth-vote timeout/old-response pairs, at source
monotonic 2334.697683/2334.698339 and 2742.883401/2742.884168 seconds.
The complete 1171-row kernel journal and source timestamps are preserved in
`preflight-1791477083497247548/`. These are new priority-3 suspects; the
CPU-stall/panic classifier found no CPU fault signature. This is not proof
of a GPU root cause, a CPU wedge, or a harmless warning.

Read-only baseline kernel/config/notes, all five partition hashes, 181 module
hashes, ADB and authenticated Wi-Fi identity passed before the journal stop.
The actual preflight battery was 83%, 34.1°C, Good, VBAT 4.282 V, not the older
registration snapshot. SSH, adbd, NCM and GDM remained active; no failed units.
The history and Windows PnP stages following the journal gate were not executed;
do not call the entire preflight accepted. No active preflight was produced.

No flash, reboot, rootfs/input mapping change, module replacement, ADSP/SSC
start, PPS request or pump activation occurred. No rollback is necessary.
The first-failure marker prevents installing/retrying this stopped registration.
The native keyboard is compiled and included in the retained offline candidate,
but actual direct Escape/Fn+Escape, sensor discovery and rotation remain untested.
The user's interim desktop mapping and normal GNOME baseline remain in place.

All 38 owned Windows staging files were hash-verified, then removed to release
space; formal WSL candidate/rollback artifacts and Windows ADB tools are retained.
The original registered inputs and historical Test365 result are unchanged.
Result-only documentation validation: `executed: false`; the 73 affected host
PASS/0-skip from registration and earlier build are reused, not rerun or claimed
as hardware acceptance. No full regression, rebuild or GitHub Actions.

Next: analyze the first baseline GMU anomaly using the pinned Linux HFI path
and same-model Fedora source, without inventing a GPU fix or whitelisting it.
Then independently register the next physical scope, retaining native Escape,
exact paired inputs, bounded SSC trace and ordinary charging limits. Sensors
and the complete port remain unfinished; higher-power charging follows sensors.
