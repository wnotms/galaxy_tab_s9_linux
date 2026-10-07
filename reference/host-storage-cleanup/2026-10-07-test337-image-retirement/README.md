# Test337 expired Windows-image retirement

Latest completed test337 sets the Test328–Test337 retention window.
Two verified, unused Windows Test327 boot copies were removed:192 MiB of
logical files. This is not a measured filesystem-free-space increase.

Canonical Test327-origin Image/boot remain because the same exact files are
still candidate/rollback consumers attributed to in-window Test328/Test330.
Their consumer paths and hashes are recorded, not treated as a permanent
exception. Current331/323/337 runtime/qualified providers and original evidence
remain. Nonimage expired-stage files retained; no device action or test rerun.
