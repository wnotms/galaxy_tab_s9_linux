# Restore — production kernel returned, confirmed in behaviour

Performed 2026-09-26T20:28:23Z. The CSD instrument was removed after the
wedge was captured, so the tablet is not left running a diagnostic kernel.

## Bytes

```
$ dd if=/tmp/boot-before.img        of=/dev/disk/by-partlabel/boot        bs=1M
$ dd if=/tmp/vendor_boot-before.img of=/dev/disk/by-partlabel/vendor_boot bs=1M
$ sync; sha256sum /dev/disk/by-partlabel/boot /dev/disk/by-partlabel/vendor_boot
71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d  boot
49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9  vendor_boot
```

Both match the pre-test state exactly. \ and \ were never
written and still read 1a8c7148 / c17418be.

## Behaviour, after a reboot

| check | during the test | after the restore |
|---|---|---|
| \ on /proc/cmdline | present | **0** |
| /sys/module/smp/parameters/ | csd_lock_timeout, panic_on_ipistall | **empty** |
| ^cpuidle/current_driver | (unchanged) | psci_idle |
| CPUs online | 0-7 | 0-7 |
| failed units | 0 | 0 |
| panel | connected | connected |

The emptied parameters directory is the substantive row: it is the same
capability test the arming gate used, now showing the diagnostic kernel is
gone. The tablet is back on the production configuration in bytes and in
behaviour, and no recovery boot, vbmeta write or repartition was needed.

## Note for the next run

\ on the tablet is tmpfs and is cleared by a reboot — the first restore
attempt found the staged images gone. The host-side copies in
\ are the authority and were pushed back before writing.
