# STOP; offline recovery pending

One272candidate boot and one274observer load. First fresh call returned-110 in
108ms; zero usable facts. Observer stopped after one call, no retry. Then rmmod
command timed out20s, both fullkernel reads timed out25s, Wi-Fi SSH banner timeout.
Windows still enumerates ADB/NCM with Code0; this does not establish device health.
No final acceptance or complete30s window. No PPS/pumpON/current increase.

Owner requested to enter TWRP to collect persistent journal and restore exact263
boot+saved181modules; neither recovery nor rollback is confirmed yet. Current
deployment272 remains. Do not boot Debian/reload observer/repeat physical test.

Source review identified a real diagnostic lifetime defect: observer_thread exits
after STOP/completion, while observer_exit later calls kthread_stop on an unowned
task pointer. Pinned7.2 kernel/kthread.c documents caller lifetime responsibility.
This is an implementation bug regardless of whether persistent logs prove it
caused this loss. CPU stall/panic/Oops not yet proven; logs are unavailable.
Do not conflate fresh deadline refusal with subsequent unload transport failure.

All raw STOPs and startup/vbmeta host corrections remain immutable.16 local tests
and unchanged272/274 offline qualification reused, no results-only rebuild/full
run. ActiveStage3 NOT READY; next fix is diagnostic task lifetime, no ADC gate or
charging-policy relaxation.
