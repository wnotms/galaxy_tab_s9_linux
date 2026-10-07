# Test336 ordinary fixed-charge restore correction

Purpose: consume an explicit async switching-release reconfiguration even when
the poller cached fixed PD/online/normal temperature, as observed in Test336.
Do not change current, float voltage, thermal limits, TCPM core, USB/DWC3,
DTS, config, adbd or rootfs. Pump ON and new PPS work are not authorized here.

A charger-lock-protected one-shot pending flag is set only after validated
asynchronous lease release. Acquire/revocation clears it; normal configuration
consumes it before revalidating live grant/fault/temp/PM gates. It is separate
from the one-per-binding unexpected-program-loss recovery budget. The existing
poller runs the slow IIO work outside the TCPC source lock.

Declare PD_PPS among sm5714-usb standard USB types; this fixes enum8 warnings
without permitting ordinary switching during PPS. Host fixed gates use TCPM
ONLINE=1 and voltage/current/roles, not PPS-capability USB_TYPE. Active ONLINE=2
remains rejected after native fixed return.

Preserve the original Test336 runner/source/inputs and STOP. A next runner must
consume discovery's flat result and test real discovery/admission integration.
Build once using the existing passive/native cache, preserve exact Test331
config/DT and paired181 modules. Run affected suites only per latest owner scope;
no routing change/full suite/Actions/device operations.

Next physical proposal: Test337, same single pump-OFF PPS roundtrip and bounded
10s settle +30s ordinary charge +15s unplug, unconditional exact Test331 rollback.
First abnormal state stops; no pump/current advance or timeout relaxation.
