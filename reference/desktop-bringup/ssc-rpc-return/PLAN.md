# Bounded RPC return-frame observation after Test387

Test387 used the corrected Fedora0.4 codec, two ordered RPC roles, exact stock
registry/assets and native mapper.35 config stat responses matched, but no SSC400
or sample appeared in60s. Existing verbose output precedes return encoding; it
cannot prove exact buffer framing/content or successful listener_next2 return.
This is the next unobserved boundary, not an SSC rootcause claim.

Prepare a separate hash-qualified profile over unchanged wire+stat sources.
Change only listener.c and add a bounded trace helper header. Explicit environment
opt-in, disabled by default; no changes to callback results, file data, wire
encoding, library/API, ioctl arguments, registry, firmware, kernel or hardware.
Record encoded TX, successful/failed next2 return and complete incoming frame
with sequence/context/handle/scalars. next2 success is a host transport boundary,
not proof of DSP application parsing. A final blocked next2 remains pending.
Cap each frame at8192B and total records at512KiB per daemon; emit an explicit
limit/error marker rather than silently truncate or alter runtime. Two daemons
plus existing verbose output must fit the existing2MiB bounded journal budget.
A qualified physical registration must stop on limit/malformed/missing evidence.

Compile the real modified listener+codec in native C harnesses with substituted
fastrpc2 only (no hardware), verify unchanged response bytes, complete fragmented
input, empty buffers, transport failure and default disabled behavior. Exercise
limits, strict independent framing/sequence parser and corrupt source admission.
Build ARM64 using the pinned networkless Debian builder, same library and sources;
reuse the exact kernel/config/DTB/181-module qualification. No Actions/full tests
unless actual routing/integration changes require them.

This offline preparation does not execute a device test or authorize an unchanged
Test387 retry. A later independent Test388 must register the changed observation,
one ordered root/sensor startup, bounded60s capture and exact Test370/GNOME
restoration before installation. No DIAG masks, registry reset, selectors guessed,
PPS/pump, kernel/module/USB/input/charging mutation or repeated RPC restart.
