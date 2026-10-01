# Test265: Fedora-derived PM transition core (offline)

Start after Test264; installed Test263 remains unchanged. Port Fedora ab123e7d
sm5440_pm_notify() drain/OFF/fixed-before-suspend semantics to the existing
unwired transaction C core. Source pointers and protection findings are in
Test264 sources.json and docs/SM5440_ACTIVE_PROTECTION_PM_PLAN.md.

Add a transaction suspend latch: suspend revokes arming before verified stop;
ON/start remains denied during suspend. Resume only clears a successfully
quiesced SWITCHING/uninhibited/unarmed transaction; no automatic rearm or old
PPS restoration. Invalid adapter/OFF/exit/fixed/epoch failure stays stopped or
faulted and is propagated. Repeated suspend is safe. Cancellation/drain/device
links/actual PM notification remain the future live adapter's responsibility.
No callback race/lifetime or physical cutoff claim from the pure C model.

Preserve fixed limits, thermal, register writes, ADC, live TCPC deny-PPS, DTS,
config fragments, USB/adbd and HVC_DCC absence. Only x710-charging-policy.c/.h
and their host tests change. No live adapter, PM notifier, kernel hardware write
API, thread, source role, current escalation or rootfs changes. No device access,
reboot/flash/module replacement or suspend command.

Validate actual C with mocked ops/clock and fault injection. One isolated
sm5440-policy-offline build (JOBS8, clang21, ccache, paired modules), resolved
config exact diff versus Test263: only CONFIG_X710_CHARGING_POLICY=y expected.
DTB must match; all other existing charging/container/USB/DCC gates remain.
One final full host run, W=1/sparse for changed policy core where available;
reuse immutable installed artifacts, do not overwrite them or rebuild for prose.
Physical Test265 NOT EXECUTED; activeStage3 still NOT READY.
