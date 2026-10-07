# Offline development corrections

The first host extraction matched new C forward declarations instead of function
bodies. Restrict extraction to a definition with an opening brace. No kernel
behavior was changed to satisfy that harness. An owned-read fault test then
used its pre-change hard-coded third read; target the next actual read so the
additional pre/post-ON coherence observations remain exercised.

Final affected run284 tests passed/no skips. No old test was deleted or skipped;
boot-mode coverage expanded from8 to16 combinations. RealC entry/monitor/refresh/
cleanup/PM functions are extracted, including every entry I2C-refusal position.
No hardware execution was performed.
