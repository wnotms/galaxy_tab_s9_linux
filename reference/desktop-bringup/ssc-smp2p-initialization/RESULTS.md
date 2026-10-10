# SSC SMP2P initialization boundary — source and capability evidence

ADB is available on the unchanged returned Test370 boot
`0171a6e6-ef97-41e8-baf8-4ab81b0d6b89`; GNOME is active. Read-only checks
record 100%, 34.2°C and VBAT4.445V. ADSP remains offline. Nothing was flashed,
rebooted, loaded, enabled or started. This is not another SSC startup test.

## New source evidence

The X710 stock DT dump and Samsung Kalama source agree on ADSP SMP2P host2,
SMEM items443/429, and two additional entries: AP output `sleepstate` and DSP
input `sleepstate_see`. The downstream sleepstate driver sets bit12 on probe,
clears it at `PM_SUSPEND_PREPARE`, sets it at `PM_POST_SUSPEND`, and handles
the inbound wake notification. This is a processor sleep/wake contract, not
an IMU bus, a PD service state or a substitute for SSC samples.

The actual running mainline DT exposes only `master-kernel` and `slave-kernel`.
The source behind the accepted mainline board and the Fedora board do not add
the stock sleepstate entries. Fedora remains at ab123e7d. Its reported sensor
operation is cross-check evidence; missing stock sleepstate alone is not a
demonstrated explanation of our unpublished SSC service.

Three original firmware members, including `adsp.mdt` and `adsp.b18`, were
individually checked against the previously qualified archive manifest after
checking the entire archive SHA256. The signed sensor segment contains both
entry names and the client-manager QMI registration failure string. These are
**static strings**, not DSP logs or observed failures. Offsets/virtual addresses
and hashes are in `firmware-strings.json` and `AUDIT.json`; no firmware binary
has been added to Git or installed on the tablet.

Bounded Hexagon disassembly supplies more than a string match:

| Span | Observed instruction relationship | Limit |
| --- | --- | --- |
| b32f8740–b32f8800 | Thread setup precedes the call passing the exact `sleepstate_see` string at b32f87bc. Its error branch clears a context field, then rejoins the success path at b32f87dc. | No direct initialization abort at this local join; not proof that later processing succeeds. |
| b3273b50–b3273ce0 | The call passes `sleepstate`; the received value is reduced to bit12 at b3273c3c. | Matches downstream awake-bit semantics; no runtime value or sensor readiness observed. |
| b32f8fc0–b32f9100 | A thread wait/event path tests bit6 and calls b32fc4f8 before the QMI registration error branch. | Event meaning/cause and actual execution remain unproven; no claim that bit6 is a particular registry-complete event. |

Addresses are the original ELF program-header **virtual** addresses, not
physical addresses for memory access. The disassembler input is an offline
synthetic ELF wrapper around unmodified segment bytes, with a synthetic `.text`
section and no original symbol names. Data interpreted as instructions outside
these bounded code spans is not evidence. No DSP instruction was executed or
patched. The source comparison does not justify creating an arbitrary SMP2P
entry, driving bit12, editing registry timestamps or changing a bus owner.

## Available next observation

All four native `qcom_smp2p` trace formats are present on this exact accepted
kernel: negotiate, notify_in, ssr_ack and update_bits. Their raw format/enable/
filter state is retained. All are disabled, the global tracer is `nop` and there
are no trace instances. The capability read did not alter trace state.

A separately qualified early-boot trace can therefore observe the existing
ADSP SMP2P negotiation and configured master/slave entries alongside GLINK,
without a new kernel, DT change, diagnostic module, shared-memory write or DSP
control packet. It must start before the first ADSP start, use an isolated
bounded buffer and a verified ADSP device filter, preserve raw events and loss
counters, and restore exact370/GNOME after one startup window. Missing early
coverage or loss is an evidence failure, not a negotiation-failure finding.
The native events only report configured entries; they cannot inventory every
unconfigured remote SMEM entry or capture arbitrary DSP log strings.

This is a next observation design, **not registered or deployed Test399**.
Retain the exact398 RPC repair, stock assets and safety limits; do not repeat
398 unchanged. A positive SMP2P open does not prove SSC initialization, while
an absent event without full coverage does not prove a failed open. If the
provider path is healthy, the remaining question is the firmware initialization/
QMI registration boundary; transport success must not be renamed sensor PASS.

## Validation and scope

Archive/member hashes, original program-header mapping, bounded disassembler
outputs and same-boot ADB reads were verified. `SHA256.json` seals this new
evidence separately from historical Test398 files. Source identities are pinned
in `AUDIT.json`; unmodified accepted identity/181-module qualification remains
the separate Test398 return result, not a newly executed full acceptance here.

Host tests/build: `executed:false`, documentation/source evidence only. No
runner/parser, production kernel/config/DT/modules, rootfs, firmware, registry,
USB, charging or input change; no full regression or Actions. DCC/PPS/pump OFF
and 4.44V float/thermal policy remain unchanged. SSC400/sample/automatic rotation
remain unfinished. No image was created; retention remains389–398.
