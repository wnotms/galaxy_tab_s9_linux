# test-227 flash transcript — cpuidle.off=1 candidate

Date: 2026-09-26T17:23:10Z

## Write scope: vendor_boot ONLY

Transport: USB-NCM ssh (the tablet was running mainline Linux, not TWRP).
No COM port was required; adb saw no device and the harness's COM17/COM19 are absent.

## Backup first (verified byte-exact)

```
$ dd if=/dev/sda24 of=/tmp/vb-before.img bs=1M
100663296 bytes (101 MB, 96 MiB) copied, 0.345598 s, 291 MB/s
$ sha256sum /tmp/vb-before.img
49ae21b333f953e88de430cf7c4b66f1b45afa0503640c042746ba79fd1f44f9  /tmp/vb-before.img
```

Pulled to `.work/test-227/vendor_boot-device-before.img` and re-hashed on the host:
same hash. Rollback is a byte-for-byte restore of a file I hold.

## The candidate, verified on the device BEFORE writing

```
$ sha256sum /tmp/vb-candidate.img
1245bb39be1a6cfd65e381e44d19ce4ab29ca295f976f0c78067e4bfecc5b18a  /tmp/vb-candidate.img
$ grep -ao "console=tty0[^\\x00]*cpuidle[^\\x00]*" /tmp/vb-candidate.img | head -1
console=tty0 msm.separate_gpu_kms=1 cpuidle.off=1 panic=1...
```

The token was read out of the image **on the tablet**, not assumed from the build.

## The write, with read-back

```
$ dd if=/tmp/vb-candidate.img of=/dev/sda24 bs=1M
100663296 bytes (101 MB, 96 MiB) copied, 0.406379 s, 248 MB/s
$ sync; sha256sum /dev/sda24
1245bb39be1a6cfd65e381e44d19ce4ab29ca295f976f0c78067e4bfecc5b18a  /dev/sda24
```

## The other partitions, unchanged

```
boot       71e194a528d373580ee354bea1c0e68c2ff146d014ae34679955577b261d038d  (unchanged)
init_boot  1a8c71487d30bf39d635ff52893cce22efc0b9a81a6f4788edf47945843f78c0  (unchanged)
dtbo       c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  (unchanged)
vbmeta     9844859b45716a2a098c96cd38b15bb378e784dab34843d1edcd2704236d36e4  (NOT WRITTEN)
```

Exactly one partition changed, which is what makes this a one-variable test.
