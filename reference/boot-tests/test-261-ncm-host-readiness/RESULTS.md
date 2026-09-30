# Test261 outcome: host readiness entry verified on unchanged Test255

Source/registration `3ecf2093` was pushed before the one read-only device check.
Owner requested NCM repair without flashing. The new entry fills the missing
Windows/WSL readiness gate and binds SSH to the verified NCM source address.
It does not change a USB driver or claim the old timeout's cause is proven.

Current check passes on boot `cfb09d0136a64f9b9d5e1ad0e2fd9c45`:

| Evidence | Result |
| --- | --- |
| ADB initial identity | Same accepted Test255 boot; uptime 15858.75s |
| Windows production NIC | UsbNcm Host Device #3, ifIndex9, Up |
| Windows APIPA | 169.254.74.160/16, Preferred |
| Windows Code43 | None in captured snapshot |
| WSL route/address | Direct eth2 route to 169.254.42.1, source 169.254.74.160 |
| Readiness capture | First sample ready, 13.883s metadata time; no observed unready state |
| Source-bound NCM SSH | One attempt, status0; 0.830397s process duration |
| Authenticated boot ID | Matches ADB; uptime15873.46s |
| Device configuration changes | None |

The 13.883s measures host metadata collection, not a measured APIPA recovery
delay. Windows and WSL raw topology, SSH argv/source binding, stdout/stderr and
UTC command timings are retained under `current-transport/`. No extra successful
banner/SSH probe, unplug or reboot was needed. Failed-case diagnostics are not
executed on a pass.

Host qualification: 109 affected tests pass in1.041s, zero failures/errors/skips
(29 new readiness tests, existing passive admission and production transport
coverage). Python compilation, all required shell syntax checks and diff checks
pass. No routing edit, kernel/build/config/DTS/driver/rootfs/adbd change. No
rebuild or repeated full host run: Test260 kernel qualification remains unchanged
and hardware acceptance pending. See `validation/host-tests.json` and summary.

Historical Test259 attempt02 remains STOP: its first SSH started at
04:16:21.474578UTC, after ADB reported uptime8.26s at04:16:20.366569–20.480474UTC,
approximately9.3s after boot. SSH timed out after10.023s. That boot lacks an
initial Windows APIPA/WSL route snapshot; later tablet-side usb0/sshd state does
not prove the host path was initially ready. APIPA/mirroring timing is a possible
explanation, not an established root cause. Source0x80 remains a separate
retained hardware finding, not cleared by this host result.

New entry is explicit for future registrations; old `gts9-ssh.sh`, passive
admission and wedge runners retain their first-failure semantics. Unready metadata
may wait within the registered budget and is retained; first SSH failure never
retries. A strict series must decide delayed-readiness classification in advance.

Bounded current-path verification only: no cold/warm boot or physical reconnect
coverage and no proof the historical startup timeout is eliminated. Tablet stays
on Test255. No flash/reboot/partition/module/rootfs/USB/network-setting/PPS/pump
action occurred. Further startup observations need separate registration and
authorization; Test260 must not be deployed by this host-only workflow.
