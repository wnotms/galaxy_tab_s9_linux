# Test391 — sensor PD readiness boundary

Test390's corrected missing-file status was acknowledged but SSC400/sample
remained absent. This attempt adds a previously unobserved boundary: whether
`msm/adsp/sensor_pd` is UP before and after one ordered RPC startup. It is an
observation, not another claim that the unchanged status69 repair fixes sensors.

Reuse the exact Test390 kernel/config/DTB/181 modules, Test382 early vendor,
firmware/native mapper, isolated stock assets and corrected RPC daemon/library.
Only the private-client notifier tool is new. Do not mix separately qualified
libssc wait/proxy changes, change registry selectors or add firmware blobs.
The eight temporary text/RPC/GLINK overlay files use the new Test391 namespace.

One candidate boot, maximum two method0x20 enable=0 requests, each with a2s
absolute bound, using fresh complete same-boot QRTR and native domain inventory.
See `reference/desktop-bringup/ssc-pdr-state/RESULTS.md` for source/semantics:
this unregisters only a newly created client, it is not GET_STATE. The firmware
may omit state. Unknown/malformed/rejected initial response stops before RPC;
no enable=1, ACK, restart, listener retry or second startup. Valid initial state
permits one root→sensor RPC start and30s health observation, then one new client
query. LOCATOR_ERROR stops. UP never substitutes for SSC/sample acceptance.
Only when SSC400 is actually advertised, make one bounded accelerometer probe.

Essential gates: ADB root/rescue, exact five partitions/181 modules/config/notes,
unique attributed boot, no new kernel fault/failed unit/Code43, battery20–100%,
10–42°C, VBAT3.4–4.45V. Three bounded TWRP samples before transfer. Kernel,
charging, USB, native input, DCC and firmware remain unchanged. PPS/pump OFF.
Full journals at boundaries; no long per-sample rehash or host NCM/SSH wait.

Any first unknown/fault stops; preserve raw state packets and journals. Always
restore exact Test370 vendor, owned assets/overlay and normal GNOME. No sensor
PASS or rotation claim from a successful state query. No physical retry.

Register, qualify affected host tests and push origin/test before mutation.
Reuse unchanged build/tests; no kernel rebuild/full regression/Actions.
Retention382–391. Next action follows the first actual domain state evidence.

## Admission revision2: historical EP0 row

Initial read-only enrollment stopped on one added priority3 DWC3 ep0out dequeue
rejection at uptime102.348212s of the restored Test370 boot. No device mutation
occurred; incomplete draft input hashes also rejected stage/preflight before
staging or further device checks. Original journal/STOP are retained.

The pinned no-list `dwc3_gadget_ep_dequeue` branch returns-EINVAL; it does not
itself restart hardware. The triggering caller remains unknown. This is not a
claim of harmlessness or a USB fix. A later same-boot root ADB shell, configured
device NCM, healthy services and Windows noCode43 were observed. Full journal
comparison found no later severe error or CPU signature. `ENROLLMENT.json`
enrolls only this exact historical row/cursor, following Test387's prior method.
Any subsequent error at a new cursor still stops; no future error waiver or
change to the health guard. Stage/preflight must pass again before deployment.
