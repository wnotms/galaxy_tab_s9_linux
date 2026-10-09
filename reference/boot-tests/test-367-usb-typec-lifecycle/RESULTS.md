# Test367 — STOP on the first new ep0 teardown diagnostic

Registration/source commit f257a20c was pushed before installation. Read-only
preflight passed on unchanged Test331 boot78ec1906:96%,29.5°C,VBAT4.297V,
discharging, Good, GNOME/adbd/SSH active, no failed unit. Full existing kernel
journal/error counts were retained, including unresolved GMU errors and the
earlier manual-rebind ep0 message. No claim that this was a clean kernel boot.

Three verified, initially absent userspace files were installed with a durable
ledger. The transient unit started once. After1s stable physical-detached state,
the helper performed exactly one unbind. The kernel emitted a new priority3
message at source monotonic42552.324630s:

`dwc3-qcom a600000.usb: request 00000000f31e7287 was not queued to ep0out`

The runner preserved first-failure.json before cleanup. **Test367 is STOP**, not
passed, and will not restart. No owner reconnect or physical cable cycle ran.
The unit was stopped, its own original-controller binding restored, and all
three payload files removed after exact hash/mode/owner checks. Restored raw
journal/state show same boot, UDCa600000.usb, GNOME/SSH/adbd/original gadget
service active, battery96%, no kernel/config/modules/partition/firmware or
charging/adbd changes. No reboot, flash, PPS or pump. Runtime ledger remains
marked rolled_back; initially absent payloads are again absent.

Post-stop read-only footprint also found a14579byte Python3.13 cache produced
by the runner's SourceFileLoader import. This was an **extra generated file**,
not one of the three registered payloads. Raw metadata and exact compiled-code
comparison with frozen helper source prove ownership: filename matches the
new helper, header source size8923, mtime1791515288, code equality true, SHA256
079ac4cf346a0f501aa38ee012c3f1e33436fdbd23e826a666347f26a39decbe.
This prevents claiming exact complete rootfs rollback yet. Registered cleanup:
on exact same boot and inactive transient unit, recheck this exact file/hash,
magic/header and frozen compiled-code equality, then delete only this cache.
Do not remove other caches or parent directories. Save post-delete readback.
Future runner must load frozen helper without generating bytecode.

61 affected host tests PASS/0skip; syntax PASS. No build, full regression or
Actions executed; no kernel inputs changed. Host tests did not predict this
real DWC3 message. Native Escape remains compiled/not deployed and interim
XKB/GNOME preserved. USB persistent fix, SSC sensors and full port remain open.

Pinned source now identifies a relevant path: configfs unbind removes functions,
FunctionFS unconditionally dequeues its ep0 request before freeing it; DWC3 logs
this exact error and returns-EINVAL if the request is on none of its lists.
This explains a plausible teardown diagnostic, but does not change this STOP
or establish that all ep0 errors are harmless. Before another independent scope,
record source evidence and decide a tightly bounded classification based on
owned teardown events and actual transport recovery. Do not silence kernel
logging or weaken unknown-error/CPU/USB safety gates merely to advance SSC.
