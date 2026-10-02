# SM5714 switching-path ownership (Test294, offline)

Design written before implementation, against test HEAD 706811f9. This fills
the missing `switching_gate` backend for the existing direct-charge transaction
engine; it does not attach that engine to hardware or authorize PPS/pump ON.
The accepted fixed 5V <=1800mA / 9V <=1500mA policy remains the default.

## Ownership and errors

Acquire returns a unique, nonzero 64-bit lease under companion-lock -> chg_lock.
The monotonically increasing issuer survives companion unbind/rebind. Exhaustion
refuses acquisition; no wrap/reuse. Concurrent ownership returns EBUSY without
I/O. An absent companion, suspend, fault or missing healthy fixed grant refuses
new acquisition. A revoked inhibited path may be adopted by a new qualified
owner, but adoption is not evidence of pump OFF or permission to negotiate PPS.

Latch switching inhibition before I/O; retain the existing fixed contract.
Use the existing vendor-derived CNTL1 ENQ4FET clear and VBUSCNTL[6:0] minimum
100mA encoding, then read back both. Attempt both safety operations even if
one fails, preserve the first error, latch fault on error. A nonzero output
lease on failure identifies retained inhibition; it is never a charging grant.
Q4 OFF plus 100mA is not full VBUS/VSYS isolation or measured pack current.

Release requires the exact still-active lease and current healthy fixed grant.
Only a future single-owner adapter that has independently verified pump OFF,
fresh fixed TCPM contract and physical VBUS may call release. These external
facts cannot be certified by the battery API and no such adapter is wired yet.
Keep chg_lock across the ordinary configuration transaction; failed restoration
retains inhibition and revokes the lease. No automatic fault-latch reset.

## Revocation and lifetime

Any changed TCPM budget, charge=false (standby/reset as well as detach), safety
fault, poller detach, suspend or unpublish revokes an active token while keeping
inhibition. No claim that every standby means physical detach. Resume/new attach
cannot reopen switching on behalf of an old transaction. Unpublish transfers a
sticky inhibited flag to the companion registry; publish inherits it before
allowing callbacks, preventing rebind from clearing another chip's ownership.
Registry and charger locks protect lifetime; poller/PM only take chg_lock and
never invert into the registry lock. No raw companion pointer escapes.

Ordinary configuration is split into a lock-held implementation plus its usual
locking wrapper, preserving the old register sequence when inhibition is false.
The inhibit test joins the existing standby/suspend/fault early-return gate.
No long PD waits, PPS requests or new delays inside either mutex. Existing
short ordinary-current ramp delay remains unchanged.

## Qualification and boundary

Actual-C fault tests cover acquire/readback failure, poll/TCPM attempts to reopen,
token mismatch, duplicate ownership, budget/standby/fault/PM/detach revocation,
rebind and token exhaustion, restoration errors and default fixed policy.
One final kernel build/full host regression/config/DT/protected-artifact audit
is required. Keep all old tests; update mirrored host fixture declarations only
as needed to compile the actual added state and lock-held function.

Test294 is offline only. No device command, flash, reboot, module installation,
PPS transport authorization, pump activation, current increase, DTS/config/TCPM
core/USB change. Current Test263 installation and Test293 refusal stay intact.
Calibration, physical cutoff/OCP, live coordinator and PM supplier ordering remain
separate unresolved gates; this backend alone cannot make Stage3 READY.
