// SPDX-License-Identifier: GPL-2.0
/*
 * Reboot the tablet into a named bootloader mode through reboot(2) RESTART2.
 *
 * busybox's reboot applet can only ask for a plain restart, and it is the
 * *string* that matters: the kernel's nvmem reboot-mode driver stores it in the
 * PMK8550 SDAM cell (pmk8550.dtsi: mode-recovery = <0x01>) and Samsung's ABL
 * reads that cell to pick the boot mode.  That is the difference between
 * powering off after a test and landing back in TWRP.
 *
 * Built freestanding for the initramfs: no libc, one syscall.  The mode is a
 * compile-time define so the builder can emit one binary per name.
 */
#ifndef GTS9_REBOOT_MODE
#define GTS9_REBOOT_MODE "recovery"
#endif

#define LINUX_REBOOT_MAGIC1 0xfee1dead
#define LINUX_REBOOT_MAGIC2 672274793
#define LINUX_REBOOT_CMD_RESTART2 0xa1b2c3d4
#define __NR_reboot 142

static const char mode[] = GTS9_REBOOT_MODE;

void _start(void)
{
	register long x0 __asm__("x0") = LINUX_REBOOT_MAGIC1;
	register long x1 __asm__("x1") = LINUX_REBOOT_MAGIC2;
	register long x2 __asm__("x2") = LINUX_REBOOT_CMD_RESTART2;
	register long x3 __asm__("x3") = (long)mode;
	register long x8 __asm__("x8") = __NR_reboot;

	__asm__ volatile("svc #0"
			 : "+r"(x0)
			 : "r"(x1), "r"(x2), "r"(x3), "r"(x8));

	for (;;)
		;
}
