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
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/of.h>
#include <linux/regulator/consumer.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>

#define POGO_MAX_PAYLOAD 100
#define POGO_MODEL_DX710 0x02

/* STM32 command ids, from Samsung's stm32_pogo_v3.h. */
#define POGO_CMD_GET_MODE		0x01
#define POGO_CMD_CHECK_VERSION		0x02

struct samsung_pogo {
	struct i2c_client *client;
	struct input_dev *input;
	struct gpio_desc *connected;
	struct gpio_desc *swclk;
	struct gpio_desc *nrst;
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
		/*
		 * Mainline's regulator core can switch this rail off during late
		 * init, before this driver claims it, which leaves the MCU latched
		 * in a brown-out state that an NRST pulse alone does not clear.
		 * Give it a real power cycle, then take it out of reset with SWCLK
		 * already low, as the stock keyboard_start does.
		 */
		if (regulator_is_enabled(p->vdd)) {
			regulator_disable(p->vdd);
			msleep(100);
		}
		ret = regulator_enable(p->vdd);
		if (ret) {
			dev_err(&p->client->dev, "power on failed: %d\n", ret);
		} else {
			p->powered = true;
			gpiod_set_value_cansleep(p->swclk, 0);
			gpiod_set_value_cansleep(p->nrst, 0);
			msleep(10);
			gpiod_set_value_cansleep(p->nrst, 1);
			msleep(50); /* stock keyboard_start power settling */
			p->event_enabled = true;
			enable_irq(p->client->irq);
			dev_info(&p->client->dev,
				 "pogo rail power-cycled, MCU out of reset, reading its version\n");
			pogo_read_mcu(p);
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

	for (i = 0; i < 40; i++) {
		ret = pogo_read_reg(p, POGO_CMD_CHECK_VERSION, version,
				    sizeof(version));
		if (!ret)
			break;
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
