# Test297 — offline runtime snapshot qualification

OFFLINE_RUNTIME_SNAPSHOT_QUALIFIED, sourceeefef33f (implementationd352deb4).
119 affected SM5714 tests pass in4.399s, including actual-C threaded teardown,
provider references, source/budget transitions, property failures and zeroed
refusals. Existing fixed-PD tests retained. Initial ARM64 build identified a
`current` macro collision; corrected parameter and added kernel macro to fixture.
Both initial failure and final successful output remain in validation/.

Final standard ARM64 ccache passive build66.85s PASS. Changed TCPC object W=1/
sparse PASS and byte-identical to linked object; no driver warning. One unrelated
upstream vDSO sparse warning recorded, no external cleanup. Exact296 embedded
config/DTB bytes, protected96inputs/compiled overlays and181paired modules pass
artifact audit. Module archive must remain paired with the new Image. Linux pin,
HVC_DCC=n, Test254 config and Stage1/2 limits unchanged.

Kernel-only lifetime-pinned standard TCPM/source/fixed callback observation;
0400 debugfs calls the actual API. Not an atomic TCPM state transaction, physical
voltage measurement, activation or charging grant. LinuxTCPM core/SM5440/DT/config/
USB/ADB/roles/current/float/thermal unchanged. Old SM5440 startup refusal remains
unresolved, and PPS/active pump remain disabled.

Full regression executed:false under current owner scope; reuse unchanged294
qualification, no routing changes/Actions. No physical operations in Test297.
Next separately register one short Test298 runtime read/device endpoint/263
rollback. Full charging-port goal remains active; Stage3 active NOT READY.
