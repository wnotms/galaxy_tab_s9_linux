# ECC candidate capacity and validation limits

The kernel Image.gz equals the earlier unmodified production rebuild byte for
byte. The decoded DTB differs only by ramoops ecc-size=64; config and release
match production. No diagnostic C code was added in this candidate.

Pinned ram_core.c allocates parity inside each existing zone. The 1 MiB PMSG
zone has 698,996 usable bytes; the 512 KiB console zone has 349,428. Reserving
128 KiB for crash messages leaves 218,356 console bytes. This still fits the
6,245-byte test-230 manual snapshot, but does not validate automatic capture,
console traffic margin or full-event trace coverage. Default ECC=0 capacity
calculations remain unchanged for production builds.

Source boot 059c1400-1ccf-4861-9590-1fe2592611b7 reports six uncorrectable header
messages while reading incompatible old ECC=0 regions. Those belong to layout
transition, before this trial writes its fresh known payload. They cannot be
used either to pass or to fail the later same-layout retention trial. The
observer record must carry its own correction result and exact identified data.
