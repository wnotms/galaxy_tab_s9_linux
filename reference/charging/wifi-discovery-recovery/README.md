# Bounded enrolled WiFi discovery recovery

## Problem and scope

Test334 stopped after its host0.4s TCP/254 concurrent-/24 scan found no SSH
endpoint in90s, although ADB later preserved a valid native fixed-return proof.
The prior cause is not uniquely established. Native1s known-IP TCP also timed
out once after restoration; a subsequent3s probe connected. Keep the original
334 STOP and valid native proof, not rewrite that series or repeat its kernel
one-shot. Device remains accepted331 defaultOFF.

This independent host helper changes no kernel/config/DTS/USB/ADB/charging/
rootfs/transport configuration. It does not flash/reboot/change host keys.
No PPS/current progression. Main API is scripts/charging_wifi_discovery.py.

## Design

Recent enrolledIP is authenticated directly, so a short rawTCP false negative
cannot veto it. Otherwise scan only its RFC1918 private-/24 host addresses,
TCP22 only,16 TCP workers,3s connect bound, at most2 SSH identities in flight.
At most2 passes, shared90s deadline includes identification. Strict enrolled
ed25519 alias/file, unchanged enrollment hash, machineID, exact embeddedconfig/
notes and optional expectedboot must match. No accept-new/hostkey learning,
public/linklocal/loopback/IPv6 scan, passwords or extra network scope. Returned
bootID is evidence; downstream must still gate unique boot history/current
pack/pump/faults. This helper alone never authorizes charging acquisition.

Every TCP/SSH start/result/cancellation and overall match/stop/drain is JSONL.
Raw SSH identity stdout/stderr and argv are preserved; private key contents are
never read into logs. A match cancels remaining work; deadline/error drains
pending TCP/SSH children before return. Child cleanup can take up to0.5s after
the90s attempt deadline; no new probe/accepted match after that deadline.
CLI refuses an existing evidence directory rather than overwriting it.

## Qualification and planned read-only device check

23 affected mock tests PASS0.112s, including knownIP withoutTCPprefilter, changed
IP/unknown neighbor, key rejection/identity drift, strict file permissions and
trust-change rejection, subnet/worker/deadline bounds, cancelled children and
closed sockets. No routing/build integration change, full host run/build/Actions
not executed. Legacy frozen333/334 runners and all historical tests remain intact.

After this host qualification is committed/pushed: read current identity once
via ADB, require accepted331 config51ba6a9c/notes03c9c46e/directOFF/currentboot,
then invoke new helper with recorded previousIP10.139.153.19 and the freshly
read expected machine/config/notes/boot. This intentionally exercises the DHCP
address-change path against the current baseline. Only read-only identity SSH
commands and bounded TCP22 probes, no charger/reboot/flash/test replay.
Store all bootstrap/events/summary. A failed helper stops; do not change router,
WiFi/sysfs/systemd/charger configuration or lengthen deadline automatically.

Future charging registration must freeze this helper and qualify its own use;
current334 records are not edited to point at new code. Native fixed-return
already proven; continuous charger/PPS-transition questions remain independent.
