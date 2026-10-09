# Test368 — STOP in read-only preflight

Registration0d9e2e35 was committed and pushed. The sole preflight captured the
same original Test331 boot78ec1906,94%,30.5°C,Good/discharging,VBAT4.279V,
GNOME/SSH/adbd/gadget services active. No kernel/config/notes identity change.

Full kernel JSON revealed five new BW_PERF_VOTE timeout/late-response pairs:
seq3296 at42953.063909s,166 at43023.459805s,249 at43029.187649s,
3587 at43213.850918s and883 at43263.110242s (kernel source monotonic).
The prior two GMU pairs and both archived ep0 diagnostics remain retained.
The new pairs did not match the frozen preflight error counts; first-failure
was saved and the runner stopped before ownership/install/Windows stages.
No new overlay, unit start, UDC write, flash, reboot, modules, firmware, DT,
charging/adbd change, PPS or pump. No rollback needed. No physical cable cycle.

Test368 is STOP, not USB acceptance. Do not retry or enlarge old error counts
to hide the observed recurrence. The53 affected host tests remain a local
qualification, not hardware success. Source-bounded ep0 classification was
not exercised on hardware in this scope. No kernel build/full regression/CI.

GPU communications failed while GNOME/Wi-Fi remained responsive. This does not
prove CPU wedge, USB causality or harmlessness of all GPU errors. Preserve the
new source-timestamped evidence and compare the same-model Fedora GPU/firmware
and pinned mainline HFI implementation before choosing the next physical scope.
SSC sensors/rotation, native Escape deployment and persistent USB qualification
remain unfinished; ordinary charging caps and user graphical endpoint remain.
