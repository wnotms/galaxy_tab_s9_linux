// SPDX-License-Identifier: GPL-2.0
/*
 * Apply Samsung's existing RTC offset to the system clock, from the initramfs.
 *
 * Why this exists
 * ---------------
 * The PMK8550 RTC on this tablet counts from 1970 and is never set, so the
 * counter is about 56 years behind.  Android and TWRP show the correct time
 * because userspace adds an offset that Samsung's time daemon keeps in a file:
 *
 *	/persist/time/ats_2	8-byte signed little-endian milliseconds
 *
 * That file is the only place the offset lives.  It is not a PMIC SDAM cell, not
 * an NVMEM cell and not a UEFI variable, so mainline's rtc-pm8xxx offset support
 * - which expects a four-byte *seconds* cell from a hardware NVMEM provider -
 * cannot reach it.  docs/RTC_OFFSET.md carries the evidence.
 *
 * What this program does, and deliberately does not do
 * ---------------------------------------------------
 * It reads that file and sets CLOCK_REALTIME to
 *
 *	/sys/class/rtc/rtc0/since_epoch  +  ats_2 / 1000
 *
 * Two negative properties matter more than the arithmetic:
 *
 *   * it NEVER writes the PMIC RTC.  Nothing here opens an RTC device node for
 *     writing, so this cannot reach the SPMI write path that blocks this kernel
 *     uninterruptibly (docs/RTC_REPORT.md, tests 021-027).  The raw counter is
 *     left exactly as Android and TWRP expect to find it.
 *   * it does not mount anything, and it does not guess a device.  /init mounts
 *     the persist partition read-only, found by the kernel's own GPT label, and
 *     this program reads the file below that fixed mount point.  Keeping the
 *     mount in the shell keeps that policy where the boot-path tests can see it.
 *
 * The clock it sets survives switch_root, because the wall clock is kernel state
 * and not something the initramfs owns.  That is the whole point: Debian starts
 * with `date` already correct and with no network.
 *
 * Output is one line of key=value tokens, which /init parses with the shell's own
 * word splitting so the production image needs no new BusyBox applet:
 *
 *	rtc-offset: status=applied offset_ms=1767701103844 raw_ms=22638758000 \
 *	            realtime_epoch=1790453247 source=persist/time/ats_2
 *
 * Built freestanding for aarch64: no libc, no dynamic linker, no libgcc.
 */
/*
 * GTS9_HOST_TEST builds the same source against x86_64 syscall numbers so a host
 * test can exercise the real parser and the real arithmetic.  It changes only the
 * two things a host cannot provide: the syscall table, and a CLOCK_REALTIME that
 * the test must not actually set - it would move the machine running the tests.
 * The production aarch64 build never defines it, and every behaviour asserted by
 * the tests is the behaviour the tablet runs.
 */
#ifdef GTS9_HOST_TEST
#define SYS_openat	 257
#define SYS_close	 3
#define SYS_read	 0
#define SYS_write	 1
#define SYS_exit_group	 231
#define SYS_clock_settime 227
#else
#define SYS_openat	 56
#define SYS_close	 57
#define SYS_read	 63
#define SYS_write	 64
#define SYS_exit_group	 94
#define SYS_clock_settime 112
#endif

#define AT_FDCWD	(-100)
#define O_RDONLY	0

#define CLOCK_REALTIME	0

/*
 * The mount point /init uses for the read-only persist partition.  Fixed rather
 * than a command-line argument: the mount is performed by /init at this exact
 * path, and an interface with no second caller is a place for the two halves to
 * disagree.  There is no fallback path, so a handoff that did not mount it gets
 * `offset-file-missing` reported rather than a silently invented epoch.
 *
 * Both paths are overridable only so the host test can point them at a temporary
 * directory; production takes the defaults below.
 */
#ifndef GTS9_OFFSET_PATH
#define GTS9_OFFSET_PATH "/persist-ro/time/ats_2"
#endif
#ifndef GTS9_EPOCH_PATH
#define GTS9_EPOCH_PATH "/sys/class/rtc/rtc0/since_epoch"
#endif

#define OFFSET_PATH	GTS9_OFFSET_PATH
#define OFFSET_LABEL	"persist/time/ats_2"
#define EPOCH_PATH	GTS9_EPOCH_PATH

/*
 * A delta outside these bounds means the file is not what we think it is, and a
 * confidently wrong clock is worse than an obvious 1970 one: it breaks TLS and
 * ssh in ways that read as a network fault.  The real value is ~1.767e12 ms.
 */
#define MIN_OFFSET_MS	1000LL			/* 1 second */
#define MAX_OFFSET_MS	100000000000000LL	/* ~3170 years */

/*
 * Accept a resulting wall clock only inside a plausible window.  2020-01-01 is
 * comfortably before this board's earliest plausible correct time and 2100-01-01
 * comfortably after; anything outside is refused and the clock left alone.
 */
#define MIN_REALTIME	1577836800LL		/* 2020-01-01T00:00:00Z */
#define MAX_REALTIME	4102444800LL		/* 2100-01-01T00:00:00Z */

#define EXIT_OK		0
#define EXIT_NO_OFFSET	12	/* file absent, unreadable or the wrong size */
#define EXIT_BAD_OFFSET	13	/* present, but not a sane delta */
#define EXIT_NO_EPOCH	14	/* the RTC counter could not be read */
#define EXIT_BAD_TIME	15	/* sum landed outside the plausible window */

/*
 * The syscall primitive.  Exactly one instruction differs between the two builds;
 * everything above it - the parser, the bounds, the arithmetic, the report - is
 * the same code the tablet runs.
 */
#ifdef GTS9_HOST_TEST
static long raw_syscall3(long n, long a, long b, long c)
{
	register long r10 asm("r10") = 0;
	register long r8 asm("r8") = 0;
	register long r9 asm("r9") = 0;
	long ret;

	asm volatile("syscall"
		     : "=a"(ret)
		     : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8), "r"(r9)
		     : "rcx", "r11", "memory");
	return ret;
}

static long raw_syscall4(long n, long a, long b, long c, long d)
{
	register long r10 asm("r10") = d;
	register long r8 asm("r8") = 0;
	register long r9 asm("r9") = 0;
	long ret;

	asm volatile("syscall"
		     : "=a"(ret)
		     : "a"(n), "D"(a), "S"(b), "d"(c), "r"(r10), "r"(r8), "r"(r9)
		     : "rcx", "r11", "memory");
	return ret;
}
#else
static long raw_syscall3(long n, long a, long b, long c)
{
	register long x0 asm("x0") = a;
	register long x1 asm("x1") = b;
	register long x2 asm("x2") = c;
	register long x8 asm("x8") = n;

	asm volatile("svc #0"
		     : "+r"(x0)
		     : "r"(x1), "r"(x2), "r"(x8)
		     : "memory", "x3", "x4", "x5", "x6", "x7", "x9", "x10",
		       "x11", "x12", "x13", "x14", "x15", "x16", "x17", "x18");
	return x0;
}

static long raw_syscall4(long n, long a, long b, long c, long d)
{
	register long x0 asm("x0") = a;
	register long x1 asm("x1") = b;
	register long x2 asm("x2") = c;
	register long x3 asm("x3") = d;
	register long x8 asm("x8") = n;

	asm volatile("svc #0"
		     : "+r"(x0)
		     : "r"(x1), "r"(x2), "r"(x3), "r"(x8)
		     : "memory", "x4", "x5", "x6", "x7", "x9", "x10", "x11",
		       "x12", "x13", "x14", "x15", "x16", "x17", "x18");
	return x0;
}
#endif

#define sys_call3 raw_syscall3
#define sys_call4 raw_syscall4

static long str_len(const char *text)
{
	long length = 0;

	while (text[length])
		length++;
	return length;
}

static void put_str(const char *text)
{
	long length = str_len(text);
	long done = 0;

	while (done < length) {
		long rc = sys_call3(SYS_write, 1, (long)(text + done),
				    length - done);

		if (rc <= 0)
			return;
		done += rc;
	}
}

/* Signed 64-bit decimal.  The only formatting in the program. */
static void put_ll(long long value)
{
	char digits[24];
	int used = 0;
	int negative = value < 0;
	unsigned long long magnitude;

	if (negative)
		magnitude = (unsigned long long)(-value);
	else
		magnitude = (unsigned long long)value;

	do {
		digits[used++] = (char)('0' + (int)(magnitude % 10ULL));
		magnitude /= 10ULL;
	} while (magnitude);

	if (negative)
		put_str("-");
	while (used > 0)
		sys_call3(SYS_write, 1, (long)&digits[--used], 1);
}

/*
 * Read the whole file, insisting on exactly the eight bytes Samsung's format
 * defines.  The format has no header, no magic and no checksum, so its length is
 * the only structural check that exists - and a nine-byte read is how a changed
 * format is detected rather than silently truncated.
 */
static int read_offset_ms(long long *value)
{
	unsigned char raw[8];
	unsigned char extra;
	long fd;
	long got;
	long total = 0;
	int index;

	fd = sys_call4(SYS_openat, AT_FDCWD, (long)OFFSET_PATH, O_RDONLY, 0);
	if (fd < 0)
		return -1;

	while (total < 8) {
		got = sys_call3(SYS_read, fd, (long)(raw + total), 8 - total);
		if (got < 0) {
			sys_call3(SYS_close, fd, 0, 0);
			return -1;
		}
		if (got == 0)
			break;
		total += got;
	}
	if (total == 8 && sys_call3(SYS_read, fd, (long)&extra, 1) > 0)
		total = 9;
	sys_call3(SYS_close, fd, 0, 0);

	if (total != 8)
		return -1;

	/*
	 * Little-endian two's complement, assembled by hand and sign-extended
	 * explicitly, so nothing depends on the compiler's aliasing or shift
	 * behaviour under -ffreestanding.
	 */
	{
		unsigned long long magnitude = 0;

		for (index = 7; index >= 0; index--)
			magnitude = (magnitude << 8) |
				    (unsigned long long)raw[index];

		if (magnitude & 0x8000000000000000ULL)
			*value = -(long long)(~magnitude + 1ULL);
		else
			*value = (long long)magnitude;
	}

	return 0;
}

/*
 * The raw counter, from the driver's own attribute.  `since_epoch` is served by
 * rtc_read_time(), and rtc-pm8xxx has no offset configured in this board's DTS,
 * so what comes back is the counter itself - the same number
 * scripts/read-rtc-state.sh and the boot-test evidence read.  Used for the report
 * line only; the arithmetic never invents this value.
 *
 * Returns the value in *milliseconds* so the caller adds like with like.
 */
static int read_raw_ms(long long *value)
{
	char buffer[24];
	long fd;
	long got;
	long long parsed = 0;
	long index = 0;

	fd = sys_call4(SYS_openat, AT_FDCWD, (long)EPOCH_PATH, O_RDONLY, 0);
	if (fd < 0)
		return -1;

	got = sys_call3(SYS_read, fd, (long)buffer, sizeof(buffer) - 1);
	sys_call3(SYS_close, fd, 0, 0);
	if (got <= 0)
		return -1;
	buffer[got] = '\0';

	while (index < got && buffer[index] >= '0' && buffer[index] <= '9') {
		parsed = parsed * 10 + (buffer[index] - '0');
		index++;
	}
	if (index == 0)
		return -1;

	*value = parsed * 1000;
	return 0;
}

/*
 * Sentinel for "this field is not known", distinct from any value that can
 * legitimately occur: the raw counter is at most U32_MAX*1000 (~4.3e12), a
 * plausible offset is under MAX_OFFSET_MS (1e14), and an accepted wall clock is
 * under MAX_REALTIME (4.1e9).  A negative offset must still be *reported* - that
 * is how a corrupt file is told apart from a missing one - so "absent" cannot be
 * signalled by a negative number.
 */
#define ABSENT		0x7FFFFFFFFFFFFFFFLL

static void report(const char *status, long long offset_ms, long long raw_ms,
		   long long realtime, int with_source)
{
	put_str("rtc-offset: status=");
	put_str(status);
	if (with_source) {
		put_str(" source=");
		put_str(OFFSET_LABEL);
	}
	if (offset_ms != ABSENT) {
		put_str(" offset_ms=");
		put_ll(offset_ms);
	}
	if (raw_ms != ABSENT) {
		put_str(" raw_ms=");
		put_ll(raw_ms);
	}
	if (realtime != ABSENT) {
		put_str(" realtime_epoch=");
		put_ll(realtime);
	}
	put_str("\n");
}

/* struct __kernel_timespec is two 64-bit fields on aarch64. */
struct kernel_timespec {
	long long tv_sec;
	long long tv_nsec;
};

/* CLOCK_REALTIME only.  There is no path in this program that can reach an RTC
 * device node, which is what keeps it away from the SPMI write that hangs this
 * board (docs/RTC_REPORT.md, tests 021-027). */
static void set_realtime(long long seconds)
{
#ifdef GTS9_HOST_TEST
	/* Never move the clock of the machine running the tests.  The caller's
	 * report line still carries the value that would have been set, which is
	 * what the test asserts on. */
	(void)seconds;
#else
	struct kernel_timespec when;

	when.tv_sec = seconds;
	when.tv_nsec = 0;
	sys_call3(SYS_clock_settime, CLOCK_REALTIME, (long)&when, 0);
#endif
}

static void exit_with(int status)
{
	sys_call3(SYS_exit_group, status, 0, 0);
	for (;;)
		;
}

void _start(void)
{
	long long offset_ms = ABSENT;
	long long raw_ms = ABSENT;
	long long realtime;

	if (read_offset_ms(&offset_ms) != 0) {
		/* Not fatal and not new: without the offset the clock is simply the
		 * raw counter, which is what this board did before. */
		report("offset-file-missing", ABSENT, ABSENT, ABSENT, 1);
		exit_with(EXIT_NO_OFFSET);
	}

	if (offset_ms < MIN_OFFSET_MS || offset_ms > MAX_OFFSET_MS) {
		report("offset-out-of-range", offset_ms, ABSENT, ABSENT, 1);
		exit_with(EXIT_BAD_OFFSET);
	}

	if (read_raw_ms(&raw_ms) != 0) {
		report("rtc-unreadable", offset_ms, ABSENT, ABSENT, 1);
		exit_with(EXIT_NO_EPOCH);
	}

	/* Milliseconds on both sides, then one truncating division - the same
	 * arithmetic TWRP applies to the same file, so the two agree to the
	 * second rather than drifting by up to 999 ms. */
	realtime = (raw_ms + offset_ms) / 1000;

	if (realtime < MIN_REALTIME || realtime > MAX_REALTIME) {
		report("realtime-out-of-range", offset_ms, raw_ms, realtime, 1);
		exit_with(EXIT_BAD_TIME);
	}

	set_realtime(realtime);
	report("applied", offset_ms, raw_ms, realtime, 1);
	exit_with(EXIT_OK);
}
