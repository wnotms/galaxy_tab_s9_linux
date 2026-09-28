# Test253 attempt04: adopted; fresh preflight passed

The owner explicitly adopted the proposed scheme ("使用新方案"). Registration
and33 focused host checks were committed/pushed at dcb46833 before this fresh
read-only preflight. Existing final1124-test all-suite validation still covers
the unchanged host implementation; no device software or host backend changed.

Fresh Wi-Fi and real native USB snapshots confirm boot461c1408e42643afae5b48162771d077,
PID834 and custom daemon053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5.
Full five-partition/embedded-config/notes/181 candidate/181 original module
identity passed, with DCC absent, protected settings unchanged and no new kernel
fault, failed unit or Code43. Native ADB, bound NCM banner/authenticated SSH and
Wi-Fi SSH passed. Fresh evidence is in preflight-adopted/.

Cycle01 subsequently passed the adopted cable-recovery gate:37.058s observed
offline lower bound,14.100s native/NCM recovery upper bound and155.487s elapsed
responsive observation. Native shell passed first attempt; NCM attempt01 timed
out8s and attempt02 recovered, retained as a bounded recovery transient. One
exact contextual pre-enable DISABLE W completed ENABLE/worker within the adopted
limits. Full post-cycle five partitions/config/notes/181+181/DCC/protected
settings/daemon/failed-unit/kernel/ADB/NCM/Wi-Fi checks pass without a new
CPU/kernel fault or Code43. Read cycle01 raw journals/verdict/audit/results.

Series remains in progress:1/3 performed and accepted; cycle02/03 and full final
series acceptance are pending. No device/host-server restart, reset, software
change or reboot occurred. This bounded acceptance records the NCM transient;
it is not a claim of three strictly transient-free cycles. Test252 and prior
Test253 stopped attempts stay stopped.
