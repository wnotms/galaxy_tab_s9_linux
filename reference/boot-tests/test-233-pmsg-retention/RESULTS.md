# Test 233: binary pmsg retention is corrupt too

Source a80804be-229c-46f7-aae8-bd797fb22883 wrote capture
0a09ff25-7436-4162-9194-230fd9bffc54: 33,005 bytes, SHA-256
10e2928aea9b2b0f7e924501a0fada746dc6b6298a46e241076914e4548ff625.
The staged device file matched before the successful /dev/pmsg0 write.
Normal systemctl reboot went directly to observer
 a8bab63e-525e-477a-9590-0d00be9d8fb1, the next retained journal boot.
No partitions, watchdogs, kernel/config/DTS or userspace services were changed.

The newly archived pmsg-ramoops-0 has the exact header, footer/length, but
**464 changed bytes / 542 changed bits**. Its SHA-256 is
69547878f8547d8c96ae97e69670ff2b0951234fbf6ec9f06ffbd493e2d705f5.
Device hash, tar/base64 transfer and two independent repeat reads all agree.
There are 483 one-to-zero and 59 zero-to-one bit changes. The worst aligned
128-byte payload block contains 18 changed bytes. Alignment is relative to
this known payload; it does not predict a future ECC correction guarantee.
The console/dmesg files remained stale with their previous hashes.

This extends test-231's console corruption to raw binary pmsg; it is not a
text-decoder problem. It does not establish DRAM voltage, a CPU root cause,
or the stage that changed the bits. pmsg is write-only: successful write and
staged-file hash do not prove the persistent RAM itself was correct before
reboot. That missing observation is the next discriminating measurement.

Next prepare an opt-in read-only live pmsg RAM view, with writers quiesced and
two matching reads before reset. ECC may be tested separately within the same
reservation, but must not turn an unverified record into accepted CPU evidence.
No wedge series is ready. The observer stayed responsive beyond 150 seconds,
with no failed units; raw closing health is archived. Final device remains in
Debian with both ADB transports and NCM available.

Four focused integrity tests, individual shell syntax checks and the required
ccache production build passed. The build was not flashed.
