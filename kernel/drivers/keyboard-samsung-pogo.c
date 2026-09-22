// SPDX-License-Identifier: GPL-2.0-only
/*
 * Samsung X710 STM32 pogo keyboard, native Linux input port.
 * Protocol derived from Samsung Electronics' GPLv2 stm32_pogo_*_v3
 * sources in SM-X710_EUR_15_Opensource.zip (2019 Samsung copyright).
 * EF-DX710 uses little-endian Linux keycodes, bit 15 is key-down.
 * No MCU firmware update, raw debug register or DFU interface is exposed.
 */
#include <linux/delay.h>
#include <linux/gpio/consumer.h>
#include <linux/i2c.h>
#include <linux/input.h>
#include <linux/interrupt.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/pinctrl/consumer.h>
#include <linux/regulator/consumer.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>

#define POGO_MAX_PAYLOAD 100
#define POGO_MODEL_DX710 0x02

/* STM32 command ids, from Samsung's stm32_pogo_v3.h. */
#define POGO_CMD_GET_MODE		0x01
#define POGO_CMD_CHECK_VERSION		0x02
#define POGO_CMD_ABORT			0x17
#define POGO_MODE_APP			1
#define POGO_MODE_DFU			2

/*
 * The MCU's system bootloader, from stm32_pogo_v3_start() and
 * stm32_sysboot_i2c_sync(): a second I2C address that Samsung's driver
 * instantiates first and that the application interface at 0x2a only follows.
 * A one-byte 0xFF write is the whole handshake.
 */
#define POGO_BOOT_ADDR			0x51
#define POGO_BOOT_CMD_SYNC		0xFF
#define POGO_BOOT_CMD_GET_VER		0x01
#define POGO_BOOT_CMD_READ		0x11
#define POGO_BOOT_RESP_ACK		0x79
/* Where Samsung's driver reads the MCU's IC version from flash. */
#define POGO_IC_VERSION_OFFSET		0x08000200
/* How often the application is polled while it starts. */
#define POGO_POLL_INTERVAL_MS		250
/* How long the MCU is left completely alone after its power-up. */
#define POGO_SILENT_WINDOW_MS		30000
/* The MCU's option bytes, at the address in Samsung's stm32_memory_map. */
#define POGO_OPTION_BYTE_OFFSET		0x1FFF7800
/* Samsung's header inside the firmware image; the magic there is "STM32". */
#define POGO_FW_HEADER_L0		0x080000bc
#define POGO_FW_HEADER_G0		0x080000c0

struct samsung_pogo {
	struct i2c_client *client;
	struct i2c_client *boot;
	struct input_dev *input;
	struct gpio_desc *connected;
	struct gpio_desc *announce;
	struct gpio_desc *swclk;
	struct gpio_desc *nrst;
	struct pinctrl *pinctrl;
	struct pinctrl_state *bus_gpio;
	struct gpio_desc *sda;
	struct gpio_desc *scl;
	struct regulator *vdd;
	struct mutex lock;
	struct delayed_work connect_work;
	int connect_irq;
	bool powered;
	bool event_enabled;
	bool ready;
	/* Passive detection of a live application: see the announce handler. */
	bool observe_only;
	unsigned int announce_seen;
	u8 caps;
};

static int pogo_read_mcu(struct samsung_pogo *p);
static int pogo_announce_level(struct samsung_pogo *p);
static void pogo_state_report(struct samsung_pogo *p, const char *stage);
static void pogo_bootloader_probe(struct samsung_pogo *p);
static bool pogo_boot_enter(struct samsung_pogo *p);
static void pogo_boot_disconnect(struct samsung_pogo *p);
static int pogo_wait_application(struct samsung_pogo *p, const char *entry, unsigned int timeout_ms);
static int pogo_boot_version(struct samsung_pogo *p, u8 *version);

/* Each call ends with STOP, matching the stock protocol. */
static int pogo_write(struct samsung_pogo *p, const u8 *buf, int len)
{
	int ret = i2c_master_send(p->client, buf, len);

	return ret == len ? 0 : ret < 0 ? ret : -EIO;
}

static int pogo_read(struct samsung_pogo *p, u8 *buf, int len)
{
	int ret = i2c_master_recv(p->client, buf, len);

	return ret == len ? 0 : ret < 0 ? ret : -EIO;
}

static int pogo_read_reg(struct samsung_pogo *p, u8 reg, u8 *buf, int len)
{
	u8 header[] = { 4, 0, 1 };
	int ret;

	ret = pogo_write(p, header, sizeof(header));
	if (ret)
		return ret;
	ret = pogo_write(p, &reg, 1);
	if (ret)
		return ret;
	ret = pogo_read(p, header, sizeof(header));
	if (ret)
		return ret;
	if (get_unaligned_le16(header) != len + 3 || header[2] != 1)
		return -EPROTO;
	return pogo_read(p, buf, len);
}

/* Samsung's stm32_i2c_reg_write: the same header, then the command byte. */
static int pogo_write_reg(struct samsung_pogo *p, u8 reg)
{
	u8 header[] = { 4, 0, 1 };
	int ret;

	ret = pogo_write(p, header, sizeof(header));
	if (ret)
		return ret;
	return pogo_write(p, &reg, 1);
}

static void pogo_release_keys(struct samsung_pogo *p)
{
	unsigned int key;

	for_each_set_bit(key, p->input->key, KEY_CNT)
		input_report_key(p->input, key, 0);
	input_sync(p->input);
}

/* lock held; data IRQ is disabled before power-off by the caller. */
static void pogo_power_off(struct samsung_pogo *p)
{
	int ret;

	p->ready = false;
	pogo_release_keys(p);
	if (!p->powered)
		return;
	ret = regulator_disable(p->vdd);
	if (ret)
		dev_warn(&p->client->dev, "power off failed: %d\n", ret);
	else
		p->powered = false;
}

/*
 * Bring the keyboard up once, and leave the rail on.
 *
 * The connect line is an edge source, not a presence level: the stock node sets
 * gpio62 up with IRQ_TYPE_EDGE_BOTH and bias-disable, and Samsung's own driver
 * enables the rail unconditionally and takes the model announcement over i2c as
 * the proof that a keyboard is seated.  Gating on the level is what made this
 * driver report "keyboard disconnected" first time round; cycling the rail on
 * every edge was worse - test 045 measured 37 connect interrupts and repeated
 * "rail on" lines in the first boot, because each edge reset the STM32 before it
 * could announce anything.  So the rail is enabled once and the announce
 * interrupt stays armed; the connect line is only logged, ratelimited.
 */
static void pogo_connect_work(struct work_struct *work)
{
	struct samsung_pogo *p = container_of(to_delayed_work(work),
					     struct samsung_pogo, connect_work);
	int conn, ret;

	mutex_lock(&p->lock);
	conn = gpiod_get_value_cansleep(p->connected);
	if (!p->powered) {
		/*
		 * The first bring-up does exactly what the stock driver does on
		 * this device: hold SWCLK (BOOT0) low, leave NRST alone (its
		 * pinctrl default is output-high), switch the rail and read the
		 * application.  No SWCLK dance, no NRST pulse, no 0x51 access
		 * before the application has had its chance - test 055 showed the
		 * stock stack reaches a running application without ever entering
		 * the system bootloader, and the bootloader stays only as the
		 * fallback below.
		 */
		/*
		 * Stock's own cycle, from the captured bring-up trace: the rail is
		 * switched off, left off for ~400 ms, switched on again with SWCLK
		 * (BOOT0) held low and NRST untouched, and the event interrupt is
		 * enabled 50 ms later.  The MCU then announces itself ~135 ms after
		 * the rail rose, with no host transaction in between.
		 */
		gpiod_set_value_cansleep(p->swclk, 0);
		regulator_disable(p->vdd);
		msleep(400);
		if (!regulator_enable(p->vdd)) {
			p->powered = true;
			msleep(50);
			p->announce_seen = 0;
			p->observe_only = false;
			enable_irq(p->client->irq);
			dev_info(&p->client->dev,
				 "MCU rail on with BOOT0 low, announce line armed (level %d)\n",
				 pogo_announce_level(p));
			/* Who is there, before anything else is touched. */
			pogo_state_report(p, "right after the rail cycle");
			/* Read-only poll; nothing in this window changes a pin. */
			ret = pogo_read_mcu(p);
			dev_info(&p->client->dev,
				 "application poll finished (%d), %u announcement(s), announce level %d\n",
				 ret, p->announce_seen, pogo_announce_level(p));
			if (!ret) {
				dev_info(&p->client->dev, "MCU application running\n");
			} else {
				dev_info(&p->client->dev,
					 "MCU application did not answer; entering its bootloader\n");
				pogo_bootloader_probe(p);
				pogo_read_mcu(p);
			}
			p->event_enabled = true;
		} else {
			dev_err(&p->client->dev, "power on failed\n");
		}
	}
	/*
	 * Diagnostic only, and at debug level: the line is a bias-disable input
	 * that a floating connector toggles at about 10 Hz, which flooded the
	 * panel console when this was dev_info_ratelimited.
	 */
	dev_dbg(&p->client->dev, "connect line reads %d\n", conn);
	mutex_unlock(&p->lock);
}

static irqreturn_t pogo_connect_irq(int irq, void *data)
{
	struct samsung_pogo *p = data;

	mod_delayed_work(system_percpu_wq, &p->connect_work, msecs_to_jiffies(20));
	return IRQ_HANDLED;
}

/*
 * Ask the MCU's system bootloader whether the part is running at all.
 *
 * Samsung's driver instantiates 0x51 before anything else and runs its firmware
 * menu there, and its own log shows the application answering first try with no
 * reset - the MCU is already running by the time it probes.  In mainline it is
 * not, and every application read NAKs, so the question this answers is whether
 * the part is powered and executing at all: SWCLK is held high across NRST as
 * stm32_sysboot_connect() does, and a single 0xFF write to the bootloader either
 * transfers or it does not.
 */
/* stm32_sysboot_connect(): SWCLK high across NRST selects the bootloader. */
static void pogo_boot_reset(struct samsung_pogo *p)
{
	gpiod_set_value_cansleep(p->nrst, 0);
	gpiod_set_value_cansleep(p->swclk, 1);
	msleep(3);
	gpiod_set_value_cansleep(p->nrst, 1);
	msleep(50); /* STM32_BOOT_I2C_STARTUP_DELAY */
	gpiod_set_value_cansleep(p->swclk, 0);
}

static bool pogo_boot_enter(struct samsung_pogo *p)
{
	u8 sync = POGO_BOOT_CMD_SYNC;

	if (!p->boot)
		return false;

	pogo_boot_reset(p);
	if (i2c_master_send(p->boot, &sync, 1) != 1)
		return false;

	/*
	 * Stock's I2C connect STEP3 resets again after the unknown-command
	 * probe.  Do not send another 0xFF in the new session: the following
	 * Get Version/GO must start with a clean command parser.
	 */
	pogo_boot_reset(p);
	return true;
}

/*
 * STM32 AN4221 framing: a command or an address goes out as those bytes followed
 * by their XOR, and each is acknowledged.
 */
static int pogo_boot_xfer(struct samsung_pogo *p, const u8 *buf, size_t len)
{
	u8 resp = 0;

	if (i2c_master_send(p->boot, buf, len) != len)
		return -EIO;
	if (i2c_master_recv(p->boot, &resp, 1) != 1 || resp != POGO_BOOT_RESP_ACK)
		return -EPROTO;
	return 0;
}

/* READ (0x11): command, address, length, then the data. */
static int pogo_boot_read(struct samsung_pogo *p, u32 addr, u8 *buf, u16 len)
{
	u8 cmd[2] = { POGO_BOOT_CMD_READ, ~POGO_BOOT_CMD_READ };
	u8 ab[5], nb[2];
	int ret;

	ab[0] = addr >> 24; ab[1] = addr >> 16; ab[2] = addr >> 8; ab[3] = addr;
	ab[4] = ab[0] ^ ab[1] ^ ab[2] ^ ab[3];
	nb[0] = len - 1;
	/* Samsung sends the byte count and its complement, then waits for the ACK. */
	nb[1] = ~nb[0];

	ret = pogo_boot_xfer(p, cmd, sizeof(cmd));
	if (ret)
		return ret;
	ret = pogo_boot_xfer(p, ab, sizeof(ab));
	if (ret)
		return ret;
	ret = pogo_boot_xfer(p, nb, sizeof(nb));
	if (ret)
		return ret;
	if (i2c_master_recv(p->boot, buf, len) != len)
		return -EIO;
	return 0;
}

/*
 * The IC version lives in flash at 0x08000200 and is only reachable through the
 * bootloader.  Stock reads it here on every boot and prints the last byte as
 * mcu_fw(ic):34, so it is both useful and a check on this READ path.
 */
static int pogo_boot_ic_version(struct samsung_pogo *p, u8 *version)
{
	int ret = pogo_boot_read(p, POGO_IC_VERSION_OFFSET, version, 4);

	if (ret)
		dev_info(&p->client->dev, "could not read the IC version (%d)\n", ret);
	else
		dev_info(&p->client->dev, "MCU IC version %*phN\n", 4, version);

	return ret;
}

static u32 pogo_le32(const u8 *p)
{
	return p[0] | p[1] << 8 | p[2] << 16 | (u32)p[3] << 24;
}

/*
 * Where the firmware header is and what it says.
 *
 * Test 049 read 0x08000000 and got a Cortex-M vector table (SP 0x200056c0,
 * reset vector 0x0800c4a5), so the application image starts there and Samsung's
 * header - whose magic is the ASCII "STM32" (stm32_pogo_cmd_v3.c) - sits at file
 * offset 0xbc (L0) or 0xc0 (G0) inside that image.  The bank addresses and
 * status_boot_mode are worth having: they say which bank holds the application
 * and whether the part considers itself in application or update mode.
 */
static void pogo_boot_dump_header(struct samsung_pogo *p)
{
	u8 hdr[48];
	u32 addr = POGO_FW_HEADER_G0;
	int ret;

	ret = pogo_boot_read(p, addr, hdr, sizeof(hdr));
	if (ret)
		goto failed;
	if (memcmp(hdr, "STM32", 5)) {
		addr = POGO_FW_HEADER_L0;
		ret = pogo_boot_read(p, addr, hdr, sizeof(hdr));
		if (ret)
			goto failed;
	}
	if (memcmp(hdr, "STM32", 5)) {
		dev_info(&p->client->dev,
			 "no STM32 header at %#x or %#x, first bytes %*phN\n",
			 POGO_FW_HEADER_G0, POGO_FW_HEADER_L0, 16, hdr);
		return;
	}
	dev_info(&p->client->dev,
		 "MCU firmware header at %#x: magic %.5s status %#x boot %u.%u target %u.%u boot bank %#x target bank %#x\n",
		 addr, hdr, pogo_le32(hdr + 8),
		 hdr[23], hdr[22], hdr[27], hdr[26],
		 pogo_le32(hdr + 28), pogo_le32(hdr + 32));
	return;
failed:
	dev_info(&p->client->dev, "could not read the firmware header (%d)\n", ret);
}

/*
 * Samsung's stm32_target_option_update() reads the option bytes on every boot and
 * clears bit 24 when it is set, then reconnects.  This port has never done that
 * step, so the first question is what the word actually holds: read only, and say
 * whether the vendor's write would do anything at all.
 */
static void pogo_boot_dump_option_bytes(struct samsung_pogo *p)
{
	u8 ob[4];
	u32 word;
	int ret;

	ret = pogo_boot_read(p, POGO_OPTION_BYTE_OFFSET, ob, sizeof(ob));
	if (ret) {
		dev_info(&p->client->dev, "could not read the option bytes (%d)\n", ret);
		return;
	}
	word = pogo_le32(ob);
	dev_info(&p->client->dev,
		 "MCU option bytes %#x: RDP %#x, bit 24 %s\n",
		 word, word & 0xff, (word & BIT(24)) ? "set (stock clears it)" : "clear");
}

/*
 * The MCU drives its announce line itself, so its level is the only signal that
 * says anything about the application without the host speaking first.  Stock's
 * status line prints it as int:1 while the application runs; here it is read
 * from the irqchip rather than inferred from whether the interrupt fired, so
 * that a floating line cannot be mistaken for an announcement.
 */
static int pogo_announce_level(struct samsung_pogo *p)
{
	if (!p->announce)
		return -1;
	return gpiod_get_value_cansleep(p->announce);
}

/*
 * Ask the part what it is, without changing anything.
 *
 * The announce line says the MCU is alive (test 067) but not which interface it
 * serves, and the two are mutually exclusive: if the bootloader at 0x51 answers
 * on its own the part is sitting in its system bootloader, and if only 0x2a
 * answers it runs its application interface.  No dance, no reset, no GO - both
 * probes are plain reads.
 */
static void pogo_state_report(struct samsung_pogo *p, const char *stage)
{
	u8 version[4], boot_version;
	int app, boot;

	app = pogo_read_reg(p, POGO_CMD_CHECK_VERSION, version, sizeof(version));
	boot = pogo_boot_version(p, &boot_version);
	dev_info(&p->client->dev,
		 "%s: application %d, bootloader %d, announce level %d\n",
		 stage, app, boot, pogo_announce_level(p));
}

/*
 * Which interface answers right now.  The bootloader at 0x51 and the keyboard
 * application at 0x2a are mutually exclusive, so this is how the port tells a
 * running application from a part that stayed in its bootloader.
 */
static void pogo_boot_report(struct samsung_pogo *p, const char *stage)
{
	u8 version[4], boot_version;
	int app, boot;

	app = pogo_read_reg(p, POGO_CMD_CHECK_VERSION, version, sizeof(version));
	boot = pogo_boot_version(p, &boot_version);
	dev_info(&p->client->dev, "%s: application %d, bootloader %d, connect %d\n",
		 stage, app, boot, gpiod_get_value_cansleep(p->connected));
}

/*
 * How the application is started, from stm32_sysboot_disconnect(): BOOT0 (the
 * SWCLK line) low, then one NRST pulse, then a 150 ms settle.  Stock runs this
 * on every boot - after the bootloader has answered, and without ever sending
 * GO.  GO 0x08000000 was acknowledged here but started nothing (tests 047, 048
 * and 049), and after a GO the MCU stopped answering on either address, so the
 * vendor's own way out of the bootloader is the one to use.
 */
static void pogo_boot_disconnect(struct samsung_pogo *p)
{
	gpiod_set_value_cansleep(p->swclk, 0);
	msleep(1);
	gpiod_set_value_cansleep(p->nrst, 0);
	msleep(2); /* STM32_BOOT_I2C_STARTUP_DELAY_NRST */
	gpiod_set_value_cansleep(p->nrst, 1);
	msleep(150);
}

/* AN4221 Get Version returns ACK, version, ACK in separate read frames. */
static int pogo_boot_version(struct samsung_pogo *p, u8 *version)
{
	static const u8 cmd[] = { POGO_BOOT_CMD_GET_VER, ~POGO_BOOT_CMD_GET_VER };
	u8 ack;
	int ret;

	ret = i2c_master_send(p->boot, cmd, sizeof(cmd));
	if (ret != sizeof(cmd))
		return ret < 0 ? ret : -EIO;
	ret = i2c_master_recv(p->boot, &ack, 1);
	if (ret != 1)
		return ret < 0 ? ret : -EIO;
	if (ack != POGO_BOOT_RESP_ACK)
		return -EPROTO;
	ret = i2c_master_recv(p->boot, version, 1);
	if (ret != 1)
		return ret < 0 ? ret : -EIO;
	ret = i2c_master_recv(p->boot, &ack, 1);
	if (ret != 1)
		return ret < 0 ? ret : -EIO;
	return ack == POGO_BOOT_RESP_ACK ? 0 : -EPROTO;
}

/*
 * A GO ACK is not application readiness.  Test 047 reset the MCU after the
 * first NACK at 150 ms, so it never measured a slower, uninterrupted start.
 * Allow five seconds of read-only polling before considering a reset fallback.
 */
static int pogo_wait_application(struct samsung_pogo *p, const char *entry,
				 unsigned int timeout_ms)
{
	unsigned long start = jiffies;
	unsigned long deadline = start + msecs_to_jiffies(timeout_ms);
	u8 version[4];
	int ret;

	msleep(150);
	for (;;) {
		ret = pogo_read_reg(p, POGO_CMD_CHECK_VERSION, version, sizeof(version));
		if (!ret || time_after_eq(jiffies, deadline))
			break;
		msleep(100);
	}
	dev_info(&p->client->dev,
		 "application after %s: %d after %u ms without reset%s\n",
		 entry, ret, jiffies_to_msecs(jiffies - start),
		 ret ? " (no version response)" : " (version received)");
	return ret;
}

/*
 * Get the MCU into its application.
 *
 * Samsung's driver never has to: its log shows the application answering on the
 * first attempt with no reset at all (rst:0), so something earlier - the
 * bootloader, in the boot it runs from - has already started it.  In mainline the
 * part sits in its system bootloader instead: it takes the 0xFF sync and reports
 * version 0x12, and the application at 0x2a never answers.
 *
 * Try GO in a completed bootloader session first, then the vendor's
 * reset-based stm32_sysboot_disconnect() if the application still fails.
 */
static void pogo_bootloader_probe(struct samsung_pogo *p)
{
	u8 boot_version, ic_version[4];
	int ret;

	if (!pogo_boot_enter(p)) {
		dev_info(&p->client->dev,
			 "MCU bootloader did not take the 0xFF sync\n");
		return;
	}
	dev_info(&p->client->dev, "MCU bootloader took the 0xFF sync\n");

	ret = pogo_boot_version(p, &boot_version);
	if (ret) {
		dev_info(&p->client->dev, "bootloader version exchange failed: %d\n", ret);
		/* An incomplete reply must not become the next command's ACK. */
		if (!pogo_boot_enter(p))
			return;
	} else {
		dev_info(&p->client->dev, "MCU bootloader version %#x\n", boot_version);
	}

	/*
	 * Stock reads the IC version and then leaves the bootloader the vendor's
	 * way.  Never send GO: it was acknowledged but started nothing, and it
	 * left the MCU answering on neither address.
	 */
	pogo_boot_ic_version(p, ic_version);
	pogo_boot_dump_header(p);
	pogo_boot_dump_option_bytes(p);
	pogo_boot_disconnect(p);
	pogo_boot_report(p, "after the disconnected reset");
	pogo_wait_application(p, "bootloader start", 30000);
	pogo_boot_report(p, "five seconds later");
}

/*
 * Free a bus the keyboard may be holding, and report the line levels.
 *
 * The controller's two pins are multiplexed to qup2_se7, so gpiolib will not hand
 * them out while that state is selected; the "recovery" pinctrl state moves them
 * to plain GPIOs for the duration.  Nine clocks plus a STOP is the standard I2C
 * bus recovery, and the levels printed here are the measurement Samsung's own
 * driver takes when a transfer fails.
 */
static void pogo_recover_bus(struct samsung_pogo *p)
{
	struct gpio_desc *sda, *scl;
	int i;

	if (!p->bus_gpio)
		return;
	if (pinctrl_select_state(p->pinctrl, p->bus_gpio))
		return;

	sda = gpiod_get_optional(&p->client->dev, "sda", GPIOD_IN);
	scl = gpiod_get_optional(&p->client->dev, "scl", GPIOD_IN);
	if (IS_ERR(sda))
		sda = NULL;
	if (IS_ERR(scl))
		scl = NULL;

	dev_info(&p->client->dev, "bus before recovery: scl:%d sda:%d conn:%d\n",
		 scl ? gpiod_get_value_cansleep(scl) : -1,
		 sda ? gpiod_get_value_cansleep(sda) : -1,
		 gpiod_get_value_cansleep(p->connected));

	if (sda && scl) {
		gpiod_direction_output(scl, 1);
		gpiod_direction_output(sda, 1);
		for (i = 0; i < 9; i++) {
			gpiod_set_value_cansleep(scl, 0);
			udelay(5);
			gpiod_set_value_cansleep(scl, 1);
			udelay(5);
		}
		/* STOP: SDA released while SCL is high. */
		gpiod_set_value_cansleep(sda, 0);
		udelay(5);
		gpiod_set_value_cansleep(scl, 1);
		udelay(5);
		gpiod_set_value_cansleep(sda, 1);
		udelay(5);

		dev_info(&p->client->dev, "bus after recovery: scl:%d sda:%d\n",
			 gpiod_get_value_cansleep(scl),
			 gpiod_get_value_cansleep(sda));
		gpiod_put(sda);
		gpiod_put(scl);
	}

	pinctrl_select_state(p->pinctrl,
			     pinctrl_lookup_state(p->pinctrl, "default"));
}

static void pogo_scan_bus(struct samsung_pogo *p)
{
	struct i2c_adapter *adap = p->client->adapter;
	union i2c_smbus_data dummy;
	char found[96];
	int i, n = 0;

	for (i = 0x08; i < 0x78 && n < (int)sizeof(found) - 7; i++) {
		if (i2c_smbus_xfer(adap, i, 0, I2C_SMBUS_WRITE, 0,
				   I2C_SMBUS_QUICK, &dummy) < 0)
			continue;
		n += scnprintf(found + n, sizeof(found) - n, " %#x", i);
	}
	dev_info(&p->client->dev, "i2c-%d answers at:%s\n", adap->nr,
		 n ? found : " (nothing)");
}

static int pogo_read_mcu(struct samsung_pogo *p)
{
	u8 version[4], mode;
	int ret, i;

	p->ready = false;

	/*
	 * Wait for the application instead of resetting it.
	 *
	 * Stock's driver first reads the version tens of seconds into the boot
	 * (33 s in its own log) and never resets the part to get there, while
	 * this port polled at 4 s and then pulsed NRST every ~50 ms.  If the
	 * application needs time from power-on to bring its I2C slave up, that
	 * loop restarts it forever: which is what the logs show - the connect
	 * line reads 1 at power-on and 0 after the first reset, and no address
	 * answers afterwards.  So poll patiently and touch nothing.
	 */
	for (i = 0; i < 240; i++) {
		ret = pogo_read_reg(p, POGO_CMD_CHECK_VERSION, version,
				    sizeof(version));
		if (!ret)
			break;
		/*
		 * Absolutely no side effects in this window: no bus recovery (that
		 * bit-bangs SCL/SDA and switches the controller's pinmux), no
		 * pinctrl change, no reset and no bootloader access.  Test 060 is
		 * the first candidate that leaves the application's bus, pins and
		 * power completely alone while it starts.
		 */
		if (!i)
			dev_info(&p->client->dev,
				 "waiting up to %u ms for the MCU application\n",
				 240 * POGO_POLL_INTERVAL_MS);
		if (!(i % 10))
			/* Copy the vendor's own diagnostic levels. */
			dev_info(&p->client->dev,
				 "no answer after %u ms: scl:%d sda:%d conn:%d\n",
				 i * POGO_POLL_INTERVAL_MS,
				 p->scl ? gpiod_get_value_cansleep(p->scl) : -1,
				 p->sda ? gpiod_get_value_cansleep(p->sda) : -1,
				 gpiod_get_value_cansleep(p->connected));
		msleep(POGO_POLL_INTERVAL_MS);
	}
	if (ret) {
		dev_info(&p->client->dev,
			 "no answer from the MCU application after %u ms (%d)\n",
			 i * POGO_POLL_INTERVAL_MS, ret);
		/*
		 * Diagnostics only, and only now: the recovery bit-bangs SCL/SDA
		 * and moves the controller's pinmux, and the scan talks to every
		 * address, so neither belongs in a window that is supposed to
		 * leave the application alone.
		 */
		pogo_recover_bus(p);
		pogo_scan_bus(p);
		return ret;
	}
	if (i)
		dev_info(&p->client->dev,
			 "MCU application answered after %u ms\n",
			 i * POGO_POLL_INTERVAL_MS);
	ret = pogo_read_reg(p, POGO_CMD_GET_MODE, &mode, sizeof(mode));
	if (ret) {
		dev_info(&p->client->dev, "MCU answered, mode read failed (%d)\n", ret);
		return ret;
	}
	if (mode == POGO_MODE_DFU) {
		/*
		 * Samsung's stm32_set_mode(MODE_APP): a part left in DFU mode is
		 * told to abort the update and start the application, and only
		 * then is it asked again.
		 */
		dev_info(&p->client->dev, "MCU is in DFU mode; asking for the application\n");
		ret = pogo_write_reg(p, POGO_CMD_ABORT);
		msleep(200);
		if (!ret)
			ret = pogo_read_reg(p, POGO_CMD_GET_MODE, &mode, sizeof(mode));
		if (ret) {
			dev_info(&p->client->dev, "MCU did not leave DFU mode (%d)\n", ret);
			return ret;
		}
	}
	p->ready = mode == POGO_MODE_APP;
	dev_info(&p->client->dev,
		 "MCU model %#x hw %u firmware %u.%u mode %u%s\n",
		 version[1], version[0], version[3], version[2], mode,
		 p->ready ? "" : " (not in application mode)");
	return 0;
}

static int pogo_hello(struct samsung_pogo *p, u8 model)
{
	int ret;

	p->ready = false;
	pogo_release_keys(p);
	if (model != POGO_MODEL_DX710)
		dev_warn(&p->client->dev, "announced keyboard model %#x\n", model);
	ret = pogo_read_mcu(p);
	/* Never attempt to rewrite keyboard firmware. */
	return ret;
}

static irqreturn_t pogo_irq(int irq, void *data)
{
	struct samsung_pogo *p = data;
	u8 header[] = { 3, 0, READ_ONCE(p->caps) };
	u8 payload[POGO_MAX_PAYLOAD];
	unsigned int size, i, key;
	u16 event;
	int ret = 0;

	/*
	 * Passive evidence that the application is alive: this line is the MCU's
	 * own announce/attention interrupt, so it is asserted by the application
	 * and by nothing else.  While observing, do not touch the bus - one
	 * interrupt is enough to answer the question, and servicing it would put
	 * traffic on a bus that is deliberately being left alone.
	 */
	/*
	 * The application announces itself on this line within ~150 ms of its
	 * power-up in the stock stack, before any host transaction.  Counting it
	 * is how this port tells "the application started" from "the line is
	 * quiet", which is the one difference tests 058-063 kept hitting.
	 */
	p->announce_seen++;
	if (p->announce_seen < 4)
		dev_info(&p->client->dev, "MCU announced itself (%u)\n",
			 p->announce_seen);

	mutex_lock(&p->lock);
	/*
	 * Only the rail matters here.  The connect line is an edge source with
	 * bias-disable, so its level must not decide whether the keyboard may
	 * speak: the model announcement is what proves it is there.
	 */
	if (!p->powered)
		goto out;
	ret = pogo_write(p, header, sizeof(header));
	if (ret)
		goto error;
	ret = pogo_read(p, header, sizeof(header));
	if (ret)
		goto error;
	size = get_unaligned_le16(header);
	/* Stock treats an empty startup header as a model announcement. */
	if (size == 0 || size == 3) {
		ret = pogo_hello(p, header[2]);
		if (ret)
			goto error;
		goto out;
	}
	if (size < 3 || size > sizeof(payload) + 3) {
		dev_warn_ratelimited(&p->client->dev, "invalid header size %u id %#x\n",
				     size, header[2]);
		ret = -EPROTO;
		goto error;
	}
	size -= 3;
	ret = pogo_read(p, payload, size);
	if (ret)
		goto error;
	/* Stock noise signature, checked only when all three bytes exist. */
	if (size >= 3 && payload[0] == 3 && payload[1] == 0 && payload[2] == 5)
		goto out;
	if (header[2] == 3 && p->ready) {
		if (size % 2) {
			ret = -EPROTO;
			goto error;
		}
		/* Validate the complete packet before changing key state. */
		for (i = 0; i < size; i += 2) {
			key = get_unaligned_le16(payload + i) & 0x7fff;
			if (key >= KEY_CNT || !test_bit(key, p->input->keybit)) {
				ret = -EPROTO;
				goto error;
			}
		}
		for (i = 0; i < size; i += 2) {
			event = get_unaligned_le16(payload + i);
			input_report_key(p->input, event & 0x7fff, !!(event & 0x8000));
			input_sync(p->input);
		}
	} else if (header[2] == 4 || header[2] == 5) {
		/* Hall/cover/accessory changes must not leave keys pressed. */
		pogo_release_keys(p);
	}
	goto out;
error:
	pogo_release_keys(p);
	dev_err_ratelimited(&p->client->dev, "event transfer failed: %d\n", ret);
	/* Avoid a tight level-low interrupt storm on a failed bus. */
	msleep(20);
out:
	mutex_unlock(&p->lock);
	return IRQ_HANDLED;
}

static int pogo_led(struct input_dev *input, unsigned int type,
		    unsigned int code, int value)
{
	struct samsung_pogo *p = input_get_drvdata(input);

	if (type != EV_LED || code != LED_CAPSL)
		return -EINVAL;
	/* Stock piggybacks Caps Lock state on the next event request. */
	WRITE_ONCE(p->caps, value ? 2 : 1);
	return 0;
}

static void pogo_stop(void *data)
{
	struct samsung_pogo *p = data;

	disable_irq(p->connect_irq);
	cancel_delayed_work_sync(&p->connect_work);
	if (p->event_enabled) {
		disable_irq(p->client->irq);
		p->event_enabled = false;
	}
	mutex_lock(&p->lock);
	pogo_power_off(p);
	mutex_unlock(&p->lock);
}

static int pogo_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct samsung_pogo *p;
	unsigned int key;
	int ret;

	if (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -EOPNOTSUPP;
	if (client->irq <= 0)
		return -EINVAL;
	p = devm_kzalloc(dev, sizeof(*p), GFP_KERNEL);
	if (!p)
		return -ENOMEM;
	p->client = client;
	p->caps = 1;
	mutex_init(&p->lock);
	INIT_DELAYED_WORK(&p->connect_work, pogo_connect_work);
	p->connected = devm_gpiod_get(dev, "connect", GPIOD_IN);
	p->announce = devm_gpiod_get_optional(&p->client->dev, "announce", GPIOD_IN);
	if (IS_ERR(p->connected))
		return dev_err_probe(dev, PTR_ERR(p->connected), "connect GPIO\n");
	/*
	 * The MCU's SWD pins, owned here rather than left to the pinctrl default:
	 * the STM32 boots into its keyboard firmware only if SWCLK is low when
	 * NRST is released, and Samsung's own driver takes both explicitly
	 * (stm32,mcu_swclk / stm32,mcu_nrst).
	 */
	p->swclk = devm_gpiod_get(dev, "swclk", GPIOD_OUT_LOW);
	if (IS_ERR(p->swclk))
		return dev_err_probe(dev, PTR_ERR(p->swclk), "swclk GPIO\n");
	p->nrst = devm_gpiod_get(dev, "nrst", GPIOD_OUT_HIGH);
	if (IS_ERR(p->nrst))
		return dev_err_probe(dev, PTR_ERR(p->nrst), "nrst GPIO\n");
	/*
	 * The I2C lines, as inputs and only for diagnostics: the pins stay
	 * multiplexed to the controller by the i2c node's pinctrl state, and
	 * reading the input buffer is how Samsung's driver reports a held bus.
	 */
	/*
	 * A pinctrl state that moves the controller's SDA/SCL back to plain
	 * GPIOs, for bus recovery.  The pins belong to qup2_se7 the rest of the
	 * time, which is why gpiolib refuses to hand them out while that state
	 * is selected.
	 */
	p->boot = devm_i2c_new_dummy_device(dev, client->adapter, POGO_BOOT_ADDR);
	if (IS_ERR(p->boot)) {
		dev_info(dev, "no bootloader client at %#x: %ld\n",
			 POGO_BOOT_ADDR, PTR_ERR(p->boot));
		p->boot = NULL;
	}
	p->pinctrl = devm_pinctrl_get(dev);
	if (IS_ERR(p->pinctrl)) {
		p->pinctrl = NULL;
	} else {
		p->bus_gpio = pinctrl_lookup_state(p->pinctrl, "recovery");
		if (IS_ERR(p->bus_gpio))
			p->bus_gpio = NULL;
	}
	p->vdd = devm_regulator_get(dev, "vdd");
	if (IS_ERR(p->vdd))
		return dev_err_probe(dev, PTR_ERR(p->vdd), "vdd supply\n");
	p->input = devm_input_allocate_device(dev);
	if (!p->input)
		return -ENOMEM;
	p->input->name = "Book Cover Keyboard Slim (EF-DX710)";
	p->input->id.bustype = BUS_I2C;
	p->input->id.vendor = 0x04e8;
	p->input->id.product = 0xa035;
	p->input->event = pogo_led;
	input_set_drvdata(p->input, p);
	input_set_capability(p->input, EV_LED, LED_CAPSL);
	__set_bit(EV_REP, p->input->evbit);
	for (key = 1; key < 762 && key < KEY_CNT; key++) {
		if ((key >= BTN_GAMEPAD && key <= BTN_THUMBR) || key == BTN_TOUCH)
			continue;
		input_set_capability(p->input, EV_KEY, key);
	}
	ret = input_register_device(p->input);
	if (ret)
		return ret;
	i2c_set_clientdata(client, p);
	p->connect_irq = gpiod_to_irq(p->connected);
	if (p->connect_irq < 0)
		return p->connect_irq;
	ret = devm_request_threaded_irq(dev, client->irq, NULL, pogo_irq,
			IRQF_ONESHOT | IRQF_NO_AUTOEN, dev_name(dev), p);
	if (ret)
		return dev_err_probe(dev, ret, "event IRQ\n");
	ret = devm_request_threaded_irq(dev, p->connect_irq, NULL, pogo_connect_irq,
			IRQF_ONESHOT | IRQF_TRIGGER_RISING | IRQF_TRIGGER_FALLING |
			IRQF_NO_AUTOEN, "pogo-connect", p);
	if (ret)
		return dev_err_probe(dev, ret, "connect IRQ\n");
	/* Add cleanup before allowing work to start; IRQs are freed after it. */
	ret = devm_add_action_or_reset(dev, pogo_stop, p);
	if (ret)
		return ret;
	enable_irq(p->connect_irq);
	mod_delayed_work(system_percpu_wq, &p->connect_work, 0);
	return 0;
}

static int pogo_suspend(struct device *dev)
{
	pogo_stop(i2c_get_clientdata(to_i2c_client(dev)));
	return 0;
}

static int pogo_resume(struct device *dev)
{
	struct samsung_pogo *p = i2c_get_clientdata(to_i2c_client(dev));

	enable_irq(p->connect_irq);
	mod_delayed_work(system_percpu_wq, &p->connect_work, 0);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(pogo_pm_ops, pogo_suspend, pogo_resume);
static const struct of_device_id pogo_of_match[] = {
	{ .compatible = "samsung,x710-pogo-keyboard" },
	{ }
};
MODULE_DEVICE_TABLE(of, pogo_of_match);

static struct i2c_driver pogo_driver = {
	.probe = pogo_probe,
	.driver = {
		.name = "samsung-pogo-keyboard",
		.of_match_table = pogo_of_match,
		.pm = pm_sleep_ptr(&pogo_pm_ops),
	},
};
module_i2c_driver(pogo_driver);
MODULE_DESCRIPTION("Samsung X710 STM32 pogo keyboard");
MODULE_LICENSE("GPL");
