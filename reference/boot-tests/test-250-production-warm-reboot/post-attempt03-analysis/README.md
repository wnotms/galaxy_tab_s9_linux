# Offline follow-up to Test250 attempt 03: QCA baudrate event

This analysis adds no registration, reboot, kernel patch or runtime change.
Attempt 03 stays stopped with zero clean rounds. The sealed original and both
later attempts remain unchanged. Do not use this note as permission to resume.

## New primary-source evidence

The pinned `hci_qca.c:qca_set_baudrate()` encodes opcode `0xfc48` as bytes
`0x48, 0xFC` inside `{ 0x01, 0x48, 0xFC, 0x01, 0x00 }`. The final byte selects
the baudrate. It queues directly to QCA UART TX, outside the ordinary synchronous
HCI command path. Earlier literal-opcode searches missed this byte-array form;
the attempt-03 note that the opcode was not found is superseded on this point.
Source excerpts and the unchanged full-source SHA-256 are recorded here.

The installed pin's `qca_set_speed()` arms `QCA_DROP_VENDOR_EVENT` only for
WCN3990, and `qca_recv_event()` handles its vendor event; WCN6855 lacks that
specific guard. This is a source comparison, not a changed driver.

Qualcomm's author describes baudrate-change responses being confused with a
subsequent HCI command for WCN6750/WCN6855/WCN7850 and proposes handling their
command-complete event in the UART driver. This is a proposed upstream change,
not evidence it is installed on this tablet. See the
[2024-08-21 primary patch](https://www.spinics.net/lists/linux-bluetooth/msg114463.html).
The author's
[primary discussion](https://lkml.rescloud.iu.edu/2408.2/06106.html)
says speed switching itself worked while response handling was incomplete.
The referenced vendor application note was not obtained; no claim relies on
having read it. No patch from the discussion is applied.

On this production boot the single priority-3 event occurred at kernel source
time **8.365905 s**. The same controller reported successful UART setup at
**9.174012 s**, **0.808107 s** later. Post-stop reads found Bluetooth powered,
both units active, no failed unit and ADB/NCM/SSH available. Raw source-time
journal hashes tie the derived timing to boot
`830da717-5e6d-40be-8390-7398b55ff2e2`.

Taken together, these observations support the known QCA baudrate-response
handling issue as a concrete explanation to investigate. They do not prove
actual HCI packet ordering on this boot, general Bluetooth reliability, or a
CPU-stall cause. No packet trace was recorded. The absence of the message from
accepted Test249 captures remains true; historical Test241/Test247 occurrences
do not replace the accepted production baseline.

## Concrete decision needed before a later series

The current stop rule still treats this event as suspect. A possible future
**host-only** classification could count one exact `hci0`/`0xfc48`, priority-3
startup event by 20 s only when WCN6855 setup succeeds within 5 s afterward and
the same boot's powered controller and Bluetooth services pass the final
150 s window. Extra events, a different opcode/controller, late event, missing
setup, another Bluetooth error or any existing CPU/identity/transport/evidence/
systemd fault would still stop. All 20 ordinary warm reboots and final full
Test249 integrity acceptance would remain required.

This proposal is **not implemented or approved**, does not amend any sealed
verdict and does not arm a new runner. It requires an explicit owner decision
before a new Test250 registration, local runner tests, push and fresh unchanged-
production preflight. No Test251 is created. The alternatives are to retain
this as suspect and keep physical testing stopped, or authorize precisely the
future host classification above without modifying production.
