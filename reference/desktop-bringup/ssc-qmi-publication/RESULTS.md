# SSC publication prerequisite — bounded original-firmware evidence

Test399 directly observed native ADSP SMP2P negotiation and complete GLINK
opening, while SSC400 remained unpublished. This narrows the next question
to firmware initialization/service publication; it does not prove every DSP
provider or internal dependency healthy.

Four additional bounded spans were decoded from the same hash-qualified,
original-flag segment18 wrapper. Addresses are ELF virtual addresses for
offline analysis, not targets for physical memory access. Original firmware
was neither patched nor executed. No symbol names were reconstructed.

* At b32f89e8–b32f8a2c, the code calls the same lookup/predicate function with
  the exact strings `resampler` (b337a3d0), then `sim` (b337b428) if the first
  predicate is false. A true predicate reaches the existing context flag check
  and the call to b32f8424. These are internal named-dependency checks, not
  proof that either dependency is absent on the running DSP.
* At b32f8424, the function supplies 0x40 to the same signal helper. The earlier
  qualified thread span tests bit6, then calls b32fc4f8 before the QMI error
  branch. This provides a concrete connection to the publication trigger;
  the earlier suggestion that bit6 might be registry completion is unsupported.
* At b32fc4f8–b32fc580, the called function obtains an object using arguments
  1/4/6 and supplies it with three callback addresses to b32cf5c4. No runtime
  return value or registration failure was observed.
* At b3238a2c–b3238a4c, the getter checks those three exact arguments and returns
  b33e0d58 or NULL. MDT mapping places that object in **segment19**, not18.
  Its little-endian word at offset8 is400. Raw40 bytes and the mapping are
  recorded; without an original type symbol, this is not a full recovered
  service-object schema or evidence of a successful registration.

All35 config metadata,178 returned registry groups and220 initialized directory
replies in399 prove the APPS callback results, not completion of the firmware's
resampler/sim dependency discovery. There is no justification for an arbitrary
RPC trigger, forced signal bit, firmware instruction patch, sensor bus probe or
registry reset. Next compare the same-model Fedora firmware and initialization
inputs before deciding on one separately registered changed-profile boot.

Reproduce the qualified wrapper using
`../ssc-smp2p-initialization/REPRODUCE.md`, then run the four `commands` in
SOURCE.json. Preserve the source archive and manifest hashes; do not substitute
a similarly named firmware file. The segment19 object bytes are obtained from
the original MDT program-header mapping and unchanged `adsp.b19`, not guessed
from a segment18 offset. Generated wrapper/exploration output was removed after
the bounded evidence was retained.

Host tests/build/new physical test: executed:false, source-evidence only.
No device commands, reboot, firmware/rootfs/kernel/DT/modules/charging/input
change or Actions. Normal Test370 GNOME endpoint from399 remains the last
accepted device state. Sensors/sample/rotation remain unfinished.
