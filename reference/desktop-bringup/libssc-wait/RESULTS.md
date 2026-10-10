# libssc blocking wait — compiled, not deployed

The sensor goal remains incomplete: Test389 still has no SSC400 publication or
real accelerometer sample. Its seven returned initialization inputs match; that
does not prove firmware initialization. This change fixes a separate, reproducible
client defect before the sensor stack is made permanent. It is not an SSC repair.

## Source and change

Reuse the public SM8550 client fix from S9 Ultra commit
`32273b0a410b3e73b20a3a2451e24260fb2a36bd`,
[`fix-ssc-sync-wait-busy-loop.patch`](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/32273b0a410b3e73b20a3a2451e24260fb2a36bd/packaging/sensors/fix-ssc-sync-wait-busy-loop.patch).
The copy is byte-identical. Fresh upstream HEAD916e2f13 has the same patch;
the URL/hash/size check is retained in `UPSTREAM_CHECK.json`. X910 temperature
and current measurements in its patch header are reference-author observations,
not measurements of this X710.

Only `libssc 0.4.4/src/libssc-common.c` changes. The existing default-context wait
uses nonblocking iterations in a tight loop. The imported fix acquires the
context, blocks in its poll while dispatching other sources, and sleeps on the
existing condition variable if another thread owns the context.

A small additional patch wakes the default context when the existing completion
callback records its result. A condition signal alone cannot wake an owner
blocked in `g_main_context_iteration()`. The real GLib test reproduces that
case with an already-produced GAsyncResult completed on a foreign thread. The
reference-only build times out under the fixture's2s guard; the final build wakes
and returns. This is a tested helper/API scenario, not a newly observed device
QMI failure. No QMI timeout, completion result, public API or firmware protocol
is changed. Requests that never complete remain pending while consuming little
CPU; this patch does not invent a protocol deadline.

The new explicit profile pins all70 original source files and both patches.
Preparation rejects drift, links, extra files, overlaps and existing output.
Only one original source file may differ. Base `sources.json`, prepared Fedora
tree, historical daemon profiles and qualified Test389 artifacts are unchanged.
The fix is an independently built candidate, not yet the device's library.

## Validation

32 affected host tests PASS,0skip (7 new strict preparation tests plus existing
source/build admission dependencies),0.174s. No suite-routing change or full host
run. The existing pinned Debian builder1b148977 runs with network disabled;
the complete ARM64 library/ssccli compile and stage validation pass. No kernel
build or GitHub Actions.69 defined dynamic exports exactly match the original
library. New GLib imports are condition wait and context acquire/release/wakeup;
SONAME/public ABI remain compatible. The runtime archive includes only libssc,
ssccli and GPL license, three verified files/64,694 bytes, no installer or units.

13 ARM64/QEMU cases use the **real libssc common C and real GLib/GIO**, not a
reimplemented wait or a fake poll:

| Comparison | Observed behavior |
| --- | --- |
| Original,200ms completion/no reply | Tens of thousands of zero-timeout polls |
| Imported fix,ordinary completion | About6 polls; other sources continue dispatching |
| Imported fix,foreign-thread completion | Fixture timeout124, missing context wakeup reproduced |
| Final,ordinary/foreign completion | Returns with matching result, at most6 polls |
| Final,already completed | Returns with zero polls |
| Final,context owned by another thread | Waiter uses the condition, no foreign poll |
| Final,cancelled result | Cancellation propagates unchanged |
| Final,no reply | Remains unfinished; about6 polls during the200ms fixture observation |

Counts and raw outputs are in `WAIT_TESTS.json`; they are behavioral regression
checks, not physical CPU/power or sensor measurements. The expected reference
timeout is a successful negative-control reproduction, not a skipped final test.
Upstream QRTR/mock-server sensor tests were compiled by Meson but not run in the
networkless builder; the13 helper cases do not exercise SSC/QMI discovery.

Two initial host stops are preserved. The first fixture created/returned a GTask
inside the completion thread, independently queuing a context source and masking
the missing wakeup; the corrected fixture creates the result before waiting.
The second run passed all13 cases but used `COPYING` instead of this archive's
`LICENSE` in the last copy. The pathname was corrected. Both failures and reasons
remain separate; final qualification passed using the same incremental output.
No failed run is relabelled as successful.

## Reproduction and next step

Prepare the final source independently:

```sh
python3 userspace/sensors/libssc_wait_profile.py \
  --source out/ssc-sources/prepared-clean/libssc \
  --output out/libssc-wait/sources
```

Use `prepare(..., reference_only=True)` from the same module for the comparison
tree. `BUILD.json` records the exact networkless container command, read-only
original/reference/final mounts and output mount. The committed
`compile-libssc-wait.sh` compiles the full library, executes the committed real
GLib harness and packages the license; preserve prior qualification before any
incremental reuse. Never overwrite the original prepared tree.

No flash, reboot, ADSP/RPC activation, rootfs/library replacement, USB/charging/
kernel/config/DTS/input change or registry reset occurred. PPS/pump/DCC remain
OFF. The candidate can accompany a separately registered future sensor test;
its wait fix alone does not justify replaying Test389's failed startup. Next
continue firmware initialization and actual X710 prerequisites, and qualify the
remaining early D-Bus claim race before enabling GNOME's sensor proxy permanently.
Hardware acceptance still needs SSC publication, real samples and orientation.
