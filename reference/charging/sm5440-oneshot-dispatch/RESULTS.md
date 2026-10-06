# Complete scoped startup dispatch — offline qualified

Sourcef338eeb3 repairs the second genericfault check which still usedPC5V only
inTest325. Both initialentry and tailfaultpreservation now admit the same isolated
fixed9V OFF initialREVBLK context. Confirmation matcher still requires two new
clean sameclass/control samples,5s bound, zeroIBUS, VBAT<4.3/die<42. The tail never
clears a previously latchedfault; repeated/live faults remain terminal. Only the
ONESHOT diagnostic branch differs, no ordinarypredicate/converter/PM/policy change.

Actual full worker and unchanged mockedI2Cfixture replayed Test325 exactly:
pre-fix two expected positive cases failed fault1/pending2, matchinghardware.
Corrected worker reaches pending2 ->pending1 ->native callback once. Thirteen
success/fault/detach/control/temperature/voltage/current/I2C/suspend/deadline paths
in six new tests; native callback mocked, not hardwareADC/grant. First minimal
fixture context compilation failures retained. No old tests changed/removed.
88affected worker/predicate/passive/rearm/native/converter/startupgauge testsPASS,
0skip,1.587s. Other unaffected158-test baseline coverage reused; no all-suite run.

ARM64Image/DTB/181modules PASS81.920s incremental samecache, W1/sparse PASS13.290s
no warnings; normalobjectflags restored/exactqualifiedobject retained/noformal
relink. Config byte-identical Test325; accepted323 onlyONESHOT absent->y. DTB
exactaccepted323,59protected sources/37formal baseline files preserved,181exact
modulefiles/runtime sections+symbols checked (debug/BTF changes recorded). Exact
Linux7.2-rc3/DCCn/container/SM5714/ADC5 and all charging/thermal/current limits
unchanged. Offline boot-only package unpacked/hashsealed, exact323 rollback.

No physicaloperation for this qualification. NewTest326 also repairs duplicate
producer closing marker and retains originalTest325stop/raw. Register/push before
single new candidateboot. No PPS/ON/nativeactuator/charging authority. READY for
new pump-OFF ADC observation only; fullportNOT_READY/calibration/current/OCP/
PPS/cutoff/faultPM/higher-power acceptance remain incomplete.
