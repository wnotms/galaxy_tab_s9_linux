# Rollback — vendor_boot restored to the pre-test image

Performed 2026-09-26T17:38:19Z, after the elevated-rate observation in
README.md §5a made it wrong to leave the profile on the tablet.

## The image was verified at three points before the write

```
$ sha256sum .work/test-227/vendor_boot-device-before.img   # the backup I pulled earlier
49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9
$ sha256sum /tmp/vb-rollback.img                       # after pushing to the device
49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9
```

## The write, with read-back

```
$ dd if=/tmp/vb-rollback.img of=/dev/sda24 bs=1M
100663296 bytes (101 MB, 96 MiB) copied, 0.355678 s, 283 MB/s
$ sync; sha256sum /dev/sda24
49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9  /dev/sda24
```

## All five partitions at the pre-test state

```
boot        71e194a528d37358  (unchanged throughout)
vendor_boot 49ae21b333f953e8  (was 1245bb39 during the test, now restored)
init_boot   1a8c71487d30bf39  (unchanged throughout)
dtbo        c17418be08365c03  (unchanged throughout)
vbmeta      9844859b45716a2a  (never written)
```

The tablet is byte-for-byte in the configuration it was in before test-227.
Nothing was repartitioned, no bootloader/recovery/userdata was touched, and no
rollback required a recovery boot.

## Confirmed in effect after a reboot

A reboot was issued so the revert could be proven rather than assumed, and the
running kernel was re-checked. This matters because `/proc/cmdline` still showed
`cpuidle.off=1` immediately after the write — correctly, since it reports the
**running** kernel's command line, which came from RAM and predates the write.
The partition content is what the *next* boot uses, and that is what changed.

| check | during the test | after the revert |
|---|---|---|
| `cpuidle.off=1` on `/proc/cmdline` | present | **absent** |
| `current_driver` | absent (framework off) | **`psci_idle`** |
| `cpuidle: using governor` | 0 | **1** |
| cluster state usage | 0 / 0 | **449 / 1246** |
| failed units | 0 | 0 |
| panel | connected | connected |

The last row is the substantive one: the deep cluster idle states are being
entered again, at a rate of roughly 1 700 entries in 40 s. The tablet is back on
the pre-test configuration in behaviour as well as in bytes.
