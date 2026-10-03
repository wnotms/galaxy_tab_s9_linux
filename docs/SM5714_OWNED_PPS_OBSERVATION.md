# Native read-only observation of an owned PPS contract

Current `sm5714_pd_read_snapshot()` calls the fixed-only reader. A receipt
returned by `sm5714_pd_request_pps()` is valid evidence of that operation,
but cannot remain fresh throughout active charging. Issuing Requests to
obtain every monitoring snapshot would introduce frequent renegotiations and
violate the pump-OFF rule. The active adapter needs a separate read-only API.

The draft in `reference/charging/sm5714-owned-observer/owned-pps-observer.patch`
adds `sm5714_pd_read_owned_snapshot(instance, source_generation, lease, out)`.
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

The fixed wrapper, PPS operation, native TCPM and current installed Test317
remain unchanged. This is a two-file **unapplied** integration patch, not a
new installed driver or registered physical candidate. Its complete TCPC C is
compiled as a separate unlinked ARM64 object with a private include filename;
only those names differ from the patched source, protecting the current provider.
The host tests execute the patched functions together with existing producer,
property validation, actual pthread locking and teardown code.

After Test317 capture and compulsory exact accepted311 rollback, apply the
reviewed patch to a separately qualified integration candidate. The active
worker can then pair new native receipts with genuinely acquired pack/ADC data
and cancellation generation, without changing PPS cadence. This API is logical
contract evidence only: it cannot establish physical VBUS, ADC calibration,
qualified OCP/cutoff latency, safe ON, fixed fallback or PM acceptance. Those
remain required; the full charging port is NOT READY.
