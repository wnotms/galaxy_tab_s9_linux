# Test280 — passive trace integration; read-only preflight stopped

Purpose: prepare single-process orchestration of the qualified Test279 tracefs
session and corrected Test276 observer, to narrow Test275/277 request latency.
Reuse sealed Test272 provider, without a kernel rebuild or hardware/policy change.

Before registration, read-only device checks found Test263 config/notes intact,
but a new boot with `lpcharge=1` command-line differences from the accepted normal
boot. Raw evidence is preserved in `preflight/`; **the physical test stops here**.
No collector setup, module load, reboot, transfer, partition/module write or
charging mutation occurs. An owner explanation of the new boot does not silently
qualify different command-line inputs. No retry of this Test280 attempt.

## Offline preparation

Implement a future device-side coordinator that directly owns a Test279 Session:
setup -> start -> one corrected observer load -> cached terminal result -> fixed
500ms tail -> snapshot/cleanup -> unload. No asynchronous ready-file race or
additional fresh request. Required identity/health/transport preflight remains
outside the coordinator, with its exact boot ID rechecked before the load.
Maximum observation30s (load included), trace35s, unload10s. First refusal stops
acquisition; tail is evidence of existing work, never a retry. Error preserves
raw collection and attempts owned cleanup/unload, while recording failures.

Only host fixtures execute the new coordinator in Test280. Validate first refusal,
trace setup failure, ambiguous load timeout, cached read failure, deadline,
boot change, cleanup/unload failure and single-load semantics. Keep historical
Test279 source/tests sealed; imports are explicit, not global routing changes.

## Frozen scope

Provider399eb497, observer7a887eab9aafabf6;100ms/average32/channel0xdf/12x25ms;
fixed5V<=1.8A/9V<=1.5A,4440mV, thermal/suspend safety, DCC=n and Docker/ADB intact.
No PPS, pump ON, current increase, USB/rootfs/DTS/config/driver changes.

Future physical execution needs a separate registration and accepted normal-boot
preflight, deployment readback/paired181modules and exact Test263 rollback. That
registration must be pushed before any device write. Test280 neither deploys nor
automatically reboots to repair the rejected preflight. Active Stage3 NOT READY.
