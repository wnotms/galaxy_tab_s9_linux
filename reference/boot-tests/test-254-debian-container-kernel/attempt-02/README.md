# Test254 attempt02: fresh connected-device deployment

Owner authorization remains “刷入测试”; owner confirmed the intervening reboot
was manual and that the tablet is now connected to the computer data port.
Attempt01 remains stopped before deployment, preserving Code43/incomplete rescue
evidence. Its previous journal demonstrates ordered shutdown; restored native
ADB sees a new boot with unchanged Test252 identities. Code43 cause is unresolved.

This independent attempt uses the same already validated candidate and the exact
acceptance order, limits, protected software, stop conditions and rollback in
[attempt01 registration](../attempt-01/README.md). No retry/result rewrite of that
stopped attempt. Recheck full identity and all three connected transports before
any TWRP transition or write; commit/push this registration first.

The candidate boot/modules and rollback are byte-identical to attempt01 packaging;
its original successful install/restore rehearsal and offline host1148-test result
are referenced, not falsely presented as newly executed tests. Newly copied tools
only select this attempt directory and current Wi-Fi DHCP address. No kernel
rebuild, USB/adbd change, rootfs connectivity workaround or Stage2/3.
