# Pump-OFF PPS roundtrip candidate — offline qualification

**READY for a separately registered PPS-OFF test; not hardware accepted.**
Kernel source `4d058527fe437b21d381d25fd336278a3aed9e94`; host entry helper03f8d9bf. No device
access, flash, reboot, module/rootfs replacement, real PPS or pump activation.
Installed accepted331 was not modified.

## Changes

- sm5440-fedora.c: readonly/defaultfalse/mutually exclusive pps_return_check.
  Single existing ordered worker, absolute300s admission, no diagnostic retry.
  Strict20–<80SOC/3.5–<4.3V/20–<38C pack; verifiedOFF/existing channelsdf,
  native switching lease, same-model continuous ADC, one owned TCPM request
  at unchanged1.8A/8.2–10.5V formula. Never calls hw_init/start/pump_on; no reset/
  current/frequency/protection programming. Actual/source-bound three samples
  over100ms/range≤100mV/±500mV/zeroIBUS/OFF. Primary and cleanup errors separately
  logged; existing terminal fixed9 proof/release always attempted. No rearm.
- ordinary_charge_window.py: bounded WAIT→SETTLING≤10s→OBSERVE≥30s. First335
  negative-current packet now waits for healthy ordinary charge without
  bypassing safety gates. Any loss after entry/timeout/clock gap/fault latches
  STOP. Synthetic clocks test the rule; no claim real335 settled within10s.
  Old335 source and original STOP/result remain sealed. Caller still owns native
  completion, identity, journal and transport gates; this helper is prepared
  for the future336 observer, not retroactively substituted into335.
- Actual C mocks cover all8 mode combinations, defaultOFF/oldfixedcheck, one
  PPS call, partial/fault cleanup, source mutation/lease/PM/detach, everyI2C
  failure, zero pumpON writes and no hardware current programming.

## Qualification

263 affected adapter/lease/TCPC/pack/PM/fixed-release tests PASS;10 entry tests
PASS. No old tests removed/disabled; routing unchanged, fullrun/Actions not run.
ARM64 Image/DT/modules build83.583s with8jobs/ccache and reused profile cache.
Changed-driver W=1+sparse13.524s, no warnings, formal object restored after
checks; no extra relink. Exact embedded config matches resolved; configuration
and DTB equal accepted331 byte-for-byte (empty diff files). DCC path absent;
Docker/UPower/battery/USB/adbd/CPU/safety config intact.181-file archive paired
with Image; kernel-module runtime allocations unchanged, relevant build/BTF/
metadata identities accounted.108 protected sources and17 prior formal
artifacts unchanged. No new complete build tree or Windows staging.

| Artifact | SHA-256 |
|---|---|
| armed boot | ffb7bc9401eac3664a063bcc22213001ffb07c636516cee92faf24b0a4941a79 |
| config | 51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a |
| notes | 59a9737423ad62691e6055376b683638a04b492a6dce11acf673e74d38371543 |
| modules archive | 76aedec2e8c18f15e8858c93afb9b88cf83dc7eeabbf8b646bb93562ee31b657 |
| DTB | 233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e |

Offline armedboot preserves exact Image+DT/header4/partition size; sole added
header flag sm5440_fedora.pps_return_check=1. Primary rollback is exact331
025ebea4 and its181 archive, not an old failed diagnostic. PACKAGE freezes both.
Kernel defaults all3 flagsfalse; the staged armed artifact explicitly opts into
PPS-OFF and must not be mistaken for a default-OFF production boot.

## Remaining work

NEXT_PHYSICAL_PLAN proposes independent Test336; not registered/deployed here.
Hardware PPS roundtrip, ADC calibration/request discrepancy, active protection/
current/OCP/PM/cutoff and pump/high-power behavior remain unaccepted. No timeout
relaxation for PPS envelope, no offset correction or fake readiness. Fixed5/9
limits1.8/1.5A, float4.44V, thermal fail-closed, DCC and335 evidence unchanged.
Overall charging port **NOT READY**. No automatic PPS/pump/current progression.
