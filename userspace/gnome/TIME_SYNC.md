# Debian desktop clock

Minimal rootfs images can lack a time client even when systemd-timedated exists.
An unset RTC then gives a wrong desktop date after boot. Provision Debian's
standard `systemd-timesyncd` package and enable network time:

The package is included in the GNOME package list for future provisioning.

```sh
apt-get install systemd-timesyncd
timedatectl set-ntp true
timedatectl status
timedatectl timesync-status
```

Use the owner's timezone; this device already uses Asia/Shanghai. If its date
is too old for repository metadata or TLS, bootstrap system time from a trusted
current clock before installing. Do not change RTC/PMIC drivers or charging
logic to correct a userspace clock. Check `NTPSynchronized=yes` separately from
service activation and preserve any failure evidence. No reboot is needed.
