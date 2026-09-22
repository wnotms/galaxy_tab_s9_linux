/*
 * gts9-exec-default — reset the signals a shell cannot reset itself, then exec.
 *
 * Why this exists: a background job of a shell without job control has SIGINT and
 * SIGQUIT set to SIG_IGN (POSIX), and a shell cannot clear a signal that was already
 * ignored when it started.  That is exactly what happened to the tty1 panel shell: it
 * owned tty1's foreground process group (pgrp == tpgid) and still had SigIgn bit 1 set,
 * so Ctrl-C did nothing.  busybox has no applet that clears the disposition (setsid and
 * cttyhack were both measured not to), so this does it with three syscalls.
 *
 * Built freestanding for aarch64 - no libc, no dynamic linker - by
 * scripts/build-bringup-initramfs.sh, and installed as /sbin/gts9-exec-default.
 *
 *   gts9-exec-default PROG [ARGS...]
 *
 * The child gets a minimal environment (PATH, HOME, TERM, PS1) because there is no libc
 * here to copy the parent's.
 */
typedef unsigned long u64;

#define SYS_rt_sigaction 134
#define SYS_execve       221
#define SYS_write         64
#define SYS_exit          93

#define SIG_DFL 0UL
#define SIGINT 2
#define SIGQUIT 3
#define SIGTSTP 20
#define SIGTTIN 21
#define SIGTTOU 22

struct ksa {
	u64 handler;
	u64 flags;
	u64 restorer;
	u64 mask;
};

static long sys4(long n, long a, long b, long c, long d)
{
	register long x0 asm("x0") = a;
	register long x1 asm("x1") = b;
	register long x2 asm("x2") = c;
	register long x3 asm("x3") = d;
	register long x8 asm("x8") = n;

	asm volatile("svc #0"
		     : "+r"(x0)
		     : "r"(x1), "r"(x2), "r"(x3), "r"(x8)
		     : "memory", "x4", "x5", "x6", "x7");
	return x0;
}

static void reset_to_default(int sig)
{
	struct ksa sa;

	sa.handler = SIG_DFL;
	sa.flags = 0;
	sa.restorer = 0;
	sa.mask = 0;
	sys4(SYS_rt_sigaction, sig, (long)&sa, 0, 8);
}

void start_c(long *sp);

/*
 * A naked entry: the C prologue would adjust sp before the first statement, so the
 * original stack pointer - which is where argc/argv live - has to be captured here.
 * The first version read sp from inside a normal function and segfaulted on hardware.
 */
__attribute__((naked)) void _start(void)
{
	asm volatile("mov x0, sp\n\tbl start_c\n\tmov x8, #93\n\tsvc #0");
}

void start_c(long *sp)
{
	long argc;
	char **argv;
	static char *envp[] = {
		"PATH=/sbin:/bin:/usr/sbin:/usr/bin",
		"HOME=/",
		"TERM=linux",
		"PS1=gts9# ",
		0,
	};

	argc = sp[0];
	argv = (char **)&sp[1];

	if (argc < 2) {
		static const char usage[] = "usage: gts9-exec-default PROG [ARGS...]\n";

		sys4(SYS_write, 2, (long)usage, sizeof(usage) - 1, 0);
		sys4(SYS_exit, 2, 0, 0, 0);
	}

	reset_to_default(SIGINT);
	reset_to_default(SIGQUIT);
	reset_to_default(SIGTSTP);
	reset_to_default(SIGTTIN);
	reset_to_default(SIGTTOU);

	sys4(SYS_execve, (long)argv[1], (long)&argv[1], (long)envp, 0);

	{
		static const char failed[] = "gts9-exec-default: exec failed\n";

		sys4(SYS_write, 2, (long)failed, sizeof(failed) - 1, 0);
	}
	sys4(SYS_exit, 127, 0, 0, 0);
}
