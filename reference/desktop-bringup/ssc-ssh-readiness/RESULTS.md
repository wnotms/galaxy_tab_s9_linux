# SSC boot WiFi readiness — host policy prepared, not deployed

Test364 candidate SSH had ConnectTimeout=3; the recorded first command ended
after3.015s during banner exchange. The failure boot had ADSP/FastRPC/native
SoCinfo, normal ADB/device NCM, ssh service, no failed units and no detected
kernel fault. Exact331 restored and authenticated WiFi passed. These facts
justify improving boot admission; they do not prove a specific route/ARP/
Windows process startup cause or retroactively pass Test364.

`userspace/sensors/ssh_readiness.py` adds a callback-only policy, no device
commands: at most3 authenticated probes within a registered budget (default
30s, never greater90s), checking full same-boot device identity/health before
each probe and after success. Only classified transient TCP/banner errors may
remain pending. Retain first error and recovery timing; wrong keys/auth/peer,
boot changes, health failures, unknown errors and late success stop immediately.
The helper is not yet integrated into a registered physical runner.

15 affected mocked tests passed/zero skips, including the exact Test364 error,
boot changes, identity/trust failure, lost health, exhausted attempts, deadline
and post-probe timeout. No kernel/build/routing change: build/full executed:false.
No new boot/flash/service/PPS/pump/current change.

Fresh read-only package inventory: none of libssc2, gts9-hexagonrpc, pd-mapper,
libprotobuf-c1, libqrtr1 is installed; iio-sensor-proxy is not-installed, no
fastrpc account and no conflicting runtime payload found. Inventory is separate
raw evidence under ssc-runtime-inventory.

Runtime planning also found **CONFIG_QCOM_PD_MAPPER=y**, standard Linux
qcom_pd_mapper.c already maps SM8550 ADSP root/sensor/audio domains to instance74
and adds tms/servreg for every domain. Stock adspr.jsn/adsps.jsn likewise specify
instance74. Prefer this existing native framework: do not start a second
userspace pd-mapper server just because Fedora packages it. This is source
comparison, not proof of a live kernel QMI response; verify native service
availability during the next registered SSC runtime test.

Next separately register bounded ADSP/SSC discovery, reuse exact native kernel/
firmware/181 qualification, install only required dependencies and gated runtime
units, map the already proven actual SMEM fields into copied prefix/socinfo,
create the normal fastrpc account, leave SDSP/userspace mapper/GDM inactive.
Prove accelerometer discovery and D-Bus first; only then enable the paired input
modules/desktop and request physical four-orientation confirmation. Rootfs
installation/removal and start/stop admission need their own transaction tests
before execution. No higher-power charging while this sensor scope is incomplete.
