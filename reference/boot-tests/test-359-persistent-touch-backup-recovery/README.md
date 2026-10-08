# Test359 — persistent desktop touch after recorded backup recovery

Independent scope after358 zero-write STOP. Same331 boot/Test357 already loaded
module, same SHA-bound payload and all loader gates,17 host tests reused. GDM
Wants-only optional integration; no paired181-dir/config/DT/USB/charging change.

Require exactly the recorded dpkg-db-backup.service start-limit-hit and
ExecMainStatus=0. Acknowledge only that one state, then start its ordinary backup
once; require Result=success/status0 and empty failed units before installing.
Do not disable/mask timer, change RTC/NTP/clocks, reset other failures or retry.
The rapid-trigger/time-discrepancy cause remains unproven and original358 raw
is retained. Current daily timer/realtime/monotonic were normal in diagnostics.

Then install3 absent owned files, daemon-reload/enable/start one optional touch
unit. Require already-loaded/zero-insmod, sameboot/healthy battery/GDM/SSH,
unchanged persistent GDM masks/no new kernel fault or failed unit. Stop first
anomaly; no forced unload/rail cycle/flash/reboot. Remove only owned component
files/enable-link to roll back; current live driver remains loaded. Future
boot/GDM-triggered load is untested; do not claim reboot-persistence acceptance.

Latest10-number historical window350–359. No images/build tree created; active
3481200s candidate/provider and current331 production/rollback still consumed
and preserved. Grantunused; futurefreshdesktopinactive admission/finalTWRP.
No new host regression/kernel build/routing/CI for unchanged loader; syntax
review of the registered prerequisite and one actual backup verify are scoped.
