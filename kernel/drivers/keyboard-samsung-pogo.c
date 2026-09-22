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

/*
 * The MCU's system bootloader, from stm32_pogo_v3_start() and
 * stm32_sysboot_i2c_sync(): a second I2C address that Samsung's driver
 * instantiates first and that the application interface at 0x2a only follows.
 * A one-byte 0xFF write is the whole handshake.
 */
#define POGO_BOOT_ADDR			0x51
#define POGO_BOOT_CMD_SYNC		0xFF
#define POGO_BOOT_CMD_GET_VER		0x01
#define POGO_BOOT_CMD_GO		0x21
#define POGO_BOOT_RESP_ACK		0x79

struct samsung_pogo {
	struct i2c_client *client;
	struct i2c_client *boot;
	struct input_dev *input;
	struct gpio_desc *connected;
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
	u8 caps;
};

static int pogo_read_mcu(struct samsung_pogo *p);
static void pogo_bootloader_probe(struct samsung_pogo *p);
static bool pogo_boot_enter(struct samsung_pogo *p);
static void pogo_boot_go(struct samsung_pogo *p);

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
		u8 version[4];

		/*
		 * Ask the application first, without changing anything.  Stock's log
		 * shows rst:0 - the application was already running when its driver
		 * probed - and that driver never powers the rail, pulses NRST or
		 * enters the bootloader to get there: the bootloader has started it
		 * already, and every reset this port performs is a chance to lose it.
		 */
		if (!regulator_enable(p->vdd)) {
			p->powered = true;
			msleep(20);
			ret = pogo_read_reg(p, POGO_CMD_CHECK_VERSION,
					    version, sizeof(version));
			if (ret) {
				dev_info(&p->client->dev,
					 "MCU application did not answer; entering its bootloader\n");
				pogo_bootloader_probe(p);
			} else {
				dev_info(&p->client->dev,
					 "MCU application already running, version %u.%u\n",
					 version[3], version[2]);
			}
			/* Preserve a successful app entry; check mode before accepting keys. */
			pogo_read_mcu(p);
			p->event_enabled = true;
			enable_irq(p->client->irq);
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
 * STM32 AN4221 GO: the command, then the address with its XOR checksum.
 *
 * Stock has the case but only sets cmd[0] and breaks, so it never sends the
 * address and never worked; the frame is 0x21, its complement, the four address
 * bytes big-endian, and the XOR of those bytes.  Every step is acknowledged.
 */
static void pogo_boot_go(struct samsung_pogo *p)
{
	static const u8 cmd[] = { POGO_BOOT_CMD_GO, ~POGO_BOOT_CMD_GO };
	static const u8 addr[] = { 0x08, 0x00, 0x00, 0x00, 0x08 };
	u8 resp = 0;

	if (i2c_master_send(p->boot, cmd, sizeof(cmd)) != sizeof(cmd)) {
		dev_info(&p->client->dev, "bootloader GO command refused\n");
		return;
	}
	if (i2c_master_recv(p->boot, &resp, 1) != 1 || resp != POGO_BOOT_RESP_ACK) {
		dev_info(&p->client->dev, "bootloader GO command not acked (%#x)\n", resp);
		return;
	}
	if (i2c_master_send(p->boot, addr, sizeof(addr)) != sizeof(addr)) {
		dev_info(&p->client->dev, "bootloader GO address refused\n");
		return;
	}
	resp = 0;
	if (i2c_master_recv(p->boot, &resp, 1) == 1 && resp == POGO_BOOT_RESP_ACK)
		dev_info(&p->client->dev,
			 "MCU bootloader accepted GO 0x08000000, application should be running\n");
	else
		dev_info(&p->client->dev, "bootloader GO address not acked (%#x)\n", resp);
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
static int pogo_wait_application(struct samsung_pogo *p, const char *entry)
{
	unsigned long start = jiffies;
	unsigned long deadline = start + msecs_to_jiffies(5000);
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
	u8 boot_version;
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
		/* An incomplete reply must not become GO's command ACK. */
		if (!pogo_boot_enter(p))
			return;
	} else {
		dev_info(&p->client->dev, "MCU bootloader version %#x\n", boot_version);
	}

	/*
	 * Jump while the bootloader is still listening: the earlier attempt went
	 * out after the disconnect and timed out because by then the MCU answered
	 * on neither interface.
	 */
	pogo_boot_go(p);
	ret = pogo_wait_application(p, "GO");
	if (!ret)
		return;

	/* No GO either: fall back to the vendor's reset-based entry. */
	gpiod_set_value_cansleep(p->swclk, 0);
	msleep(1);
	gpiod_set_value_cansleep(p->nrst, 0);
	msleep(2);
	gpiod_set_value_cansleep(p->nrst, 1);
	pogo_wait_application(p, "reset entry");
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

/*
 * What is actually on this bus?
 *
 * The stock firmware answers at 0x2a on the same controller and the same two
 * pins (gpio72/gpio106, qup2_se7), while mainline gets a clean -ENXIO from every
 * attempt - a NACK means the bus is idle and nobody acknowledged, not that the
 * bus is stuck.  An STM32 that came up in its ROM bootloader answers at a
 * different address, and one that never powered answers at none, so scan once
 * and put the answer in the bring-up report.
 */
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

/*
 * Ask the MCU who it is: STM32_CMD_CHECK_VERSION returns hw revision, model id,
 * firmware minor and major, and STM32_CMD_GET_MODE says whether it is running
 * the keyboard application.  Samsung's driver polls exactly this pair and
 * retries, and it is the real presence test - an unsolicited announcement is not
 * how the stock part introduces itself, which is why a driver that only listened
 * for one never got past "awaiting the model announcement" on hardware that
 * TWRP's stock kernel enumerated as EF-DX710_v1.4.1.0, model_id 0x2.
 */
static int pogo_read_mcu(struct samsung_pogo *p)
{
	u8 version[4], mode;
	int ret, i;

	p->ready = false;

	for (i = 0; i < 40; i++) {
		ret = pogo_read_reg(p, POGO_CMD_CHECK_VERSION, version,
				    sizeof(version));
		if (!ret)
			break;
		/* Do not disturb a working application or its bus pinmux. */
		if (!i)
			pogo_recover_bus(p);
		/*
		 * Copy the vendor's own diagnostic: its I2C failure path prints
		 * the raw SCL and SDA levels (stm32_pogo_i2c_v3.c), which is what
		 * separates "the bus is being held" from "the bus is idle and the
		 * MCU is simply not there".
		 */
		dev_info_ratelimited(&p->client->dev,
				     "attempt %d failed: scl:%d sda:%d conn:%d\n",
				     i,
				     p->scl ? gpiod_get_value_cansleep(p->scl) : -1,
				     p->sda ? gpiod_get_value_cansleep(p->sda) : -1,
				     gpiod_get_value_cansleep(p->connected));
		/*
		 * Samsung's retry loop pulses NRST again on every failed attempt
		 * (stm32_power_reset, reset_count up to 100000) and only then
		 * reads the version back, so a single reset after power-on is not
		 * what this part expects.
		 */
		gpiod_set_value_cansleep(p->nrst, 0);
		msleep(3);
		gpiod_set_value_cansleep(p->nrst, 1);
		msleep(50);
	}
	if (ret) {
		dev_info(&p->client->dev, "no answer from the MCU after %d resets (%d)\n",
			 i, ret);
		pogo_scan_bus(p);
		return ret;
	}
	if (i)
		dev_info(&p->client->dev, "MCU answered after %d extra reset(s)\n", i);
	ret = pogo_read_reg(p, POGO_CMD_GET_MODE, &mode, sizeof(mode));
	if (ret) {
		dev_info(&p->client->dev, "MCU answered, mode read failed (%d)\n", ret);
		return ret;
	}
	p->ready = mode == 1;
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
