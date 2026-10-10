# Missing RPC file status — compiled, not deployed

Test389 remains the latest physical sensor observation. Its sensor-PD sequence6
called `apps_std_fopen_with_env` for absent `oemconfig.so` and returned generic
`AEE_EFAILED` (1). The asset's necessity and any effect on SSC publication are
unknown. No replacement library or firmware is added.

The pinned Qualcomm [Android13 FastRPC implementation](https://android.googlesource.com/platform/external/fastrpc/+/refs/tags/android-13.0.0_r77/src/apps_std_imp.c)
returns `AEE_ENOSUCHFILE` from failed `apps_std_fopen`; its environment wrapper
delegates to that function. The matching [error definitions](https://android.googlesource.com/platform/external/fastrpc/+/refs/tags/android-13.0.0_r77/inc/AEEStdErr.h)
assign this error `0x045` (69). PRIMARY.json retains source hashes and provenance.
The local implementation conservatively maps only actual `-ENOENT` to69;
permission, I/O and read-only errors remain generic failures. Logging uses the
negative VFS error instead of unrelated libc `errno`.

## Exact composition

An explicit private profile pins all56 files of frozen Test389 rpc-return-v2.
Only `hexagonrpcd/apps_std.c` and its internal `aee_error.h` change. Zero-fuzz
preparation rejects source/patch drift, extra files, links, overlapping output
and unexpected changes. The actual compiled file set matches that manifest.
Default sources and the old prepared tree/qualification remain unchanged.

The new ARM64 daemon is `36fae649be02137c156588dacf453ffa467de6a18d15b3b95167c1e7569627a1`.
Its library is unchanged at `1be44d2fe0c9b5ca785ef27730fba586a7f678f82f91cfbfb01613b3dad76f6e`.
Existing corrected wire layout, stat metadata, file contents, descriptor
lifecycle, listener framing and bounded return tracing remain intact.

## Verification

- 105 directly affected host tests PASS,0skip:10 new source/actual-C cases plus
  existing stat, wire, listener/evidence and shared preparation tests. Native C
  compilation uses Werror and undefined-behavior sanitization.
- Full ARM64 daemon/library build PASS in the unchanged pinned, networkless
  builder; both upstream Meson tests PASS. No kernel build or full regression
  was executed, since this only changes an isolated userspace callback profile.
- 18 ARM64/QEMU executions cover original/final variants of nine cases. Real
  callback code, virtual-directory lookup, mapped host-file reads and descriptor
  allocation are exercised. Only permission/I/O error entries are injected.

| Case | Original | Final |
| --- | --- | --- |
| Missing library | 1,stale I/O diagnostic | 69,actual missing-file diagnostic |
| Present library | Success,exact15 bytes and closed descriptor | Identical |
| Permission/I/O/read-only write | Failure | Failure; actual diagnostic |
| Unknown environment/invalid mode | 14 | 14 |
| Missing environment directory | 1 | 1 |
| 1024 missing requests | 1,no leaked descriptors | 69,no leaked descriptors |

The harness verifies untouched output on failure, one root descriptor remaining
after every request and zero after root close. Present-file stdout and payload
are byte-identical. These are host tests, not DSP parsing or hardware acceptance.
The initial native fixture's output filename collided with its source directory;
that host-only stop is recorded, then corrected. Original compiler stderr was
not retained and is not fabricated. A slow per-file Git subprocess audit was
stopped and replaced by one scoped Git diff; no device operation was involved.

BUILD.json, ARM64_CASES.json, HOST_TESTS.json, source/ELF identities and raw logs
record the executed checks. RUNTIME.json identifies a verified three-file
binary/library/license archive, with no installer or service files. SHA256.json
seals this evidence. No archive was installed.

## Device and next boundary

A short read-only ADB check confirms the same accepted Test370 boot
`0f360b00-4f24-43cf-8ce5-1aa135c5f7a3`, active GNOME,100%,31.5C,4.432V,
ADSP offline. Kernel/config/DTS/modules, USB/ADB/rootfs/charging configuration,
default sensor sources and historical physical evidence are unchanged.
PPS/pump/DCC remain OFF; no reboot, ADSP startup or GitHub Actions occurred.

This fixes an observed callback semantic difference; it does not establish that
the firmware requires `oemconfig.so`, that generic status caused absent SSC400,
or that sensors/rotation now work. A separately registered single-startup test
may compare the actually returned status with Test389 and check SSC/sample
publication. Keep the same firmware/assets/registry and other userspace inputs,
stop on the first failure and restore accepted Test370/GNOME. Do not mix the
separate libssc wait or proxy race changes into that firmware comparison.
