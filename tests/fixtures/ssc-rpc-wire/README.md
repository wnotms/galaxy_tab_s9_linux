The three codec/header files are unchanged copies from pinned hexagonrpc0.4.0
after the repository's three Fedora X710 patches. Their complete hashes match
`userspace/sensors/diagnostics/rpc-wire.json` and are checked before native
compilation. Original copyright/license notices are retained. `wire-cases.c`
is the local independent protocol vector, compiled on host with UBSan and on
ARM64 under QEMU. These fixtures are not the implementation substituted by tests:
tests compile the original C, reproduce its failures, apply the actual candidate
patch with zero fuzz, verify the result hash, and compile the corrected C.

Wire layout reference: Qualcomm's
[listener_buf.h](https://android.googlesource.com/platform/external/fastrpc/+/refs/tags/android-13.0.0_r77/inc/listener_buf.h).
An empty buffer contributes only its four-byte length header; alignment applies
only to a non-empty payload. No firmware or proprietary sensor data is included.
