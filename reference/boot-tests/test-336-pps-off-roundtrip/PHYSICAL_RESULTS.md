# Test336 physical result — STOP, accepted Test331 restored

Completed 2026-10-07. Final verdict: **STOP_RESTORED_ACCEPTED331**.
The native pump-OFF PPS/fixed-return subproof passed. Ordinary switching
charging did not recover after fixed 9V return. This is not full Test336
acceptance or direct-charge acceptance. The registered 30-second ordinary
charge and 15-second unplug windows were not completed.

## Scope and identities

The owner authorized one normal reboot and the registered single pump-OFF PPS
roundtrip. No pump ON or higher-current test was performed. The qualified
source `4d058527fe437b21d381d25fd336278a3aed9e94`, registration, runner and
frozen inputs were unchanged throughout this test.

| Item | Identity |
| --- | --- |
| Normal Test331 preflight boot | `90274be1fa0c44f794eecceaad099b45` |
| Attributed Test336 boot | `b6cc488f92834c2eaae21dd8caa8ed50` |
| Restored Test331 boot | `245457825f864f33ac57d81714ebb776` |
| Embedded config, both kernels | `51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a` |
| Test336 kernel notes | `59a9737423ad62691e6055376b683638a04b492a6dce11acf673e74d38371543` |
| Restored Test331 kernel notes | `03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95` |
| Restored Test331 boot image | `025ebea4282524751bace461ce96beef85c01ea65a4d2b117106c7cdfe0ab815` |

## First host stop, preserved

The enrolled-key Wi-Fi discovery matched the candidate at `10.91.255.227`
after 44.409 seconds. Admission then stopped with `KeyError('identity')`:
`host_flow.py` expected a nested identity object, but the shared discovery
helper returns a flat identity dictionary. [first-failure.json](first-failure.json)
is retained unchanged. Prior 57-test host qualification missed this integration
case; it is not retrospectively relabelled as a successful runner execution.

Only missing read-only evidence was collected from that authenticated,
attributed boot, without a second candidate boot or another PPS operation.
The native startup worker had already run its single registered transaction.

## Native subproof

The full [kernel JSON journal](first-stop-evidence/kernel-json.txt) contains
1,531 rows, including this ordered sequence. The table uses kernel
`_SOURCE_MONOTONIC_TIMESTAMP`; the original parser's journal-reception
`__MONOTONIC_TIMESTAMP` values are also retained in `physical-summary.json`.

| Source boot seconds | Event |
| --- | --- |
| 10.677752 | PPS negotiated, source generation 8, lease 1, target 8920mV / 1800mA, pump ON=0 |
| 10.826092 | PPS sampled, internal ADC 9266mV, 3 samples / 120ms, range 9266–9266mV, raw IBUS=0 |
| 11.115613 | Fixed return verified, internal ADC 9266mV, 3 samples / 121ms, range 9266–9266mV, raw IBUS=0, pump OFF=1 |
| 11.115637 | Terminal completion, lease=0, fixed_return=1, pump ON=0 |

No native return-failed or cleanup-error terminal was observed. The later
physical CNTL5 read was `01`, pump OFF. These internal ADC samples are not
independently calibrated VBUS or power measurements. One owned API transaction
can include multiple TCPM protocol Requests; this does not claim exactly one
wire message.

## Ordinary charge recovery failure

At saved packet uptime 118.09 seconds, approximately 106.97 seconds after the
native terminal, [current-state.txt](first-stop-evidence/current-state.txt) shows:

| Measurement | Value |
| --- | --- |
| TCPM ONLINE / fixed contract | 1 / 9,000,000uV, 1,500,000uA |
| Battery | Not charging; net −959,000uA |
| SM5714 USB input limit | 100,000uA |
| SOC / VBAT / pack temperature | 58% / 3.943V / 23.6°C |
| Health / presence / design float | Good / present / 4.44V |

The result cannot be explained as a first-sample settling interval. Ordinary
charging remained absent well after the registered settling bound.

TCPM USB_TYPE was `C PD [PD_PPS] PD_SPR_AVS PD_PPS_SPR_AVS`.
In this Linux tree `tcpm_pd_select_pdo()` exposes source PPS capability in
USB_TYPE even for a selected fixed PDO; ONLINE=1 indicates fixed operation.
The PD_PPS label alone therefore does **not** prove that PPS remained active
or that fixed-contract exit failed. The ordinary charger state and negative
battery current independently establish the non-clean return.

The journal contains 412 `sm5714-usb: driver reporting unavailable enum value 8`
warnings. The existing classifier reports no CPU-stall/panic fault signature
or other classified suspect, and failed systemd units are empty. Classifier
acceptance does not erase these new power_supply warnings or the charge failure.

## Source findings and next scoped correction

These are source-level findings, not claims that internal live flags were captured:

1. `sm5714_disable_charging()` clears `charge_programmed`. Asynchronous switching
   release removes the lease/inhibit and schedules the poller, but does not
   prove completed Q4 programming. The poller reconfigures on online/type/full/
   thermal transitions; with unchanged cached PD state it can instead call
   recovery, which returns immediately when `charge_programmed` is false.
   This is a plausible missing reconfiguration trigger for the captured result.
   A follow-up must make reconfiguration explicit while preserving temperature,
   fault, detach, suspend, ownership and source-generation gates.
2. `sm5714_get_usb_type()` can return PD_PPS, while `sm5714_usb_desc.usb_types`
   does not declare it. Correct the standard property declaration without
   authorizing switching charging during PPS.
3. Test the admission integration against the actual flat discovery result.
   Host ordinary-charge gates must distinguish source PPS capability from
   active PPS using TCPM ONLINE/contract evidence, not USB_TYPE alone.

Do not repeat this unchanged failed candidate. Qualify the minimal correction
with affected tests, including actual poller recovery with unchanged cached PD,
plus fault/detach/suspend cases, before registering another physical round.
Do not alter TCPM core merely to remove its valid PPS-capability label.

## Rollback and final acceptance

After the owner unplugged C1 and reconnected PC, the exact accepted Test331
boot and original 181 modules were restored. All five partition hashes and the
complete module set matched, BCB was cleared, root unmounted, and one normal
reboot was attributed to the restored boot above. The diagnostic module set
is retained separately; it is not the active module directory.

[Final acceptance](final-acceptance/summary.json): 58%, 4.021V, 27.9°C,
net +0.957A on PC USB, input limit 1.8A; physical pump OFF, PPS false.
ADB, authenticated Wi-Fi `10.91.255.52`, device NCM and Windows Code0 passed.
Normal cmdline/config/notes, full kernel journal and empty failed-unit gate
passed. No new classified kernel fault or suspect was found. The mutation
state is `accepted331-restored`, `rollback_required=false`.

This result-only stage changed no kernel/config/DTS/driver/helper/test/rootfs
inputs. Tests `executed: false`; unchanged 57-test runner and frozen kernel
qualification were reused, not reported as a new regression pass. No rebuild,
full host run, Actions or further device experiment was started.

Expired Test326 images were retired under the Test327–Test336 retention window;
see [cleanup record](../../host-storage-cleanup/2026-10-07-test336-image-retirement/summary.json).
Original registration/result inputs remain frozen. New evidence hashes are in
`PHYSICAL_SHA256.json`; machine-readable outcome is `physical-summary.json`.
