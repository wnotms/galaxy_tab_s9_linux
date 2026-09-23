// SPDX-License-Identifier: GPL-2.0
/*
 * Tiny PID 1 trampoline used only by gts9_minimal_rootfs=1.
 *
 * BusyBox switch_root execs its requested init after moving the root. This
 * trampoline then execs Debian's /sbin/init. If that exec fails, it reports
 * the failure and keeps PID 1 alive while offering the copied static BusyBox
 * rescue shell from /run.
 *
 * Built freestanding for aarch64; no libc or dynamic linker is needed.
 */
#define SYS_openat   56
#define SYS_close    57
#define SYS_write    64
#define SYS_nanosleep 101
#define SYS_setsid   157
#define SYS_execve   221
#define SYS_clone    220
#define SYS_wait4    260
#define SYS_dup3     24

#define AT_FDCWD (-100)
#define O_WRONLY 1
#define O_RDWR   2
#define O_NONBLOCK 04000
#define SIGCHLD 17
#define TIOCSCTTY 0x540e
#define SYS_ioctl 29

static long sys_call6(long n, long a, long b, long c, long d, long e, long f)
{
	register long x0 asm("x0") = a;
	register long x1 asm("x1") = b;
	register long x2 asm("x2") = c;
	register long x3 asm("x3") = d;
	register long x4 asm("x4") = e;
	register long x5 asm("x5") = f;
	register long x8 asm("x8") = n;

	asm volatile("svc #0"
		     : "+r"(x0)
		     : "r"(x1), "r"(x2), "r"(x3), "r"(x4), "r"(x5), "r"(x8)
		     : "memory", "x6", "x7", "x9", "x10", "x11", "x12",
		       "x13", "x14", "x15", "x16", "x17", "x18");
	return x0;
}

static long sys_write(long fd, const char *data, long length)
{
	return sys_call6(SYS_write, fd, (long)data, length, 0, 0, 0);
}

static void write_path(const char *path, const char *data, long length)
{
	long fd = sys_call6(SYS_openat, AT_FDCWD, (long)path,
			    O_WRONLY | O_NONBLOCK, 0, 0, 0);

	if (fd >= 0) {
		sys_write(fd, data, length);
		sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
	}
}

static void emit(const char *message, long length)
{
	sys_write(2, message, length);
	write_path("/dev/console", message, length);
	write_path("/dev/tty1", message, length);
}

static void sleep_one_second(void)
{
	struct timespec {
		long seconds;
		long nanoseconds;
	} delay = { 1, 0 };

	sys_call6(SYS_nanosleep, (long)&delay, 0, 0, 0, 0, 0);
}

__attribute__((noreturn)) static void rescue_loop(void)
{
	static const char command[] =
		"echo 'check: cat /proc/partitions; ls -l /sys/class/block; ls -l /dev/mmcblk*'; "
		"cat /proc/partitions; ls -l /sys/class/block; ls -l /dev/mmcblk*; "
		"echo 'GTS9 minimal root rescue shell'; "
		"exec /run/busybox sh -i";
	static char *argv[] = {
		"busybox", "sh", "-c", (char *)command, 0
	};
	static char *envp[] = {
		"PATH=/run:/sbin:/bin:/usr/sbin:/usr/bin",
		"HOME=/root",
		"TERM=linux",
		"PS1=gts9-rescue# ",
		0
	};

	for (;;) {
		long pid = sys_call6(SYS_clone, SIGCHLD, 0, 0, 0, 0, 0);

		if (pid == 0) {
			long console;

			sys_call6(SYS_setsid, 0, 0, 0, 0, 0, 0);
			console = sys_call6(SYS_openat, AT_FDCWD,
					    (long)"/dev/console", O_RDWR, 0, 0, 0);
			if (console >= 0) {
				sys_call6(SYS_ioctl, console, TIOCSCTTY, 0, 0, 0, 0);
				sys_call6(SYS_dup3, console, 0, 0, 0, 0, 0);
				sys_call6(SYS_dup3, console, 1, 0, 0, 0, 0);
				sys_call6(SYS_dup3, console, 2, 0, 0, 0, 0);
				if (console > 2)
					sys_call6(SYS_close, console, 0, 0, 0, 0, 0);
			}
			sys_call6(SYS_execve,
				  (long)"/run/busybox",
				  (long)argv, (long)envp, 0, 0, 0);
			for (;;)
				sleep_one_second();
		}

		if (pid > 0) {
			long status;

			while (sys_call6(SYS_wait4, pid, (long)&status, 0,
					 0, 0, 0) < 0)
				sleep_one_second();
		} else {
			sleep_one_second();
		}
	}
}

__attribute__((noreturn, used)) void gts9_start(void)
{
	static const char failure[] =
		"GTS9_MINIMAL_FAIL=switch-root-returned\n";
	static const char rescue[] =
		"GTS9_MINIMAL_RESCUE=BusyBox shell; root init exec failed\n";
	static const char kmsg_failure[] =
		"gts9-minimal-pid1: GTS9_MINIMAL_FAIL=switch-root-returned\n";

	sys_call6(SYS_execve, (long)"/sbin/init", (long)(char *[]){
		"/sbin/init", 0
	}, (long)(char *[]){
		"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
		"HOME=/root", "TERM=linux", 0
	}, 0, 0, 0);
	write_path("/dev/kmsg", kmsg_failure, sizeof(kmsg_failure) - 1);
	emit(failure, sizeof(failure) - 1);
	emit(rescue, sizeof(rescue) - 1);
	rescue_loop();
}

__attribute__((naked)) void _start(void)
{
	asm volatile("bl gts9_start\n"
		     "1: wfe\n"
		     "b 1b\n");
}
