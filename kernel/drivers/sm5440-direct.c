// SPDX-License-Identifier: GPL-2.0-only
/* X710 Stage3B PASSIVE monitor. No pump-ON, PPS, Q4, reset, active protection,
 * reverse/bypass or writable power_supply property exists in this driver.
 * Hardware provenance: Samsung sm5440_charger.c/.h, cross-checked Fedora
 * ab123e7d. See docs/SM5440_REGISTER_AUDIT.md; register writes are limited to
 * mode-OFF and traced converter controls. Unaccepted ADC => unavailable.
 */
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/jiffies.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/pm.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>
#include <linux/workqueue.h>

#include "sm5440-hw.h"

struct sm5440_sample {
	u32 vbus_uv;
	u32 vbat_uv;
	u32 ibus_ua;
	int die_decic;
	u32 faults;
	bool online;
	bool valid;
	unsigned long stamp;
};

struct sm5440_direct {
	struct device *dev;
	struct regmap *regmap;
	struct mutex io_lock;
	struct delayed_work work;
	struct power_supply *psy;
	struct sm5440_sample sample;
	bool stopped;
	bool fault;
};

static const struct regmap_config sm5440_regmap = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = SM5440_DEVICEID,
	.cache_type = REGCACHE_NONE,
};

/* Caller holds io_lock. Vendor set_op_mode(): CNTL5[3:2], OFF=0. */
static int sm5440_off(struct sm5440_direct *sm)
{
	unsigned int mode;
	int ret;

	lockdep_assert_held(&sm->io_lock);
	ret = regmap_update_bits(sm->regmap, SM5440_CNTL5,
				 SM5440_MODE_MASK, SM5440_MODE_OFF);
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EIO;
	return ret;
}

static int sm5440_sample_once(struct sm5440_direct *sm,
			      struct sm5440_sample *sample)
{
	unsigned int mode, ready;
	u8 events[4], status[4], adc[11];
	int ret, i;

	mutex_lock(&sm->io_lock);
	ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY; /* never adopt a running/reverse pump */
	/* Consume old conversion/fault latches before starting a new conversion.
	 * Vendor IRQ reads INT1..4; retain faults instead of discarding them.
	 */
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5440_INT1, events, sizeof(events));
	if (!ret)
		ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					 SM5440_ADC_ENABLE | SM5440_ADC_RATE, 0);
	/* A previous conversion can finish between the first latch read and
	 * disabling ADC. Consume that completion AFTER disable as well.
	 */
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_INT4, &ready);
		if (!ret)
			events[3] |= ready;
	}
	if (!ret)
		ret = regmap_write(sm->regmap, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
	if (!ret)
		ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					 SM5440_ADC_ENABLE | SM5440_ADC_AVG32,
					 SM5440_ADC_ENABLE | SM5440_ADC_AVG32);
	mutex_unlock(&sm->io_lock);
	if (ret)
		return ret;
	/* Single worker; PM/remove synchronously drain it. No mutex is held
	 * across a converter wait. Unknown completion is not a measurement.
	 */
	for (i = 0; i < 12; i++) {
		if (READ_ONCE(sm->stopped))
			return -ESHUTDOWN;
		msleep(25);
		mutex_lock(&sm->io_lock);
		ret = regmap_read(sm->regmap, SM5440_INT4, &ready);
		mutex_unlock(&sm->io_lock);
		if (ret)
			return ret;
		/* Retain watchdog/timer events consumed while waiting. */
		events[3] |= ready;
		if (ready & SM5440_ADC_READY)
			break;
	}
	if (i == 12)
		return -ETIMEDOUT;
	mutex_lock(&sm->io_lock);
	ret = regmap_bulk_read(sm->regmap, SM5440_ADC_VBUS, adc, sizeof(adc));
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5440_STATUS1, status, sizeof(status));
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY;
	if (!ret) {
		for (i = 0; i < 4; i++)
			events[i] |= status[i];
		sample->vbus_uv = sm5440_vbus_uv(adc[0], adc[1]);
		sample->ibus_ua = sm5440_ibus_ua(adc[4], adc[5]);
		sample->die_decic = sm5440_die_decic(adc[8]);
		sample->vbat_uv = sm5440_vbat_uv(adc[9], adc[10]);
		sample->online = !!(status[2] & BIT(5));
		sample->faults = sm5440_decode_faults(events, false, 0);
		/* Implausible pack samples remain unavailable, even if ADC ready.
		 * Passive monitor never authorizes charge based on these values.
		 */
		if (sample->vbat_uv < 2500000 || sample->vbat_uv > 4600000)
			ret = -ERANGE;
	}
	mutex_unlock(&sm->io_lock);
	return ret;
}

static void sm5440_poll(struct work_struct *work)
{
	struct sm5440_direct *sm = container_of(to_delayed_work(work),
					       struct sm5440_direct, work);
	struct sm5440_sample sample = {};
	int ret;

	if (READ_ONCE(sm->stopped) || READ_ONCE(sm->fault))
		return;
	ret = sm5440_sample_once(sm, &sample);
	mutex_lock(&sm->io_lock);
	if (ret) {
		sm->sample.valid = false;
		if (ret != -ESHUTDOWN) {
			sm->fault = true;
			/* Best effort OFF is not proof when I2C has failed. */
			dev_err(sm->dev, "passive ADC fault %d; OFF verification=%d\n",
				ret, sm5440_off(sm));
			regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					   SM5440_ADC_ENABLE, 0);
		}
	} else {
		sample.valid = true;
		sample.stamp = jiffies;
		sm->sample = sample;
		if (sample.faults) {
			/* INT latches are consumed by reads. Preserve the first fault
			 * until unbind/reboot instead of reporting Good next second.
			 */
			sm->fault = true;
			dev_warn_ratelimited(sm->dev, "passive fault bitmap=%#x\n", sample.faults);
		}
		dev_dbg(sm->dev, "passive VBUS=%uuV VBAT=%uuV IBUS=%uuA die=%d deciC faults=%#x\n",
			sample.vbus_uv, sample.vbat_uv, sample.ibus_ua,
			sample.die_decic, sample.faults);
	}
	mutex_unlock(&sm->io_lock);
	power_supply_changed(sm->psy);
	if (!READ_ONCE(sm->stopped) && !READ_ONCE(sm->fault))
		schedule_delayed_work(&sm->work, msecs_to_jiffies(1000));
}

static int sm5440_get_property(struct power_supply *psy,
			       enum power_supply_property prop,
			       union power_supply_propval *val)
{
	struct sm5440_direct *sm = power_supply_get_drvdata(psy);
	struct sm5440_sample sample;
	bool fault;

	mutex_lock(&sm->io_lock);
	sample = sm->sample;
	fault = sm->fault;
	mutex_unlock(&sm->io_lock);
	if (prop == POWER_SUPPLY_PROP_STATUS) {
		val->intval = POWER_SUPPLY_STATUS_NOT_CHARGING;
		return 0;
	}
	if (prop == POWER_SUPPLY_PROP_HEALTH) {
		val->intval = fault || sample.faults ? POWER_SUPPLY_HEALTH_UNSPEC_FAILURE :
			sample.valid ? POWER_SUPPLY_HEALTH_GOOD : POWER_SUPPLY_HEALTH_UNKNOWN;
		return 0;
	}
	if (!sample.valid || time_after(jiffies, sample.stamp + msecs_to_jiffies(2500)))
		return -ENODATA;
	switch (prop) {
	case POWER_SUPPLY_PROP_ONLINE:
		val->intval = sample.online;
		break;
	case POWER_SUPPLY_PROP_VOLTAGE_NOW:
		val->intval = sample.vbus_uv;
		break;
	case POWER_SUPPLY_PROP_CURRENT_NOW:
		val->intval = sample.ibus_ua;
		break;
	case POWER_SUPPLY_PROP_TEMP:
		val->intval = sample.die_decic;
		break;
	default:
		return -EINVAL;
	}
	return 0;
}

static enum power_supply_property sm5440_props[] = {
	POWER_SUPPLY_PROP_STATUS, POWER_SUPPLY_PROP_HEALTH, POWER_SUPPLY_PROP_ONLINE,
	POWER_SUPPLY_PROP_VOLTAGE_NOW, POWER_SUPPLY_PROP_CURRENT_NOW,
	POWER_SUPPLY_PROP_TEMP,
};

static const struct power_supply_desc sm5440_desc = {
	.name = "sm5440-passive",
	.type = POWER_SUPPLY_TYPE_MAINS,
	.properties = sm5440_props,
	.num_properties = ARRAY_SIZE(sm5440_props),
	.get_property = sm5440_get_property,
};

static int sm5440_quiesce(struct sm5440_direct *sm)
{
	int ret, adc_ret;

	WRITE_ONCE(sm->stopped, true);
	cancel_delayed_work_sync(&sm->work);
	mutex_lock(&sm->io_lock);
	sm->sample.valid = false;
	ret = sm5440_off(sm);
	adc_ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	mutex_unlock(&sm->io_lock);
	if (ret || adc_ret)
		dev_err(sm->dev, "passive teardown cannot verify OFF/ADC-off: %d/%d\n", ret, adc_ret);
	return ret ? ret : adc_ret;
}

static void sm5440_stop(void *data)
{
	sm5440_quiesce(data);
}

static int sm5440_suspend(struct device *dev)
{
	struct sm5440_direct *sm = dev_get_drvdata(dev);

	return sm5440_quiesce(sm);
}

static int sm5440_resume(struct device *dev)
{
	struct sm5440_direct *sm = dev_get_drvdata(dev);
	int ret;

	mutex_lock(&sm->io_lock);
	ret = sm5440_off(sm);
	mutex_unlock(&sm->io_lock);
	if (ret || READ_ONCE(sm->fault))
		return ret ? ret : -EIO;
	WRITE_ONCE(sm->stopped, false);
	schedule_delayed_work(&sm->work, 0);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(sm5440_pm, sm5440_suspend, sm5440_resume);

static int sm5440_probe(struct i2c_client *client)
{
	struct sm5440_direct *sm;
	struct power_supply_config config = {};
	unsigned int id, mode;
	int ret;

	sm = devm_kzalloc(&client->dev, sizeof(*sm), GFP_KERNEL);
	if (!sm)
		return -ENOMEM;
	sm->dev = &client->dev;
	sm->regmap = devm_regmap_init_i2c(client, &sm5440_regmap);
	if (IS_ERR(sm->regmap))
		return PTR_ERR(sm->regmap);
	mutex_init(&sm->io_lock);
	INIT_DELAYED_WORK(&sm->work, sm5440_poll);
	i2c_set_clientdata(client, sm);
	ret = regmap_read(sm->regmap, SM5440_DEVICEID, &id);
	if (ret || (id & 0xf) != 1)
		return dev_err_probe(sm->dev, ret ? ret : -ENODEV, "invalid SM5440 identity\n");
	ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (ret || (mode & SM5440_MODE_MASK))
		return dev_err_probe(sm->dev, ret ? ret : -EBUSY, "passive probe requires pump OFF\n");
	config.drv_data = sm;
	sm->psy = devm_power_supply_register(sm->dev, &sm5440_desc, &config);
	if (IS_ERR(sm->psy))
		return PTR_ERR(sm->psy);
	/* Register last so worker is drained before power_supply/regmap free. */
	ret = devm_add_action_or_reset(sm->dev, sm5440_stop, sm);
	if (ret)
		return ret;
	schedule_delayed_work(&sm->work, 0);
	dev_info(sm->dev, "passive SM5440 revision %u; pump activation unavailable\n", id >> 4);
	return 0;
}

static void sm5440_shutdown(struct i2c_client *client)
{
	sm5440_stop(i2c_get_clientdata(client));
}

static const struct of_device_id sm5440_match[] = {
	{ .compatible = "siliconmitus,sm5440" },
	{ }
};
MODULE_DEVICE_TABLE(of, sm5440_match);

static struct i2c_driver sm5440_driver = {
	.driver = {
		.name = "sm5440-passive",
		.of_match_table = sm5440_match,
		.pm = pm_sleep_ptr(&sm5440_pm),
	},
	.probe = sm5440_probe,
	.shutdown = sm5440_shutdown,
};
module_i2c_driver(sm5440_driver);
MODULE_DESCRIPTION("SM-X710 passive SM5440 ID/ADC/fault monitor; pump OFF only");
MODULE_LICENSE("GPL");
