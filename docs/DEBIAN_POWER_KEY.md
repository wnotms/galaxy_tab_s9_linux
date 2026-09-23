# Debian power-key behavior

The Qualcomm PMIC power key is both the suspend wake source and the tablet's
physical power button. The default `systemd-logind` action is `poweroff`, which
is unsuitable for this tablet: a short press while Debian is awake would shut
the system down.

Install the overlay on the Debian root filesystem so a short press suspends
the tablet and the next press wakes it:

```sh
sudo install -D -m 0644 \
  rootfs-overlay/etc/systemd/logind.conf.d/60-gts9-power-key.conf \
  /etc/systemd/logind.conf.d/60-gts9-power-key.conf
sudo reboot
```

This is a Debian userspace policy; it does not alter the kernel key driver or
the PMIC wake configuration. The rootfs overlay is not part of the initramfs
build. To restore the systemd default, remove this drop-in and reboot.
