# Test254 attempt01 stopped before deployment

Candidate boot packaging/layout and complete matched-module install/restore
rehearsal passed. Boot SHA ea73e65836ab316af658ed53273be0ec6351b335750978095e509054164509f7.
Read-only Test252 config/notes/five partitions/181+181 files and Test253 protected
userspace matched on boot461c1408e42643afae5b48162771d077. No kernel fault or failed unit.

Initial Windows capture showed ProblemCode43 at USB\VID_0000&PID_0002\6&109510F2&0&1;
ADB empty and device UDC default/NCM down. This rescue precondition stopped the
attempt before any agent reboot, file transfer to the device, partition or module
write. This is not a failed Test254 kernel boot: the candidate was never deployed.

Supplemental Windows state probe timed out, PnP event query exited1, and subsequent
properties showed the NCM interface up. Device Wi-Fi became unreachable during
the owner's manual reboot. Native ADB returned on64716d74b79844ac859b8d25e9b7f318,
Wi-Fi10.191.121.167, still exact Test252 config/notes/five partitions. The owner
confirmed manual reboot; old full journal ends in ordered systemd reboot/shutdown.
The identity change is explained, not evidence of an automatic CPU wedge reboot.
Code43 attribution/cause is not established and remains separately recorded.

Preserve this stopped result. A new authorized attempt requires its own fresh
complete USB/identity preflight and pushed registration. No USB/adbd workaround,
diagnostic change, Stage2/3 or charging experiment occurred.

Host wrapper changed --base HEAD~1 executed all1148 retained tests (98.092s test
time), zero failures/errors/skips. Command exit0. A postprocessing attempt to copy
an implicit JSON report failed because the wrapper does not create that file;
raw test log and derived changed-summary are preserved, no stale report copied.
The host syncfs qualification remains the recorded real repo+/tmp flush; no device
helper/test assertions changed.
