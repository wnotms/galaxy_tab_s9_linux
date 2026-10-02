# Test304 results

Verdict: **READ_ONLY_OPERATING_STATE_CAPTURED**. Device remained on the accepted
Test299/Test300 boot. The 1,180-row kernel journal is attributed to that boot;
no CPU-stall/panic signature or temperature-read-disable message was found.
All enumerated thermal zones are enabled; the real pack zone is 31.8°C.
No passive SM5440 thermal zone exists. No systemd failed unit was listed.
This confirms the retained thermal-registration fix, not SM5440 ADC readiness.

## Actual control state versus primary sources

| Field | Live value [MEASURED] | Source interpretation |
| --- | --- | --- |
| CNTL5 before/after | `0x01` | Mode bits3:2 are OFF [VENDOR] |
| CNTL6 | `0x89` | ENHIZ bit7 set; lower bits match vendor init `0x09` |
| CNTL2 | `0xf2` | Matches vendor init disabling IBUS/IBAT OCP/THEM; not active protection proof |
| CNTL3 / CNTL4 | `0xb8` / `0xff` | Match vendor init |
| CNTL7 | `0x0c` | Vendor frequency encoding gives850kHz |
| VBUSCNTL | `0xe7` | Low bits7 match vendor11V OVP encoding; not permission to request11V |
| VBATCNTL | `0x37` | Vendor encoding gives4487.5mV; inherited inactive control, not actual pack voltage or an approved limit |
| VOUTCNTL / PRTNCNTL | `0x3f` / `0xfe` | Match vendor init |
| IBUSCNTL | `0x41` | Vendor encoding gives3250mA; pump OFF, not measured current or approved bring-up limit |
| THEMCNTL1 | `0x0c` | Matches vendor thermal recipe; not permission to heat the device |
| ADCCNTL1 / ADCCNTL2 | `0x0c` / `0xdf` | AVG32 set, enable/rate clear after refusal; traced vendor channel mask |
| DEVICEID | `0x21` | Expected low-nibble identity1, revision2 |

[VENDOR] `sm5440_init_reg_param()` writes CNTL6=`0x09` before starting the
direct state machine. `sm5440_set_ENHIZ()` explicitly sets bit7 when VBUS is
present and charging is disabled; `psy_chg_set_online()` applies that policy.
Therefore the current `0x89` is consistent with a vendor OFF/attached condition,
not automatically a defect. [FEDORA] the audited same-model `hw_init()` writes
`0x09`, resets hardware and selects continuous ADC as part of its active recipe.
Neither source justifies wholesale active init in the passive driver.

The current port does not write CNTL6. It preserves the inherited condition and
operates an explicitly triggered OFF-mode one-shot converter. This is a concrete
operating-condition difference worth isolating; it **does not establish** ENHIZ
as the cause of the voltage discrepancy. CNTL6 was not recorded during the
original startup conversions, and today's register read cannot fill that gap.

## ADC evidence remains refused

The cached snapshot is stale, fault1/startup_pending2. The full journal retains
two startup pairs from this same boot:

| Conversion | ADC start/read | SM5440 VBAT | Adjacent gauge VBAT | Difference |
| --- | --- | --- | --- | --- |
| 1 | 174/316ms | 3.597V | 3.819V, read316–318ms | 222mV |
| 2 | 1369/1497ms | 3.498V | 3.826V, read1497ms | 328mV |

The second sample fails the existing3.5V lower bound; the fault remains latched.
These are adjacent acquisition windows, not simultaneous calibrated references.
No offset correction, threshold waiver, freshness restamping or active grant is
derived. 142/128ms acquisition intervals also do not satisfy the strict100ms
fresh API; the separate500ms diagnostic API remains diagnostic only.

Current gauge at the register collection: Good/27%/3.753V/31.8°C. Net negative
battery current on the PC input is not direct-pump operation. Actual endpoint
VBAT was3.756V, far below the inactive VBATCNTL field described above.

## Next bounded scope

Prepare an isolated vendor-backed ADC operating-condition comparison, keeping
the pump OFF. Capture CNTL6 before/during/after conversion, preserve other bits,
and require verified restoration on success, error, PM and unbind. If ENHIZ is
temporarily changed, qualify the operation/restore lifecycle and register the
specific physical mutation before execution. Preserve original startup fault
evidence, paired gauge reads, ADC channels/average/encoding and freshness gates.
One short purpose-specific comparison should replace more delay-only replays.

The standard PPS consumer remains offline; active protection/OCP, actual ADC
validity/freshness and physical PPS/pump acceptance remain unresolved.
**Active Stage3: NOT READY.** No code/configuration change or device deployment
was made in Test304. Host tests/build `executed: false`.
