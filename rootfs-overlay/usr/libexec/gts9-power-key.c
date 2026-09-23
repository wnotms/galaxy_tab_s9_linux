// SPDX-License-Identifier: GPL-2.0
/*
 * gts9-power-key - short power-key press turns the screen off, nothing else.
 *
 * systemd-logind's power-key actions all stop the machine in some way:
 * poweroff shuts it down, suspend freezes the SoC and - on this tablet - takes
 * the USB gadget down with it, so the ttyGS0 debug console disappears exactly
 * when it is most useful.  The owner asked for the screen to go off and the
 * machine to keep running, so this small daemon owns the key instead:
 *
 *	short press -> backlight off / backlight restored
 *
 * The backlight is used rather than /sys/class/graphics/fb0/blank on purpose.
 * Blanking fb0 is a full modeset on the DPU, and test 178 caught that path
 * hanging the tablet twice (enc35 frame done timeout -> vblank wait timeout ->
 * workqueue lockup, with two CPUs that stop answering NMIs).  A backlight
 * write is a single DSI DCS brightness command inside the panel driver - the
 * same path a desktop brightness slider uses - and touches neither the DPU
 * encoder nor vblank.
 *
 * Nothing else changes: no suspend, no poweroff, no USB reconfiguration.
 * The kernel's own long-press handling is untouched, so the tablet can still
 * be forced off with a long press.
 *
 * `gts9-power-key --toggle` performs one toggle and exits, which is how the
 * host and the tablet verify the blank path without pressing the key.
 *
 * Built freestanding for aarch64; no libc, no compiler runtime.
 */
#define SYS_ioctl    29
#define SYS_openat   56
#define SYS_close    57
#define SYS_read     63
#define SYS_write    64
#define SYS_nanosleep 101
#define SYS_exit_group 94

#define AT_FDCWD (-100)
#define O_RDONLY 0
#define O_WRONLY 1
#define O_NONBLOCK 04000

#define EV_KEY 0x01
#define KEY_POWER 116

#define BACKLIGHT_DIR "/sys/class/backlight/ae94000.dsi.0"
#define BRIGHTNESS_PATH BACKLIGHT_DIR "/brightness"
#define BL_POWER_PATH BACKLIGHT_DIR "/bl_power"
#define MAX_BRIGHTNESS_PATH BACKLIGHT_DIR "/max_brightness"
#define SAVED_BRIGHTNESS_PATH "/run/gts9-power-key.brightness"
#define KMSG_PATH "/dev/kmsg"
#define INPUT_NAME_PATTERN "pwrkey"
#define BL_POWER_ON "0"
#define BL_POWER_OFF "4"

struct input_event {
	long seconds;
	long microseconds;
	unsigned short type;
	unsigned short code;
	int value;
};

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

static int str_contains(const char *haystack, const char *needle)
{
	long i, j;

	for (i = 0; haystack[i]; i++) {
		for (j = 0; needle[j]; j++) {
			if (haystack[i + j] != needle[j])
				break;
		}
		if (!needle[j])
			return 1;
	}
	return 0;
}

static void copy_text(char *dest, const char *src, long limit)
{
	long i = 0;

	while (src[i] && i < limit - 1) {
		dest[i] = src[i];
		i++;
	}
	dest[i] = '\0';
}

static void append_number(char *buffer, long value, long limit)
{
	char digits[24];
	int count = 0;

	do {
		digits[count++] = (char)('0' + value % 10);
		value /= 10;
	} while (value && count < (int)sizeof(digits));

	while (count > 0 && str_len(buffer) + 1 < limit)
		buffer[str_len(buffer)] = digits[--count];
}

static void log_message(const char *message)
{
	long fd = sys_call6(SYS_openat, AT_FDCWD, (long)KMSG_PATH,
			    O_WRONLY | O_NONBLOCK, 0, 0, 0);

	if (fd < 0)
		return;
	sys_call6(SYS_write, fd, (long)message, str_len(message), 0, 0, 0);
	sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
}

static long read_file(const char *path, char *buffer, long size)
{
	long fd = sys_call6(SYS_openat, AT_FDCWD, (long)path, O_RDONLY, 0, 0, 0);
	long got;

	if (fd < 0)
		return -1;
	got = sys_call6(SYS_read, fd, (long)buffer, size - 1, 0, 0, 0);
	sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
	if (got < 0)
		return -1;
	buffer[got] = '\0';
	return got;
}

/*
 * The backlight is the only thing this daemon controls.  It may be absent (no
 * panel came up), in which case the key simply does nothing.
 */
static int write_file_text(const char *path, const char *text, long length)
{
	long fd = sys_call6(SYS_openat, AT_FDCWD, (long)path, O_WRONLY, 0, 0, 0);

	if (fd < 0)
		return -1;
	sys_call6(SYS_write, fd, (long)text, length, 0, 0, 0);
	sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
	return 0;
}

static int read_number(const char *path, long *value)
{
	char buffer[32];
	long got = read_file(path, buffer, sizeof(buffer));
	long result = 0;
	int digits = 0;
	long i;

	if (got <= 0)
		return -1;
	for (i = 0; i < got; i++) {
		if (buffer[i] < '0' || buffer[i] > '9')
			break;
		result = result * 10 + (buffer[i] - '0');
		digits++;
	}
	if (!digits)
		return -1;
	*value = result;
	return 0;
}

static void write_number(const char *path, long value)
{
	char buffer[24];
	char digits[24];
	int count = 0;
	int i = 0;

	do {
		digits[count++] = (char)('0' + value % 10);
		value /= 10;
	} while (value && count < (int)sizeof(digits));
	while (count > 0)
		buffer[i++] = digits[--count];
	buffer[i] = '\n';
	write_file_text(path, buffer, i + 1);
}

static int toggle_backlight(void)
{
	long power;
	long brightness;
	long max_brightness;

	if (read_number(BL_POWER_PATH, &power) != 0)
		return -1;

	if (power == 0) {
		/* Screen on: remember the level, then power the backlight down. */
		char saved[24];
		int length = 0;

		if (read_number(BRIGHTNESS_PATH, &brightness) == 0) {
			long value = brightness;
			char digits[24];
			int count = 0;

			do {
				digits[count++] = (char)('0' + value % 10);
				value /= 10;
			} while (value && count < (int)sizeof(digits));
			while (count > 0)
				saved[length++] = digits[--count];
			saved[length++] = '\n';
			write_file_text(SAVED_BRIGHTNESS_PATH, saved, length);
		}
		if (write_file_text(BL_POWER_PATH, BL_POWER_OFF,
				    sizeof(BL_POWER_OFF) - 1) != 0)
			return -1;
		log_message("gts9-power-key: screen off (backlight off, system keeps running)\n");
		return 0;
	}

	/* Screen off: power the backlight back up at the remembered level. */
	if (write_file_text(BL_POWER_PATH, BL_POWER_ON,
			    sizeof(BL_POWER_ON) - 1) != 0)
		return -1;
	if (read_number(SAVED_BRIGHTNESS_PATH, &brightness) != 0) {
		if (read_number(MAX_BRIGHTNESS_PATH, &max_brightness) != 0)
			max_brightness = 0x7ff;
		brightness = max_brightness;
	}
	write_number(BRIGHTNESS_PATH, brightness);
	log_message("gts9-power-key: screen on (backlight restored)\n");
	return 0;
}

/*
 * Find the PMIC power key among the input devices by its sysfs name; the
 * tablet registers it as "pmic_pwrkey".
 */
static int open_power_key(void)
{
	static const char name_prefix[] = "/sys/class/input/event";
	static const char name_suffix[] = "/device/name";
	char name_path[64];
	char dev_path[64];
	char name[128];
	int index;

	for (index = 0; index < 32; index++) {
		long got;

		copy_text(name_path, name_prefix, sizeof(name_path));
		append_number(name_path, index, sizeof(name_path));
		copy_text(name_path + str_len(name_path), name_suffix,
			  sizeof(name_path) - str_len(name_path));

		got = read_file(name_path, name, sizeof(name));
		if (got <= 0 || !str_contains(name, INPUT_NAME_PATTERN))
			continue;

		copy_text(dev_path, "/dev/input/event", sizeof(dev_path));
		append_number(dev_path, index, sizeof(dev_path));
		return (int)sys_call6(SYS_openat, AT_FDCWD, (long)dev_path,
				      O_RDONLY, 0, 0, 0);
	}
	return -1;
}

static void sleep_one_second(void)
{
	struct timespec {
		long seconds;
		long nanoseconds;
	} delay = { 1, 0 };

	sys_call6(SYS_nanosleep, (long)&delay, 0, 0, 0, 0, 0);
}

__attribute__((noreturn)) static void exit_now(long code)
{
	sys_call6(SYS_exit_group, code, 0, 0, 0, 0, 0);
	for (;;)
		;
}

__attribute__((noreturn, used)) void gts9_main(long argc, char **argv)
{
	struct input_event event;
	int failures = 0;
	int fd;

	if (argc >= 2 && str_contains(argv[1], "toggle"))
		exit_now(toggle_backlight() == 0 ? 0 : 1);

	fd = open_power_key();
	if (fd < 0) {
		log_message("gts9-power-key: no PMIC power key input device found\n");
		exit_now(1);
	}
	log_message("gts9-power-key: watching the power key; short press turns the backlight off\n");

	for (;;) {
		long got = sys_call6(SYS_read, fd, (long)&event, sizeof(event), 0, 0, 0);

		if (got != (long)sizeof(event)) {
			/*
			 * EINTR, a short read or a removed device.  Never spin:
			 * sleep, and let systemd restart us if the device is
			 * really gone.
			 */
			if (++failures > 30) {
				log_message("gts9-power-key: power key device stopped delivering events\n");
				exit_now(1);
			}
			sleep_one_second();
			continue;
		}
		failures = 0;
		if (event.type != EV_KEY || event.code != KEY_POWER)
			continue;
		if (event.value != 1)
			continue;
		toggle_backlight();
	}
}

__attribute__((naked)) void _start(void)
{
	asm volatile("bl gts9_main\n"
		     "1: wfe\n"
		     "b 1b\n");
}
