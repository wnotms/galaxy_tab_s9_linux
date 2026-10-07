# Test341 — observer STOP before activation, rollback pending

The OFF/unbound guardian stopped while the owner changed PC to C1. Primary and cleanup both report `pre-entry ordinary source limit`. Its 97 successful samples include normal offline detach; the rejected sample was checked before emission and is missing. Preserve that limitation: exact triggering tuple is not proven.

Full same-boot kernel journal shows145.351347s detach,150.094937s implicit TCPM5V/3A budget,150.122292s ordinary charger input1.8A,150.291211s5V/0.5A,150.440276s9V/1.5A. The observer requires advertised5V budget<=1.8A as well as actual input<=1.8A; that rejects a legitimate3A source capability. It must separate source capability from SM5714 input programming. No evidence of actual input3A or pump operation.

After owner reply, the marker script refused a finished guardian before writing activate.json. No bind, lease, PPS request, entry or pump start; sole kernel attempt was never activated. Later sameboot read proves unbound/OFF, ordinary fixed9/1.5A, healthy70%/4.161V/28.5°C and +1.923A battery current. ADC is disabled; its stale9267mV value is not a physical measurement. No classified CPU fault. Preserve primary/cleanup errors separately, no341 restart/replay. Await owner PC return for registered exact331 restoration.

Next independent host-only correction should allow known5V Type-C source capability<=3A while retaining actual ordinary input<=1.8A, strict9V source/input<=1.5A and all post-entry fallback gates. Always emit the raw preparation sample before validation, including rejected samples. No kernel/driver/thermal/current-limit change, rebuild or new pump/current scope implied.
