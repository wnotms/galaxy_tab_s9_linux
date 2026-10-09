# Test379 — stopped before deployment

Admission revision2 was committed/pushed as6fef507e before the fresh read-only
preflight. Battery100%,28.8°C,4.446V passed the amended observation gate; original
4.44V float setpoint unchanged. Identity, authenticated Wi-Fi, allfive accepted
partition hashes and181 module files passed. Same boota1e7570f as enrollment.

Full kernel JSON contains one new priority3 DWC3 ep0out not-queued request
at source11463.272981s relative to the enrolled Test378 restoration journal.
The no-new-error preflight therefore stopped. No candidate was installed, no
partition/rootfs/config was written, no reboot/ADSP/RPC/proxy started. Test379
is STOP, not sensor acceptance; physical attempt count0. Full raw log and exact
row are retained.

Pinned FunctionFS/DWC3 source explains this message as dequeue of an ep0 request
absent from its lists during unbind (see docs/USB_EP0_TEARDOWN_AUDIT.md). That
source evidence does not retroactively pass this preflight or prove every USB
failure harmless. ADB and Wi-Fi had recovered before the read. A later independent
registration may enroll this exact existing row with its cursor and complete
journal; any additional error after that baseline still stops. No future waiver
and no modification of USB logic is authorized by that enrollment.

Result recording executed:false; reuse117 affected checks from VALIDATION.json,
unchanged ARM64 RPC and accepted Test370 kernel/build. No full regression or CI.
SSC/accelerometer/automatic rotation remain incomplete.
