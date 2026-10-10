# Native RPMSG diagnostic interface — offline only

After Test383's complete zero-loss trace found no DIAG channel through the
ordered RPC startup, source comparison found a usable AP-initiated route.
Linux7.2 `qcom_glink_create_chrdev` always registers an overridden rpmsg_ctrl
parent; native rpmsg_ctrl provides CREATE_EPT. Creating the character endpoint
alone does not open a channel: `rpmsg_eptdev_open` calls `rpmsg_create_ept`, and
GLINK's local-create path sends OPEN and waits for OPEN_ACK/remote OPEN (two
5-second kernel waits). This can query a channel not remotely advertised.
The current trace does not prove that X710 firmware supports this DIAG route.

Fedora X710 ab123e7d resolves RPMSG_CHAR=m and RPMSG_CTRL=m; our accepted kernel
has CHAR=y,CTRL=n. Its daemon/registry changes are already imported and Test383
still has no SSC400, so don't claim CTRL as SSC's root cause or rerun that profile.
The linux-msm/diag reference uses DIAG,DIAG_CNTL,DIAG_CMD but negotiates features
and sends masks. Only its DIAG channel name is used here; the router is not run.

Unmodified upstream control driver compiled as an external ARM64 module against
accepted Test370 provider. W=1 clean,32 imported symbol CRCs match. Config/notes/
provider inputs unchanged, no Image/DTB rebuild. SHA-256
4538faee7edee5153382cd2327e7da4b63651a70e34c56c0182685303c9f7154.
Loaded-module build-ID note is independently pinned for future runtime admission.
No module loaded, endpoint created, DIAG command sent or device altered.

One-shot helper has20 affected host tests PASS/no skips: UAPI bytes, forbidden
names, identity failure, stale ledger, create/open/read/evidence errors, duplicate
endpoint, destroy failure, same-FD cleanup, native EOF versus idle and progress
ledger saved before blocking open. Syntax passed. No full regression or CI.
The helper is not a registered deployment runner: future Test384 must bind the
plan to fresh boot/kernel/module/sysfs identity, impose15s, capture raw GLINK/
packet evidence and always restore370. No live module unload. No SSC/rotation
or decoded-DSP-log proof, PPS/pump/DCC remainOFF.
