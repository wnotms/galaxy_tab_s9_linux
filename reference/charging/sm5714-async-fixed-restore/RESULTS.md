# Async fixed charging recovery correction — offline qualified

Source revision: `86f7b6787f4d807f488f39818ae08f2b08f6f0eb`.
Linux pin: `a13c140cc289c0b7b3770bce5b3ad42ab35074aa` (7.2-rc3).
Verdict: **OFFLINE_ASYNC_FIXED_RESTORE_PASS**. Physical correction is not yet
accepted. Overall charging port remains **NOT READY**; no device command,
flash, reboot, PPS request or pump activation was performed in this phase.

## Change and reproduced gap

Test336 native PPS-OFF/fixed-return proof completed, but ordinary charging did
not return. Its saved fixed9 packet still had input100mA and negative battery
current over106 seconds later. The original source skipped reconfiguration if
online, cached PD and temperature state did not change; recovery required a
`charge_programmed` witness that the owned Q4-off operation had cleared.

The new actual-C regression initializes the previously cached fixedPD state,
executes acquire/asynchronous release and invokes the real poller. A one-shot
`charge_restore_pending` flag requests normal reconfiguration under `chg_lock`.
Normal configuration consumes it; acquire/revoke cancels it. The existing
charger faults, real thermistor, ownership, suspend, full-charge and I2C gates
remain in force. The unexpected-program-loss recovery budget is not consumed.
The second normal poll verifies stable programming instead of reprogramming.

The descriptor now declares the PD_PPS type already returned by the driver,
removing the enum8 property mismatch. This does not enable ordinary switching
charging during PPS. Host fixed charge safety now uses TCPM ONLINE/contract:
ONLINE1 may display PD_PPS source capability; ONLINE2 remains active
programmable operation and is rejected after native fixed-return proof.
The captured Test336 packet still times out settling because ordinary charging
never becomes healthy; a valid capability label does not conceal this failure.

The frozen Test336 runner and inputs are unchanged. Independent Test337
admission uses the shared discovery helper's flat `boot_id`, tested with the
actual bounded discovery code and mocked authentication/transport plus original
boot histories. Unchanged boot, missing/extra history and timeout stop admission.
The historical authorization test now isolates the unexecuted case from the
persisted real Test336 execution scope; no authorization checks were removed.

## Validation

- 295 affected host/C tests PASS, no skips,6.526s. Actual cached-PD poller,
  charge-program fault, I2C failure, thermistor failure, detach, suspend, renewed
  inhibition, full-charge and reduced-temperature cases are covered.
- 65 final host admission/window tests PASS, no skips,0.442s. Overlap with the
  previous set is intentional coverage of later-added host tests; counts are
  separate runs, not360 distinct cases.
- Full Image/modules/DT build PASS,81.492s, existing incrementally reused cache.
- Changed battery object W=1/C=2 sparse PASS,13.395s, no warnings; exact qualified
  object restored after inspection, no artifact relink from the inspection.
- Exact Test331 embedded config, release and DTB unchanged (`config.diff` and
  `dtb.diff` empty). HVC_DCC absent; Test254 container/UPower preserved.
- Paired181-file archive validated against output directory, required symbols
  and source copies checked. Module runtime allocations unchanged; permitted
  BTF/debug/build-ID metadata changes accounted.107 protected sources and17
  previous formal artifacts unchanged.
- No full host run/CI/Actions: latest owner scope is affected tests and
  dependencies. No test routing change. Qualification is not a hardware pass.

## Candidate and rollback

| Artifact | SHA-256 |
| --- | --- |
| Armed PPS-OFF-only boot | 39bf84766d298eee444a2739ab24005a0ba37402d686aa4ab6928cba0cc4e2ab |
| Embedded config | 51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a |
| Kernel notes | 39a825d12b9c4beb6a2cd2d8d7b5a62f120c00c4bc3d6da02382345e23e113d2 |
| Unchanged DTB | 233a9fee91dc725901f0c7c620a38e475d6d6e6880cde660ec85ae34d49e0a8e |
| Accepted Test331 rollback boot | 025ebea4282524751bace461ce96beef85c01ea65a4d2b117106c7cdfe0ab815 |

Full Image/module identities and181-file manifests are in `summary.json` and
`PACKAGE.json`. Header4/Image+DT/partition-size pairing verified offline.
Kernel defaults direct_charge/fixed_return_check/pps_return_check remain false;
the offline armed boot adds only `sm5440_fedora.pps_return_check=1` and is
not a default-OFF production image.

Fixed5/9 limits remain1.8/1.5A, float4.44V, fail-closed thermal/suspend policy
unchanged. No DTS, config, TCPM core, SM5440, USB/DWC3/gadget, adbd, CPU/GPU,
Wi-Fi/Bluetooth or rootfs change. No physical VBUS/power calibration claim.

Next: registered Test337 same single pump-OFF PPS/fixed-return scope, bounded
10s settle +30s ordinary charge +15s unplug and unconditional Test331 rollback.
Fresh live preflight and explicit Test337 scope remain required; registration
alone cannot opt the device into PPS or pump activation. No higher power step.
