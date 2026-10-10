# Standard PDR listener observation: host qualified, not deployed

Test392's fresh-client unregister was rejected with result1/error9 and no state.
The new independent helper uses the actual Linux7.2-rc3 PDR lifecycle to obtain
an initial state: register enable=1, optionally ACK valid state indications,
unregister enable=0 on the same private client, close. Method0x24 restart-PD is
not implemented; neither RPC nor remoteproc nor charging/USB is controlled.
The original observer, Test391/Test392 evidence and tests remain unchanged.

`PRIMARY.json` pins the inspected actual kernel schema. REGISTER0x20 has the
enable/path fields and optional response state; indication0x22 has state/path/
u16 transaction; ACK0x23 echoes the **body** transaction and exact path. It does
not echo the unrelated QMI indication header transaction. Linux sends ACK after
its clients release PD resources and does not wait for its response. This
read-only client owns no PD resources; it ACKs promptly after validating a
same-peer/exact-domain indication, then additionally verifies the ACK response.
That stricter verification is an observer choice, not a Linux requirement.

Registration has an absolute2s deadline. Cleanup gets a separately reserved2s
even after a lost register response; send/unregister happens once, no retries.
Late register replies cannot repair a failed initial observation. Known initial
state, register acknowledgement, verified unregister/ACKs, same boot and socket
closure are all required for completeness. Boot change prevents further sends
against a new boot. Unknown initial state stays unknown despite cleanup.
Packet/indication bounds prevent an endless notification stream. Raw outgoing
and incoming packets are retained, including the first fault. Pending queued
valid indications are drained/ACKed within the cleanup deadline.

Server support for same-client unregister remains **hardware-unverified**.
Socket closure does not substitute for an acknowledged remote unregister.
Unknown cleanup stops the physical scope and requires baseline restoration.
The result labels only the register response's initial state; indication states
remain separately recorded. UP is not SSC publication, sample or rotation proof.

36 new lifecycle/wire cases plus30 prior state and20 domain cases PASS, zero
skips. Fixtures cover exact literal request/response/indication bytes, event
interleaving, ACK tokens/order, missing state, actual error9, timeout/late reply,
foreign domain/peer, malformed/duplicate events, packet bounds, boot change,
send/bind/close faults and cleanup. Tests use host socket mocks; they are not
firmware validation. No kernel build/full regression/Actions or device query.

Next register/push one separate physical Test393 before mutation: the same
early-ADSP baseline, at most two complete private-client listener cycles around
one ordered RPC start/30s observation. Missing initial state or unverified
cleanup stops before RPC. Always restore exact Test370 and GNOME. Do not replay
Test392's failed fresh-client unregister or mix unrelated userspace repairs.
