# RPC return observer correction — qualified offline, not deployed

Test388 raw capture exposed two observer defects, preserved in its immutable
STOP result. The incoming listener2 frame contains packed input buffers followed
by one unaligned uint32 output capacity per output buffer. The former parser
incorrectly required the input buffers alone to consume the entire RX frame.
Qualcomm primary source `listener_buf.h` blobee95b1d7 defines `pack_in_bufs` and
`pack_out_lens`; the4192-byte licensed source is retained with URL/hash. All701
actual RX frames satisfy this layout, without ignoring arbitrary trailing bytes.

The corrected parser records capacities in both request/response attribution,
requires the exact descriptor count, and retains strict output-frame validation.
Native and ARM64 harnesses now exercise complete RX frames including capacities;
the actual device first frame is a separate golden fixture. No listener callback,
encoder, file policy, fastrpc2 arguments, kernel or hardware state changed.

Replay of the existing raw journal in this new namespace recovers701 calls and
130 closed/transport-acknowledged registry sessions, all matching exact stock
content hashes.48 expected nonempty groups are missing after the capacity stop.
The replay remains complete:false with the original observer limit fault; it
does not turn Test388 into PASS or prove DSP parsing, SSC publication or rotation.
Original Test388 parser outputs/raw journal/results are unchanged.

An independent `rpc-return-v2` profile raises only the explicit process logging
budget from512KiB to1MiB. Original v1 header/profile remain hash-identical and
default preparation still selects v1. V2 is explicitly selected; its prepared
source differs from v1 only in the trace header budget. Actual records consume
524052 bytes for701 calls/130 groups; returned512-byte read buffers are logged
in full, regardless of the smaller written prefix.1MiB provides bounded headroom
for178 groups; it is not an assertion that unknown future traffic will fit.
The8192-byte frame cap/default-OFF/explicit-limit behavior remain unchanged.

106 affected checks PASS,0skip:45 observer/profile/real-C/UBSan/framing/content
checks,24 wire dependencies,11 stat checks,26 existing runtime/overlay consumers.
Networkless pinned ARM64 build passes2 upstream and6 real-listener QEMU cases.
All56 compiled source hashes match; daemonbf0a9fa1, library1be44d2f unchanged.
Protected kernel/config/DTS/charging/keyboard hashes match. No new kernel build,
full regression, suite-routing change, Actions or device operation for this work.

Next independently register one complete bounded content observation with V2,
reuse exact370/382 artifacts and mandatory370/GNOME restoration. Do not replay
the old failed observer or reset registry/guess firmware selectors. PPS/pump/DCC
remain OFF. Sensor migration and automatic rotation remain unfinished.
