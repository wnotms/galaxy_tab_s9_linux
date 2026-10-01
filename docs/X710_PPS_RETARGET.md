# X710 PPS operating-point update — offline Stage3 core

Test269 extends the unwired policy core. It does not change installed Test263,
the failed Test267 result, the Test268 discharge result or the startup classifier.
There is no live adapter or timer, PPS permission, pump enable, new ADC command,
DTS/config/USB/current/thermal change. Active Stage3 remains NOT READY.

## Sources and scope

[VENDOR] `sm5440_direct_charger.c:_calc_pps_v_init_offset()` and
`pd_pre_cc_work()` initialize voltage from twice measured battery voltage,
current times board cable resistance, and 200mV initial headroom. The X710
320mΩ parameter is recorded in the existing vendor audit. Vendor CC/CV work
also adjusts voltage/current from regulation flags, power limits and offsets;
this step does **not** claim to port that entire feedback/termination policy.

[FEDORA] `sm5440_direct.c:sm5440_refresh_pps()` recalculates the operating point
as VBAT changes; `sm5440_renegotiate_pps()` parks the pump around Requests and
waits for actual VBUS. Remote HEAD checked by `git ls-remote` still equals the
audited local `ab123e7d` snapshot. Source file hashes are in Test269 sources.json.
Adopt the calculation and OFF-before-negotiation ordering. Do not copy its
unqualified current margins, permissive settle check or automatic current ramp.

[MAINLINE] Linux TCPM remains the PD/PPS protocol owner. The policy computes
desired parameters; a future reviewed adapter must perform framework operations
and verify physical evidence. No TCPM core or TCPC change is needed here.

## Transaction

Existing refresh repeats the old target. Add explicit `x710_charge_retarget()`:

1. Require active, armed, non-suspended, serialized ownership.
2. Verify pumpOFF; then check the existing monitoring deadline.
3. Acquire fresh eligible facts, verifying epoch before/after acquisition.
4. Recompute using VBAT and the current APDO. Current is at most the previous
   target and source ceiling, rounded down to 50mA; never increase it automatically.
   Use the existing 20mV voltage rounding, 8.2–10.5V / 1.0–1.8A bring-up limits.
   Refuse an offer that cannot provide headroom, rather than clamp voltage down.
5. Confirm actual OFF state and physical voltage at the old operating point;
   check again that the newly computed target fits fresh facts before Request.
6. Request new PPS, verify fresh physical VBUS within ±100mV and pumpOFF.
7. Revalidate eligibility/source; reprogram the approved current limit while OFF;
   revalidate again. ON is last, with a fresh post-ON observation within 100ms.

Even an unchanged target uses OFF and evidence gates. A shrunken offer can reduce
current; a later expanded offer cannot raise it. More current requires a separate
approved capability/bring-up stage, not this retarget function. Current reduction
must reprogram pump regulation; PPS current alone is not physical OCP.

Any failure revokes arming and uses existing checked OFF → fixed restore →
physical fixed-voltage check → switching restore. Failed OFF prohibits further
voltage changes; changed generation prohibits applying an old contract to a new
attachment. Fault/PM recovery never auto-arms. The requested target remains
available for diagnosis if failure happens after it is installed in the transaction.

## Ownership and verification

The future single owner serializes all transaction entry points; there are no
new locks or sleeping loops in this pure core. Each adapter callback must check
generation under its own hardware serialization, bound its waits and use genuine
acquisition timestamps. Core pre/post checks cannot close a callback's I/O race.

Execute the actual C in host tests: rising/falling VBAT, source-current reduction,
no autonomous increase, source voltage/current insufficiency, missing/stale
facts, epoch/source changes during callbacks, OFF/PPS/ADC/prepare/ON failures,
overcurrent, missed deadline, PM/arming refusal, and fixed restoration ordering.
Retain existing test assertions. Build once with the explicit offline profile:
only CONFIG_X710_CHARGING_POLICY=n→y versus Test263; DTB identical.

Host decisions and a compiled kernel do not validate protection or higher-power
charging. Next physical work must first resolve the passive full-pack failure
without fault masking, qualify fresh ADC/nonzero-current/protection, and review
the live adapter lifetime/PM ordering. No request for 2–3A or pumpON is included.
