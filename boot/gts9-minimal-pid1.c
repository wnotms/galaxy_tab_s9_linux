// SPDX-License-Identifier: GPL-2.0
/*
 * Tiny PID 1 trampoline used only by gts9_minimal_rootfs=1.
 *
 * BusyBox switch_root execs its requested init after moving the root. This
 * trampoline then execs Debian's /sbin/init. If that exec fails, it reports
 * the failure and keeps PID 1 alive while offering the copied static BusyBox
 * rescue shell from /run.
 *
 * It is also the last place that can leave evidence on the disk when nothing
 * else can: after switch_root the Debian root is mounted read-write, but the
 * panel may be dark and there may be no USB console at all.  Before exec'ing
 * init it appends to the persistent record
 *
 *	/var/log/gts9-minimal-last-boot
 *
 * the markers `trampoline=entered`, `trampoline=exec-init` and - if the exec
 * returns - `trampoline=exec-failed` plus the errno.  A forked watchdog then
 * appends `trampoline=alive-<n>s` together with the current `/proc/1/comm`,
 * which separates "the kernel died" from "systemd started but never reported".
 *
 * The record file is opened once and every marker goes through that
 * descriptor, so a later atomic replacement of the record by Debian
 * (write temp + rename) can never be clobbered by a late watchdog write.
 *
 * Built freestanding for aarch64; no libc or dynamic linker is needed.
 */
#define SYS_openat   56
#define SYS_close    57
#define SYS_read     63
#define SYS_write    64
#define SYS_nanosleep 101
#define SYS_setsid   157
#define SYS_execve   221
#define SYS_clone    220
#define SYS_wait4    260
#define SYS_dup3     24
#define SYS_ioctl    29

#define AT_FDCWD (-100)
#define O_WRONLY 1
#define O_RDWR   2
#define O_CREAT  0100
#define O_APPEND 02000
#define O_NONBLOCK 04000
#define SIGCHLD 17
#define TIOCSCTTY 0x540e

#define RECORD_PATH "/var/log/gts9-minimal-last-boot"

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

static long str_len(const char *text)
{
	long length = 0;

	while (text[length])
		length++;
	return length;
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

/*
 * The persistent record.  Opened once, on the Debian root filesystem, before
 * PID 1 is handed over.
 */
static long record_fd = -1;

static void record_open(void)
{
	record_fd = sys_call6(SYS_openat, AT_FDCWD, (long)RECORD_PATH,
			      O_WRONLY | O_APPEND | O_CREAT, 0644, 0, 0);
}

static void record_write(const char *text)
{
	if (record_fd >= 0)
		sys_write(record_fd, text, str_len(text));
	/* The kernel log is a second, independent copy while it exists. */
	write_path("/dev/kmsg", text, str_len(text));
}

static long read_file(const char *path, char *buffer, long size)
{
	long fd = sys_call6(SYS_openat, AT_FDCWD, (long)path, 0, 0, 0, 0);
	long got;

	if (fd < 0)
		return -1;
	got = sys_call6(SYS_read, fd, (long)buffer, size - 1, 0, 0, 0);
	sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
	if (got < 0)
		return -1;
	buffer[got] = '\0';
	while (got > 0 && (buffer[got - 1] == '\n' || buffer[got - 1] == '\r'))
		buffer[--got] = '\0';
	return got;
}

static void sleep_one_second(void)
{
	struct timespec {
		long seconds;
		long nanoseconds;
	} delay = { 1, 0 };

	sys_call6(SYS_nanosleep, (long)&delay, 0, 0, 0, 0, 0);
}

static void sleep_seconds(int seconds)
{
	int i;

	for (i = 0; i < seconds; i++)
		sleep_one_second();
}

static void number_to_text(long value, char *out)
{
	char digits[24];
	int count = 0;
	int negative = value < 0;
	unsigned long magnitude = negative ? (unsigned long)(-value) : (unsigned long)value;
	int i = 0;

	do {
		digits[count++] = (char)('0' + (magnitude % 10));
		magnitude /= 10;
	} while (magnitude && count < (int)sizeof(digits));

	if (negative)
		out[i++] = '-';
	while (count > 0)
		out[i++] = digits[--count];
	out[i] = '\0';
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

/*
 * Runs as an ordinary child of PID 1.  Its only job is to leave a trace on
 * the disk when nothing else can: the panel may be dark and the USB console
 * may never appear, but the record still says whether the kernel and PID 1
 * were alive, and which program PID 1 became.
 */
static void watchdog_loop(void)
{
	static const int checkpoints[] = { 30, 60, 90 };
	char buffer[64];
	char errno_text[24];
	int index;

	record_write("trampoline=watchdog-started\n");

	for (index = 0; index < (int)(sizeof(checkpoints) / sizeof(checkpoints[0])); index++) {
		int step = checkpoints[index] - (index ? checkpoints[index - 1] : 0);

		sleep_seconds(step);
		record_write("trampoline=alive-");
		number_to_text(checkpoints[index], errno_text);
		record_write(errno_text);
		record_write("s\n");
		record_write("trampoline=pid1 ");
		if (read_file("/proc/1/comm", buffer, sizeof(buffer)) > 0)
			record_write(buffer);
		else
			record_write("unreadable");
		record_write("\n");
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
	static const char marker_entered[] = "trampoline=entered\n";
	static const char marker_exec[] = "trampoline=exec-init\n";
	static const char marker_failed[] = "trampoline=exec-failed errno=";
	long error;
	char errno_text[24];

	record_open();
	record_write(marker_entered);

	/* Fork the watchdog before the exec: it must survive the handover. */
	if (sys_call6(SYS_clone, SIGCHLD, 0, 0, 0, 0, 0) == 0) {
		watchdog_loop();
		for (;;)
			sleep_one_second();
	}

	record_write(marker_exec);

	error = sys_call6(SYS_execve, (long)"/sbin/init", (long)(char *[]){
		"/sbin/init", 0
	}, (long)(char *[]){
		"PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
		"HOME=/root", "TERM=linux", 0
	}, 0, 0, 0);

	record_write(marker_failed);
	number_to_text(error, errno_text);
	record_write(errno_text);
	record_write("\n");
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
