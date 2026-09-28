# Adopted Test253 attempt02 registration

Owner adoption2026-09-28: "继续修复adb吧", in reply to the explicit attempt02
adoption question. This adopts the preserved proposal in README.md. The prior
Test253 preflight remains stopped and its seal is unchanged. No new daemon
variant or kernel change is introduced. All steps/limits in that proposal and
parent registration apply, including first-new-failure stop.

The unchanged shipped UPower unit is hash-pinned to
c6d300b60a7dd2e9186152b8bc4fd1557ec2977027d0a24b06304d31f6e4124c.
Only its established217/USER/PrivateUsers launch prerequisite failure is
recognized; no failed units after reboot is also allowed. It is not cleared or
fixed in this test. Any different/new failed unit stops the attempt. Six host
gate checks exercise this exception independently of the existing thirteen
thread/FD daemon checks. Original raw production-state reports keep their
failed-unit/identity_ok fields; supplementary classification never rewrites them.

Attempt02 read-only evidence is below preflight/. Only after registration and
local checks are pushed may staged hash-verified daemon/launcher/ExecStart be
installed for one normal boot, preserving the running daemon/gadget meanwhile.
Native transport must recover from one connected host reconnect and three
physical unplug/replug cycles, with source-bound NCM SSH and Wi-Fi evidence,
full journals,150s windows and≤60s recovery. Final identities repeat five
partitions,181 candidate/181 retained original module hashes and protected
NCM/SSH bytes. Stage2/3 and charging extensions remain out of scope.
