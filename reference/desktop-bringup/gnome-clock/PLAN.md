# Independent Debian clock repair after Test370 acceptance

Owner reports desktop/keys/touch pass but wrong time. Test370 kernel/input scope
is complete and archived before this separate runtime change. Same current boot
0cdf0b75-9334-46bb-adcf-8e2ea97c3517, Wi-Fi10.49.219.42, USB unplugged by owner.
Shanghai timezone is already correct. Date is September30 while trusted host
and clock tool agree October9. CanNTP=no, NTP=no, synchronized=no; timesyncd is
absent. No working RTC date is claimed.

Debian package simulation: install only systemd-timesyncd257.13-1~deb13u1,
matching existing systemd/libsystemd-shared; zero upgrades/removals. Use the
already configured Debian trixie mirror, no third-party package or full upgrade.

1. Require same enrolled machine/current boot and save original raw time evidence.
2. Set system wall time from current host epoch; keep Shanghai timezone.
3. Install this exact timesyncd version with --no-remove, bounded network retry.
4. Enable standard network time, then inspect service, synchronization and offset
   against host. Distinguish correct current clock from successful NTP response.
5. Record package/service enabled state, same boot and existing GNOME/SSH/input
   health. No reboot, RTC-register operation, kernel/modules/DT, USB/ADB, PD,
   charging policy, sensor start or hardware diagnostic.

No custom permanent time daemon/helper. Future Debian GNOME provisioning should
include standard systemd-timesyncd. Original kernel journal timestamps remain
unchanged; boot IDs/monotonic source fields retain attribution across the wall
clock correction. Do not relabel unsynchronized time as synchronized.
