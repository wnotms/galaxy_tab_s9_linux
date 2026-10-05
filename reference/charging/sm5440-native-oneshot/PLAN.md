# Native one-shot acquisition — isolated OFF observation

Current production323 fixed5V1800/packnetpositive and fixed9V1500/float4440
remain frozen; no deployment until registration/qualification/rescue gates.
Full port requires actual current/cutoff/ADC/PPS acceptance, not just mocks.

New measured context MSK1..4=0 differs from stockC0/F7/18/F8 but does not prove
a historical cause. Additional ordinary323 control reads stayed0c with frozen
cached sampleage~872s, fault1/startup_pending1: they DO NOT prove ADC self-clear.
Cached last sample is old OFF UVLO/failed-startup-confirmation data, not live
calibrated measurement; ordinary SM5714 charging is a separate healthy path.

Previous continuous READY318 failed; RAW321transport passed without READY.
Samsung1053..1079 ONESHOT usesdisable20ms/RATE0/enable and200ms work scheduling;
continuous hasdifferent semantics. Fedora direct reads notper-conversionREADY.
Do not infer conversion time/guarantee or alter masks/bit2/100ms limit.

New isolated sm5440-adc-oneshot profile links the EXACT unchanged native
sm5440-conversion.c, withoutnativeactuator/controller/policy. Existing bound poll
worker afterhealthy startup runs once: source/pack admission, four native20ms
rearm + READY + checkedcleanup transactions, each realpack bracketed. Same
native100ms deadline, samefault/epoch/rawprecision. No long lock holds across
sleep/supplier. Heap evidence, copied underio_lock, generationpointerscleared.
Read-only oneshotdebugfile formatscopies, neverreplaysconverter; diagnostic does
not publishcached/fresh charging companion or rearmonsuspend/resume.

Writes: unchangedconverter ADC1 enable/rate/AVG andADC2channels withrestoration;
checkedmodeOFF only onerror. No mask/ENHIZ/OVP/current/protection/watchdog/Q4/PPS/
ON/DTS/TCPC/USB/adbd/rootfs/thermal/OPP changes. Four READY may prove only this OFF
software acquisition result, not calibrated/coherentcurrent/OCP/activecutoff.

Build uses existing passive308 cache after frozen323 formaloutputs; no newtree.
Tests actualCwrapper with fault/PM/source/pack/heapfail and existingnativeconverter,
oldpassive/diagnostic/config/profile dependencies. Fullsuite not rerun merely for
new isolated profile; affected directcoverage chosen perlatestownerworkflow.
Later Test324 should use fixed9V if5V UVLO startup remainslatched; firstfault stops
and exact323boot/181restore. No sourcecapability/currentraise/limitwaiver/oldtest
rewrite. Test323 success remains PCordinaryscope, not SM5440qualification.
