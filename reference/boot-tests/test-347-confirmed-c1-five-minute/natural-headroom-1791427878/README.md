# Natural-discharge headroom after PC preparation rejection

The original read-only process 6681 / unified session 8056 ended normally with
`NATURAL_HEADROOM_READY_FOR_FRESH_PC_PREFLIGHT`: 29 authenticated Wi-Fi samples
over 915.390 seconds, SOC 70 → 68%. Final readings were 31.3°C, 4.009 V and
−1.332 A. Every sample was USB offline, discharging, and from accepted Test331
boot `a96de8c0383b4f78b976ecc6db3ab793`.

The owner confirmed unplugging after the retained first PC preflight rejected
SOC 71%. Target 68% reserves PC/install charging headroom; the registered
20–70% admission range, current limits and single 300-second scope are unchanged.
The watcher only read boot ID and power_supply attributes at 30-second intervals.
It added no load and executed no device mutation, PPS or pump command. These
statements describe watcher operations, not a fresh hardware pump readback.

Raw SSH results, parsed samples, the original process handle and terminal summary
are retained. Units in raw samples: µV, µA, tenths °C and percent. This preparation
observation is neither deployment preflight nor charging acceptance. A fresh PC
preflight remains mandatory before the one paired install. The earlier incomplete
preflight is preserved; it must not be reused as successful evidence.

Tests executed: false. Build executed: false. Reuse the qualified 60 host tests,
79 actual-C tests and ARM64/W=1/sparse build results; this stage changes evidence
and status documentation only. Full charging port remains NOT_READY.
