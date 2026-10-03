# Native read-only observation of an owned PPS contract

Current `sm5714_pd_read_snapshot()` calls the fixed-only reader. A receipt
returned by `sm5714_pd_request_pps()` is valid evidence of that operation,
but cannot remain fresh throughout active charging. Issuing Requests to
obtain every monitoring snapshot would introduce frequent renegotiations and
violate the pump-OFF rule. The active adapter needs a separate read-only API.

The driver now implements
`sm5714_pd_read_owned_snapshot(instance, source_generation, lease, out)`.
The earlier draft is preserved in
`reference/charging/sm5714-owned-observer/owned-pps-observer.patch` as historical
evidence; its unapplied status describes that earlier qualification only.
It uses the existing lifetime pin, try-only control mutex and actual native
`sm5714_read_contract_pinned(..., true)` path. Short transport-locked checks
bracket that getter; the transport and registry mutexes are never held across
power_supply or battery companion calls. Switching ownership is checked before
and after the native getter, outside the transport mutex. The caller serializes
against lease release and cancellation, as required by the existing control API.

Admission needs a matching live instance/source/budget generation and PPS lease,
mirrored PPS target, charge_requested, no in-flight operation/restoration/fault,
and a validated PPS APDO pair. Native ONLINE2, repeated identical properties
and exact mirrored voltage/current are required by the existing pinned reader.
Fixed ONLINE1 with a PD_PPS capability label, AVS, stale source, source reset,
new budget, PM/revocation or provider drain are refused. Error output is zero.
Returned timestamps are the original property acquisition window, never a
fresh stamp on a retained receipt. No Request, callback, lease release, SM5714
register programming or pump operation occurs. Budget generation is unchanged.

Test317 has ended and exact accepted311 has been restored. The source API is
now integrated through the normal SM5714 TCPC Kbuild path, while the fixed
wrapper, PPS operation and native TCPM remain unchanged. The device continues
running accepted311. The current tests require the API in the actual driver;
they no longer apply a draft into a temporary tree to supply a missing API.
They execute the actual functions with the existing producer, property
validation, pthread locking and teardown code. The unchanged fixed wrapper is
compared against the sealed pre-integration source, not against itself.

Integration evidence, the normal ARM64 Image/DT/modules build, exact config/DT
comparison and affected tests are recorded in
`reference/charging/sm5714-owned-observer-integration/`. This uses the existing
`sm5440-adc-condition` incremental cache and preserves the Test316 artifacts
and accepted311 rollback. It is an offline build, not a physical registration
or authorization to use its diagnostic profile for active charging.

The future active worker must pair these native receipts with genuinely
acquired pack/ADC data and cancellation generation, without changing PPS
cadence. This API is logical contract evidence only: it cannot establish
physical VBUS, ADC calibration, qualified OCP/cutoff latency, safe ON, fixed
fallback or PM acceptance. Test317's 128–130 ms ADC acquisition/read brackets
remain diagnostic evidence, not a 100 ms protection qualification. This change
does not modify the converter's averaging, waits, registers or deadlines.
Physical qualification and live worker integration remain required; the full
charging port is NOT READY.
