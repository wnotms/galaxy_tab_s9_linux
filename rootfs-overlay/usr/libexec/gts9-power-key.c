// SPDX-License-Identifier: GPL-2.0
/*
 * gts9-power-key - short power-key press turns the screen off, nothing else.
 *
 * systemd-logind's power-key actions all stop the machine in some way:
 * poweroff shuts it down, suspend freezes the SoC and - on this tablet - takes
 * the USB gadget down with it, so the ttyGS0 debug console disappears exactly
 * when it is most useful.  There is no "blank" action to use instead: logind
 * 257 rejects `HandlePowerKey=blank` with "Failed to parse ..., ignoring:
 * Invalid argument" and silently falls back to its poweroff default, which is
 * how a short power press would have shut the tablet down.  So this small
 * daemon owns the key instead:
 *
 *	short press (< 1.2 s) -> backlight off / backlight restored
 *	long press (>= 1.2 s) -> ignored; the PMIC's own forced power-off stays
 *
 * The backlight is used rather than /sys/class/graphics/fb0/blank on purpose.
 * Blanking fb0 is a full modeset on the DPU, and test 178 caught that path
 * hanging the tablet twice (enc35 frame done timeout -> vblank wait timeout ->
 * workqueue lockup, with two CPUs that stop answering NMIs).  A backlight
 * write is a single DSI DCS brightness command inside the panel driver - the
 * same path a desktop brightness slider uses - and touches neither the DPU
 * encoder nor vblank.
 *
 * Nothing else changes: no suspend, no poweroff, no USB reconfiguration.  The
 * input device is chosen by capability (EV_KEY + KEY_POWER via EVIOCGBIT), not
 * by event number, and is never grabbed, so a future desktop environment and
 * the PMIC's hardware long-hold keep working.  State lives in RAM only, under
 * /run/gts9-power-key/.
 *
 * `gts9-power-key --toggle` performs one toggle and exits, which is how the
 * host and the tablet verify the screen path without pressing the key.
 *
 * Built freestanding for aarch64; no libc, no compiler runtime.
 */
#define SYS_ioctl    29
#define SYS_mkdirat  34
#define SYS_unlinkat 35
#define SYS_openat   56
#define SYS_close    57
#define SYS_read     63
#define SYS_write    64
#define SYS_nanosleep 101
#define SYS_exit_group 94

#define AT_FDCWD (-100)
#define O_RDONLY 0
#define O_WRONLY 1
#define O_CREAT 0100
#define O_NONBLOCK 04000

#define EV_KEY 0x01
#define KEY_POWER 116
#define KEY_BITMAP_BYTES ((KEY_POWER / 8) + 1)
#define IOC_READ 2UL
/* _IOC(dir, type, nr, size): type is bits 8-15, nr is bits 0-7. */
#define GTS9_IOC(dir, type, nr, size) \
	(((unsigned long)(dir) << 30) | ((unsigned long)(type) << 8) | \
	 ((unsigned long)(nr)) | ((unsigned long)(size) << 16))
#define EVIOCGNAME(len) GTS9_IOC(IOC_READ, 'E', 0x06, len)
#define EVIOCGBIT(ev, len) GTS9_IOC(IOC_READ, 'E', 0x20 + (ev), len)

#define BACKLIGHT_DIR "/sys/class/backlight/ae94000.dsi.0"
#define BRIGHTNESS_PATH BACKLIGHT_DIR "/brightness"
#define BL_POWER_PATH BACKLIGHT_DIR "/bl_power"
#define MAX_BRIGHTNESS_PATH BACKLIGHT_DIR "/max_brightness"
#define STATE_DIR "/run/gts9-power-key"
#define SAVED_BRIGHTNESS_PATH STATE_DIR "/last-brightness"
#define DISPLAY_OFF_PATH STATE_DIR "/display-off"
#define KMSG_PATH "/dev/kmsg"
#define INPUT_NAME_PATTERN "pwrkey"
#define BL_POWER_ON "0"
#define BL_POWER_OFF "4"
/* Anything at or above this is a long press and belongs to the PMIC. */
#define LONG_PRESS_MICROSECONDS 1200000L

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
	int negative = 0;

	if (value < 0) {
		negative = 1;
		value = -value;
	}
	do {
		digits[count++] = (char)('0' + value % 10);
		value /= 10;
	} while (value && count < (int)sizeof(digits) - 1);
	if (negative)
		digits[count++] = '-';

	while (count > 0 && str_len(buffer) + 1 < limit)
		buffer[str_len(buffer)] = digits[--count];
}

/* Append text to an already NUL-terminated buffer; keeps one kmsg line. */
static void append_text(char *buffer, const char *text, long limit)
{
	long i = str_len(buffer);
	long j = 0;

	while (text[j] && i < limit - 1)
		buffer[i++] = text[j++];
	buffer[i] = '\0';
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
	long fd = sys_call6(SYS_openat, AT_FDCWD, (long)path,
			    O_WRONLY | O_CREAT, 0644, 0, 0);

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

	if (read_number(BL_POWER_PATH, &power) != 0) {
		/*
		 * No panel came up.  Do nothing at all: never fall back to
		 * fb0/blank (a modeset that can hang the DPU) and never to
		 * suspend.  Leave a trace for the console instead.
		 */
		log_message("gts9-power-key: no backlight node; key ignored\n");
		return -1;
	}

	sys_call6(SYS_mkdirat, AT_FDCWD, (long)STATE_DIR, 0755, 0, 0, 0);

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
				    sizeof(BL_POWER_OFF) - 1) != 0) {
			log_message("gts9-power-key: could not power the backlight down\n");
			return -1;
		}
		write_file_text(DISPLAY_OFF_PATH, "1\n", 2);
		log_message("gts9-power-key: screen off (backlight off, system keeps running)\n");
		return 0;
	}

	/* Screen off: power the backlight back up at the remembered level. */
	if (write_file_text(BL_POWER_PATH, BL_POWER_ON,
			    sizeof(BL_POWER_ON) - 1) != 0) {
		log_message("gts9-power-key: could not power the backlight up\n");
		return -1;
	}
	if (read_number(SAVED_BRIGHTNESS_PATH, &brightness) != 0) {
		if (read_number(MAX_BRIGHTNESS_PATH, &max_brightness) != 0)
			max_brightness = 0x7ff;
		brightness = max_brightness;
	}
	write_number(BRIGHTNESS_PATH, brightness);
	sys_call6(SYS_unlinkat, AT_FDCWD, (long)DISPLAY_OFF_PATH, 0, 0, 0, 0);
	log_message("gts9-power-key: screen on (backlight restored)\n");
	return 0;
}

/*
 * A KEY_POWER input device is identified by capability, not by event number:
 * ask for the EV_KEY bitmap and look for KEY_POWER in it.  The PMIC power key
 * ("pmic_pwrkey") wins when several devices have it; the device is never
 * grabbed, so logind and a future desktop session still see the key.
 */
static int device_has_power_key(int fd)
{
	unsigned long ev_bits[1];
	unsigned char key_bits[KEY_BITMAP_BYTES];
	long got;
	int i;

	ev_bits[0] = 0;
	got = sys_call6(SYS_ioctl, fd, EVIOCGBIT(0, sizeof(ev_bits)),
			(long)ev_bits, 0, 0, 0);
	if (got < 0 || !(ev_bits[0] & (1UL << EV_KEY)))
		return 0;

	for (i = 0; i < (int)sizeof(key_bits); i++)
		key_bits[i] = 0;
	got = sys_call6(SYS_ioctl, fd, EVIOCGBIT(EV_KEY, sizeof(key_bits)),
			(long)key_bits, 0, 0, 0);
	if (got < 0)
		return 0;
	return (key_bits[KEY_POWER / 8] >> (KEY_POWER % 8)) & 1;
}

/*
 * Second, independent capability check: sysfs publishes the same bitmap as
 * space-separated hex words, most significant word first.  Using both keeps
 * the scan honest - the daemon never picks a device by event number.
 */
static int parse_hex_words(const char *text, unsigned long *words, int max_words)
{
	int count = 0;
	int i = 0;

	while (text[i] && count < max_words) {
		unsigned long value = 0;
		int digits = 0;

		while (text[i] == ' ' || text[i] == '\n' || text[i] == '\t' || text[i] == ',')
			i++;
		for (;;) {
			char c = text[i];
			int d;

			if (c >= '0' && c <= '9')
				d = c - '0';
			else if (c >= 'a' && c <= 'f')
				d = c - 'a' + 10;
			else if (c >= 'A' && c <= 'F')
				d = c - 'A' + 10;
			else
				break;
			value = (value << 4) | (unsigned long)d;
			digits++;
			i++;
		}
		if (!digits)
			break;
		words[count++] = value;
	}
	return count;
}

static int sysfs_has_power_key(int index)
{
	char path[96];
	char text[512];
	unsigned long words[8];
	int count, word_index, bit;

	copy_text(path, "/sys/class/input/event", sizeof(path));
	append_number(path, index, sizeof(path));
	append_text(path, "/device/capabilities/key", sizeof(path));
	if (read_file(path, text, sizeof(text)) <= 0)
		return -1;

	count = parse_hex_words(text, words, (int)(sizeof(words) / sizeof(words[0])));
	word_index = count - 1 - (KEY_POWER / 64);
	if (word_index < 0)
		return 0;
	bit = KEY_POWER % 64;
	return (int)((words[word_index] >> bit) & 1UL);
}

static int open_power_key(void)
{
	char dev_path[64];
	char name[128];
	int index;
	int fallback = -1;

	for (index = 0; index < 32; index++) {
		int fd;
		int by_ioctl;
		int by_sysfs;
		long got;

		copy_text(dev_path, "/dev/input/event", sizeof(dev_path));
		append_number(dev_path, index, sizeof(dev_path));
		fd = (int)sys_call6(SYS_openat, AT_FDCWD, (long)dev_path,
				    O_RDONLY, 0, 0, 0);
		if (fd < 0)
			continue;

		by_ioctl = device_has_power_key(fd);
		by_sysfs = sysfs_has_power_key(index);
		if (!by_ioctl && by_sysfs != 1) {
			sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
			continue;
		}

		name[0] = '\0';
		got = sys_call6(SYS_ioctl, fd, EVIOCGNAME(sizeof(name)),
				(long)name, 0, 0, 0);
		name[sizeof(name) - 1] = '\0';
		if (got < 0 || name[0] == '\0') {
			/* Fall back to the sysfs name when the ioctl is unusable. */
			copy_text(name, "/sys/class/input/event", sizeof(name));
			append_number(name, index, sizeof(name));
			append_text(name, "/device/name", sizeof(name));
			if (read_file(name, name, 96) <= 0)
				name[0] = '\0';
		}

		if (str_contains(name, INPUT_NAME_PATTERN)) {
			log_message("gts9-power-key: found the PMIC power key by capability\n");
			if (fallback >= 0)
				sys_call6(SYS_close, fallback, 0, 0, 0, 0, 0);
			return fd;
		}
		if (fallback < 0)
			fallback = fd;
		else
			sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
	}
	if (fallback >= 0)
		log_message("gts9-power-key: pmic_pwrkey absent; using another KEY_POWER device\n");
	return fallback;
}

static void sleep_one_second(void)
{
	struct timespec {
		long seconds;
		long nanoseconds;
	} delay = { 1, 0 };

	sys_call6(SYS_nanosleep, (long)&delay, 0, 0, 0, 0, 0);
}

static long parse_number(const char *text)
{
	long value = 0;
	int digits = 0;

	while (text[0] >= '0' && text[0] <= '9') {
		value = value * 10 + (text[0] - '0');
		text++;
		digits++;
	}
	return digits ? value : 0;
}

/*
 * `--stress N` toggles the screen N times with a second between transitions.
 * It exercises exactly the path a short press takes (toggle_backlight) so the
 * DPU can be watched for the enc35/vblank failure without a person pressing
 * the key 30 times; the physical key is still verified separately.
 */
static void stress_cycles(long count)
{
	char line[96];
	long i;

	if (count < 1)
		count = 1;
	for (i = 0; i < count; i++) {
		toggle_backlight();
		sleep_one_second();
		toggle_backlight();
		sleep_one_second();
		if ((i % 5) == 4) {
			copy_text(line, "gts9-power-key: stress ", sizeof(line));
			append_number(line, i + 1, sizeof(line));
			append_text(line, " cycles done\n", sizeof(line));
			log_message(line);
		}
	}
	log_message("gts9-power-key: stress finished\n");
}

__attribute__((noreturn)) static void exit_now(long code)
{
	sys_call6(SYS_exit_group, code, 0, 0, 0, 0, 0);
	for (;;)
		;
}

/*
 * `--diag` prints what the capability scan sees, one line per event device.
 * It exists because this helper is freestanding: there is no strace and no
 * shell on the panel when the scan misbehaves.
 */
static void diag_devices(void)
{
	char dev_path[64];
	char name[64];
	char line[192];
	unsigned long ev_bits[1];
	unsigned char key_bits[KEY_BITMAP_BYTES];
	int index;

	for (index = 0; index < 4; index++) {
		long fd, got;
		int i;

		copy_text(dev_path, "/dev/input/event", sizeof(dev_path));
		append_number(dev_path, index, sizeof(dev_path));
		fd = sys_call6(SYS_openat, AT_FDCWD, (long)dev_path, O_RDONLY, 0, 0, 0);

		copy_text(line, "gts9-power-key: diag ", sizeof(line));
		append_text(line, dev_path, sizeof(line));
		if (fd < 0) {
			append_text(line, " open_failed\n", sizeof(line));
			log_message(line);
			continue;
		}
		ev_bits[0] = 0;
		got = sys_call6(SYS_ioctl, fd, EVIOCGBIT(0, sizeof(ev_bits)),
				(long)ev_bits, 0, 0, 0);
		append_text(line, " ev_rc=", sizeof(line));
		append_number(line, got, sizeof(line));
		append_text(line, " ev=0x", sizeof(line));
		append_number(line, ev_bits[0], sizeof(line));
		for (i = 0; i < (int)sizeof(key_bits); i++)
			key_bits[i] = 0;
		got = sys_call6(SYS_ioctl, fd, EVIOCGBIT(EV_KEY, sizeof(key_bits)),
				(long)key_bits, 0, 0, 0);
		append_text(line, " key_rc=", sizeof(line));
		append_number(line, got, sizeof(line));
		append_text(line, " keypower=", sizeof(line));
		append_number(line, (key_bits[KEY_POWER / 8] >> (KEY_POWER % 8)) & 1,
			      sizeof(line));
		append_text(line, " sysfs_keypower=", sizeof(line));
		append_number(line, sysfs_has_power_key(index), sizeof(line));
		name[0] = '\0';
		sys_call6(SYS_ioctl, fd, EVIOCGNAME(sizeof(name)), (long)name, 0, 0, 0);
		name[sizeof(name) - 1] = '\0';
		append_text(line, " name=", sizeof(line));
		append_text(line, name, sizeof(line));
		append_text(line, "\n", sizeof(line));
		log_message(line);
		sys_call6(SYS_close, fd, 0, 0, 0, 0, 0);
	}
}

__attribute__((noreturn, used)) void gts9_main(long argc, char **argv)
{
	struct input_event event;
	int failures = 0;
	int fd;
	int pressed = 0;
	long press_seconds = 0;
	long press_microseconds = 0;
	char line[160];

	/* One line, so the freestanding entry can be checked from dmesg. */
	if (argc < 2 || !argv || !argv[1]) {
		log_message("gts9-power-key: service mode (no arguments)\n");
	} else {
		copy_text(line, "gts9-power-key: argv1=", sizeof(line));
		append_text(line, argv[1], sizeof(line));
		append_text(line, "\n", sizeof(line));
		log_message(line);
	}

	if (argc >= 2 && argv && argv[1] && str_contains(argv[1], "diag")) {
		diag_devices();
		exit_now(0);
	}
	if (argc >= 3 && argv && argv[1] && argv[2] && str_contains(argv[1], "stress")) {
		stress_cycles(parse_number(argv[2]));
		exit_now(0);
	}
	if (argc >= 2 && argv && argv[1] && str_contains(argv[1], "toggle"))
		exit_now(toggle_backlight() == 0 ? 0 : 1);

	fd = open_power_key();
	if (fd < 0) {
		log_message("gts9-power-key: no KEY_POWER input device found\n");
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
		if (event.value == 1) {
			/* Press: remember when, and decide on release. */
			pressed = 1;
			press_seconds = event.seconds;
			press_microseconds = event.microseconds;
			continue;
		}
		if (event.value != 0 || !pressed)
			continue;
		pressed = 0;
		{
			long duration = (event.seconds - press_seconds) * 1000000L +
					(event.microseconds - press_microseconds);

			if (duration >= 0 && duration < LONG_PRESS_MICROSECONDS) {
				toggle_backlight();
			} else {
				/* A long hold is the PMIC's forced power-off. */
				log_message("gts9-power-key: long press ignored (PMIC owns it)\n");
			}
		}
	}
}

/*
 * A freestanding entry point gets nothing in x0/x1: the arm64 ELF loader
 * (ELF_PLAT_INIT) zeroes x0, so the libc _start that normally forwards
 * argc/argv does not exist here.  Read them from the initial stack instead -
 * otherwise argv[1] is never seen and `--toggle` silently falls through into
 * the key-watch loop, which is exactly what happened before this was fixed.
 */
__attribute__((naked)) void _start(void)
{
	asm volatile(
		"ldr x0, [sp]\n"	/* argc */
		"add x1, sp, #8\n"	/* argv */
		"bl gts9_main\n"
		"1: wfe\n"
		"b 1b\n");
}
