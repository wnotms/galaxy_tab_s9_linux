# Test268 — battery-only observation completed

On 2026-10-01 the owner confirmed PC USB unplugging. The registered 150-second
window completed in 150.378 seconds, with 28 read-only Wi-Fi samples on unchanged
Test263 boot `4bbd82213c2c4501814c4dfc13d0695e`. Both boundary config and kernel
notes match registration. No reboot, flash, configuration change, PPS request,
pump enabling, latch clearing or new ADC acquisition was performed.

| Observation | Result |
|---|---|
| Battery health / status | Good / Discharging in all samples |
| USB online | 0 in all samples |
| SOC | 99% throughout |
| Gauge battery voltage | 4.343–4.366 V; final 4.352 V |
| Battery current | −1.320 to −0.510 A; final −0.744 A |
| Pack temperature | 29.0°C initially, 27.8°C finally |
| Wi-Fi SSH / boot continuity | Responsive throughout, unchanged boot ID |
| New failed systemd units | None |
| Detected CPU/panic/severe kernel signatures | None |

Full boundary kernel journals and per-sample incremental journals retain source
timestamps; the final full journal contains 1108 rows. Previously recorded startup
warnings remain explicitly classified, rather than treated as new faults.
No Code43/ADB/NCM test is claimed: PC USB was intentionally disconnected, and this
registration contains no reconnect phase. Unplug latency was not measured.

## SM5440 qualification remains incomplete

The original stopped passive monitor retains fault `0x80` and its old cached
sample/protection state unchanged. That cache does not establish live VBUS, VBAT,
IBUS or pump state. This window did not repair or accept SM5440. The gauge entry
hint remains false (SOC 99%, voltage above 4.3 V); gauge data cannot substitute for
fresh SM5440 ADC. Test267 remains STOP and its evidence is untouched.

Battery-only acceptance: completed within the registered window.
SM5440 / active Stage3 acceptance: NOT READY.

## Validation and next step

Registration's eight focused host gate tests and syntax check passed before the
physical window. This results-only change reuses that qualification and exact
Test263 kernel qualification: kernel build and changed/full host regression were
not executed again (`executed: false`). Evidence consistency and SHA-256 sealing
are checked separately; raw journals are not normalized.

No software was changed, so no rollback was required. Leave USB disconnected;
no indefinite discharge wait or automatic new boot is part of this test. Next
work is offline auditing of the full-pack startup REVBLK classifier and fresh-ADC
requirements, or a separately registered in-range boot when entry conditions can
actually be established. Do not relax the existing gate from this observation.
