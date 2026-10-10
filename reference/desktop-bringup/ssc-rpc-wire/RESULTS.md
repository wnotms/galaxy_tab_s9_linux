# FastRPC empty-buffer correction — compiled, not deployed

The exact Fedora X710 transport is already imported and was physically used in
Test378; replacing it with the same sources again is not a new repair. Fedora
HEAD still matches ab123e7d1dbc0cbcd35661f9761197e977b15aa9. Current hexagonrpc
upstream was also compared (pinned in UPSTREAM_COMPARISON.json): its broader API
upgrade retains these codec defects. No wholesale API upgrade is introduced.

The real frozen iobuffer C implementation has two reproducible wire defects:

| Case | Original | Corrected |
| --- | --- | --- |
| One zero-length input | Parameter not consumed; decode incomplete | Consumes one header/parameter |
| One zero-length output | Reported8bytes, encoded4bytes | Reported/encoded4bytes |
| Header after odd-size payload | Potentially unaligned uint32 store | memcpy size header |

Qualcomm's [primary listener protocol implementation](https://android.googlesource.com/platform/external/fastrpc/+/refs/tags/android-13.0.0_r77/inc/listener_buf.h)
aligns only non-empty payloads. The new patch follows that boundary; existing
non-empty vectors and512-byte registry-read-sized responses remain identical.
This is an independent profile changing **one source file only**, after strict
source/patch/base/result hash admission. Historical profiles/artifacts/manifests
remain frozen. No stat values, registry data, timestamps or selectors changed.

19 new native host tests passed, including original failures, empty buffers at
all positions, fragmented headers, existing layout, independent golden bytes,
UBSan alignment and real preparation transaction/corruption/link admission.
10 preparation +15 build-admission tests also passed: **44 affected tests,
zero failures/skips**. Python/shell syntax passed. No routing change or full
regression. The copied C/header fixtures are pinned source, not a mock encoder.

Networkless pinned Debian builder compiled ARM64 hexagonrpc. Both upstream tests
passed under QEMU (2/2, no skip). The added29-byte mixed empty/non-empty golden
vector also passed on ARM64/QEMU with Wall/Wextra/Werror. All55 compiled source
files exactly match SOURCE.json. Daemon SHA256:
`e3845e823300577fd69ecbf84f83bbd07b7f618b4fe1e33a8c3cd83b48f78b8d`.
Full compiler/build/test/ELF logs and per-artifact identities are retained here;
runtime binaries remain in `out/ssc-rpc-wire/build-output/stage/`.

**No device deployment, module load, ADSP start, reboot or flash.** No kernel,
config, DTS,181-module set, charging/TCPM, USB, GNOME or input change; no kernel
rebuild or Actions. Read-only ADB confirms acceptedTest370 boot d8654881 unchanged,
ADSPoffline/GDMactive (separate post386 source evidence).

**Not a sensor PASS or proven rootcause.** The old text trace has no encoded
buffer lengths; we have not identified a real DSP invocation triggering an
empty-buffer defect. Test386's ACK-only DIAG result stays unchanged. Sensor
samples, SSC400 and auto-rotation remain unverified.

Next: independently register one controlled Fedora-RPC startup using this
qualified daemon, preserving the accepted kernel/fixed-PD baseline and isolated
stock registry. Compare SSC publication and actual samples within60s; no DIAG
masks, no service restart loop. Capture the first failure and restore Test370/
normal GNOME. A negative result must not be repeated unchanged or described as
proof that empty buffers were the cause. The profile does not authorize deployment
by itself; this document is offline qualification, not a Test387 hardware result.
