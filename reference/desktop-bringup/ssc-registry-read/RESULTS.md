# Test380 derivative: complete logged cache read lengths

This is offline replay plus a read-only accepted-baseline capability check, not
a new boot test or reinterpretation of Test380's STOP. No device write, reboot,
flash, package install, ADSP start, RPMSG binding or diagnostic packet occurred.

The new `userspace/sensors/registry_read_evidence.py` CLI requires exact journal
and manifest SHA-256 from Test380's existing `RESULT_SHA256.json`. It restricts
evidence to one sensor PID and boot, tracks FD lifetimes, rejects partial/excess
reads, missing groups, unclosed sessions, seeks/writes/failures and cross-process
or cross-boot evidence. Reopening cannot combine partial reads into a PASS.

Actual failed boot16971083-2297-4220-a24f-24e113ba612d, PID1985:

| Measurement | Result |
| --- | --- |
| Nonempty cached groups | **178 expected / 178 observed**, every length matches |
| Read callbacks for these groups | **203** |
| Sum of returned bytes | **44,863** |
| Empty archive marker | `sensors_registry`, zero bytes; no claimed read |
| Missing groups / replay faults | **0 / 0** |
| Payload contents / DSP parsing / electrical sensor response / SSC success | **Not proved** |

`READ_LENGTHS.json` preserves all per-session paths, timestamps, returned counts,
source content hashes and raw-input hashes. The content hashes identify the
expected frozen files; the verbose trace itself contains counts, not payload
bytes. The `sns_reg_version` marker read and SoC/sysfs/config-file reads are not
included in the cached-group total. Successful callback logs also precede the
next listener response, so they do not prove remote consumption. Preserve
Test380's original60s/23probe discovery failure and automatic rollback.

34 selected host tests passed in0.235s, no skips: new14 replay/fault/CLI tests,
existing12 metadata tests and8 core-cache tests. `HOST_TESTS.json` records exact
selection and source hashes. Existing kernel/ARM64/RPC qualification reused;
kernel build/full regression/routing/CI **executed:false**. Shell syntax and
Python compile checks are recorded separately in `STATIC_CHECKS.json`.

Fresh ADB read on accepted boot178facf3-7e1e-4004-8041-cd70eb48df6d:
GDM, adbd, USB ACM, `gts9-usb-typec-lifecycle` and SSH loaded/active/success;
ADSP offline, RPMSG device list empty. Battery100%,26.1°C,4.440V/healthGood;
Wi-Fi10.49.219.77, usb0 has169.254.42.1. This is a snapshot, not a new observation
window or a user-confirmed visual desktop test. The first inspection mistakenly
asked for `gts9-usb-lifecycle` (not the installed name), producing `inactive`;
its raw output is preserved and corrected by `qualified-unit-state.stdout`.
No real USB service failure is inferred from that typo.

The same boot exposes six GLINK version/open/close control trace events, all
disabled, no instances, tracer `nop`. Existing kernel instrumentation can serve
the next independent channel-init question without rebuilding a kernel.
Current ADSP-offline inventory does not establish future DIAG availability.
Primary QRTR source identifies769 as SLIMbus and4097 as DIAG; Test380 has no4097.
The downloaded DIAG source was examined only on host: it sends feature/mask
controls, so installing/running it cannot be represented as passive collection.

Source comparison, exact constraints and next bounded design:
[SSC_DSP_DIAGNOSTICS_PLAN.md](../../../docs/SSC_DSP_DIAGNOSTICS_PLAN.md).
No new physical candidate is registered/deployed here. Current kernel/config/
DTS/modules/USB/adbd/charging/registry remain unchanged. Sensor migration and
automatic rotation remain incomplete.
