# Debian adbd FunctionFS reconnect repair

Only userspace adbd34.0.5-12 is rebuilt. Linux, DTB, module files, USB gadget,
NCM addresses, SSH configuration and charge policy are not build inputs here.

Test252 captured an exited USB worker, a sleeping monitor in transport cleanup,
and persistent host offline while both SSH channels worked. Debian's
[reconnect issue54](https://salsa.debian.org/android-tools-team/admin/-/issues/54)
describes the same two implementation problems. The original StopWorker waits
for pthread_kill(thread,0) to return ESRCH; modern glibc returns0 for a terminated
but unjoined thread. A source-extracted host test reproduces that wait, and the
patched actual methods use scope-guarded completion and explicitly wake/stop
the worker before joining, including an initial read-submission failure.

ep0 now remains owned by the daemon across connections. A connection gets its
own duplicate; reopening bulk endpoints duplicates the retained control fd and
does not rewrite active descriptors. Binding state comes from actual BIND and
UNBIND events and survives DISABLE/transport cleanup. A reconnect can therefore
accept ENABLE without waiting for another BIND. Initial ENABLE without a real
BIND, and duplicate ENABLE, remain rejected. No UDC write or gadget reset is
introduced. Existing no_disconnect mount, external holder and live-restart
ExecCondition remain as safeguards, including the packaged-binary fallback.

```
bash scripts/build-adbd-reconnect.sh
```

The host-only build pins Debian source checksums and the Debian trixie container
base digest, applies the Debian patch series, then the local two-file patch.
No OpenPGP signature-validation claim is made. Builder package versions,
ELF dependencies/symbol versions and a hash manifest are retained under
`out/adbd-reconnect/`. The script neither installs nor contacts a device.

For a registered physical test, install the exact verified binary separately
as `/usr/local/libexec/gts9-adbd-reconnect`. The service runs gts9-adbd-run,
which prefers that executable and otherwise preserves packaged adbd. Stage
the unit/helper for the next normal boot; do not bypass ExecCondition or stop,
restart, unbind or rebuild the live shared gadget. Package files remain intact.

The source-baseline fixtures are the exact Debian-patched USB sources and
Android scopeguard header used to compile behavioral host tests. Their upstream
copyright/license notices and Apache2.0 NOTICE are retained. They are not a
second daemon build source or proof of real USB enumeration. Test253 separately
registers and records physical verification; stopped Test252 is not reclassified.
