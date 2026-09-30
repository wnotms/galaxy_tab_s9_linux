# Test258 stopped during deployment preparation

Verdict: STOP before candidate boot/vendor_boot writes or current-module rename.
The candidate was not installed or booted. The150s passive observation did not
start; passive hardware/ADC acceptance remains unexecuted, active Stage3 NOT READY.

Registration f3a266b5 preceded the single ordinary accepted-baseline reboot.
Boot c1716879 became d377c437; normal command line and18 identity/rescue gates
passed. The earlier host-only UUID normalization assertion is preserved and
sent no reboot. Candidate source f3a266b5 build/artifact/bundle qualification and
1264 full host tests were reused; no rebuild/full rerun after result commits.

TWRP99dc656e verified baseline five partitions, microSD identity/current181
modules, battery and staged files. Installation created only the new temporary
.gts9-test258-stage slot and extracted the archive. The archive is rooted at
7.2.0-rc3-gts9wifi-dirty/, while the borrowed helper expected
lib/modules/7.2.0-rc3-gts9wifi-dirty/. Candidate-directory verification refused
before current-directory rename or either image write. This is a host packaging
integration failure, not a measured TCPC/SM5440 hardware failure.

Post-stop TWRP inspection proved all five partitions and181 original modules
unchanged, with no .gts9-test258-original/tested directory. The extraction slot
was removed, root unmounted and the temporary recovery BCB cleared. A first
cleanup guard incorrectly assumed usr/lib prefix and refused before mutation;
the actual release-root slot was then verified/removed. Raw od compresses
repeated zero lines as '*'; its zero BCB output is retained. No restore image or
module replacement was needed because the accepted pair remained installed.

Ordinary accepted Test255 returned on0456f42317a1471c90d5d0b90d4a027c.
Its exact config/notes, normal cmdline, absent DCC/candidate supply/temporary
slots, Sink/Device role, battery Good28.9C, no failed unit/new kernel fault,
ADB/NCM and Windows no-Code43 were recorded. Wi-Fi obtained10.191.121.119,
but the first SSH attempt and one bounded read-only diagnostic retry failed
(No route to host). This remains unresolved; no all-transports pass is claimed.
No USB/Wi-Fi/rootfs/charging configuration was changed to bypass it.

Owner-requested reduced-check workflow is in AGENT.md/HOST_TEST_WORKFLOW.md:
qualify source/artifacts once, use scoped tests for runner changes, record
executed:false for documentation/results-only work, combine telemetry and
incremental journal checks during observation. Identity/rescue/rollback/safety
and write-readback gates remain. This result commit ran no build/full regression.
Full original journals and command/timing records remain under install,
install-stop-recovery and returned-baseline; PHYSICAL_SHA256.json seals them.

Next: fix archive-layout integration offline and use actual-archive host
transaction tests. Do not rerun this stopped attempt or automatically deploy
another candidate. Future passive deployment must use a fresh registration and
working rescue preflight. No PPS, pump activation or current increase occurred.
