// SPDX-License-Identifier: GPL-2.0-only
/* X710 Stage3B PASSIVE monitor. No pump-ON, PPS, Q4, reset, active protection,
 * reverse/bypass or writable power_supply property exists in this driver.
 * Hardware provenance: Samsung sm5440_charger.c/.h, cross-checked Fedora
 * ab123e7d. See docs/SM5440_REGISTER_AUDIT.md; register writes are limited to
 * mode-OFF and traced converter controls. Unaccepted ADC => unavailable.
 */
#include <linux/delay.h>
#include <linux/debugfs.h>
#include <linux/i2c.h>
#include <linux/jiffies.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/pm.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>
#include <linux/seq_file.h>
#include <linux/string.h>
#include <linux/workqueue.h>

#include "sm5440-hw.h"

struct sm5440_sample {
	u32 vbus_uv;
	u32 vbat_uv;
	u32 ibus_ua;
	int die_decic;
	u32 faults;
	/* BOOTTIME before converter enable: oldest plausible ADC acquisition. */
	u64 acquired_ms;
	/* Preserve read-to-clear INT separately from live STATUS. */
	u8 int_before[4], status[4], adc[11];
	u8 int4_after_disable, int4_wait, mode_before, mode_after;
	u8 cntl2, vbuscntl, vbatcntl, prtncntl;
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
	bool initial_sample_done;
	u8 startup_confirmations;
	unsigned long startup_deadline;
	struct sm5440_sample startup_sample;
	unsigned long startup_stamp;
	int last_sample_error;
	struct dentry *debug_root;
};

/* Copy-only companion access. Lock order: companion_lock -> io_lock.
 * No pointer escapes; unpublish serializes with readers before devres teardown.
 * Poll/PM/debugfs never take companion_lock. No I2C/wait under this lock pair.
 */
static DEFINE_MUTEX(sm5440_companion_lock);
static struct sm5440_direct *sm5440_companion;

static int sm5440_publish(struct sm5440_direct *sm)
{
	int ret = 0;

	mutex_lock(&sm5440_companion_lock);
	if (sm5440_companion)
		ret = -EBUSY;
	else
		sm5440_companion = sm;
	mutex_unlock(&sm5440_companion_lock);
	return ret;
}

static void sm5440_unpublish(void *data)
{
	mutex_lock(&sm5440_companion_lock);
	if (sm5440_companion == data)
		sm5440_companion = NULL;
	mutex_unlock(&sm5440_companion_lock);
}

int sm5440_passive_read_cached(struct sm5440_passive_measurement *out)
{
	struct sm5440_direct *sm;
	u64 now;
	int ret = 0;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	mutex_lock(&sm5440_companion_lock);
	sm = sm5440_companion;
	if (!sm) {
		ret = -ENODEV;
		goto unlock;
	}
	/* Do not hold the lifetime registry while waiting on worker I2C. */
	if (!mutex_trylock(&sm->io_lock)) {
		ret = -EBUSY;
		goto unlock;
	}
	now = ktime_to_ms(ktime_get_boottime());
	if (READ_ONCE(sm->stopped))
		ret = -ESHUTDOWN;
	else if (sm->fault || sm->sample.faults || sm->last_sample_error)
		ret = -EIO;
	else if (!sm->initial_sample_done || !sm->sample.valid ||
		 sm->startup_confirmations)
		ret = -EAGAIN;
	else if ((sm->sample.mode_before | sm->sample.mode_after) & SM5440_MODE_MASK)
		ret = -EBUSY;
	else if (!sm->sample.acquired_ms || sm->sample.acquired_ms > now ||
		 now - sm->sample.acquired_ms > 100)
		ret = -ESTALE;
	else {
		out->observed_ms = sm->sample.acquired_ms;
		out->vbus_uv = sm->sample.vbus_uv;
		out->vbat_uv = sm->sample.vbat_uv;
		out->ibus_ua = sm->sample.ibus_ua;
		out->die_decic = sm->sample.die_decic;
		out->online = sm->sample.online;
	}
	mutex_unlock(&sm->io_lock);
unlock:
	mutex_unlock(&sm5440_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5440_passive_read_cached);

/* Diagnostic copy only. No register access or charging authorization. */
struct sm5440_snapshot {
	struct sm5440_sample sample, startup;
	unsigned long captured, startup_stamp;
	u64 age_ms;
	int last_error;
	u8 pending;
	bool present, stopped, fault, fresh;
};

static void sm5440_snapshot_capture(struct sm5440_direct *sm,
				    struct sm5440_snapshot *snapshot)
{
	mutex_lock(&sm->io_lock);
	snapshot->sample = sm->sample;
	snapshot->startup = sm->startup_sample;
	snapshot->captured = jiffies;
	snapshot->startup_stamp = sm->startup_stamp;
	snapshot->last_error = sm->last_sample_error;
	snapshot->pending = sm->startup_confirmations;
	snapshot->present = sm->initial_sample_done;
	/* PM sets stopped before taking io_lock and draining the worker. */
	snapshot->stopped = READ_ONCE(sm->stopped);
	snapshot->fault = sm->fault;
	mutex_unlock(&sm->io_lock);
	snapshot->fresh = snapshot->present && snapshot->sample.valid &&
		!snapshot->stopped && !snapshot->fault && !snapshot->pending &&
		!snapshot->sample.faults && !time_before(snapshot->captured,
			snapshot->sample.stamp) && !time_after(snapshot->captured,
			snapshot->sample.stamp + msecs_to_jiffies(2500));
	/* Keep long fault-cache ages in 64 bits; zero without present is unknown. */
	snapshot->age_ms = snapshot->present ?
		jiffies64_to_msecs((u64)(snapshot->captured - snapshot->sample.stamp)) : 0;
}

static void sm5440_snapshot_sample_show(struct seq_file *seq, const char *name,
				       const struct sm5440_sample *sample)
{
	seq_printf(seq, "%s_valid=%u\n%s_stamp_jiffies=%lu\n%s_faults=0x%x\n",
		   name, sample->valid, name, sample->stamp, name, sample->faults);
	seq_printf(seq, "%s_int=%*ph\n%s_status=%*ph\n%s_adc=%*ph\n", name,
		   4, sample->int_before, name, 4, sample->status, name, 11, sample->adc);
	seq_printf(seq, "%s_int4_disable=0x%02x\n%s_int4_wait=0x%02x\n",
		   name, sample->int4_after_disable, name, sample->int4_wait);
	seq_printf(seq, "%s_mode_before=0x%02x\n%s_mode_after=0x%02x\n",
		   name, sample->mode_before, name, sample->mode_after);
	seq_printf(seq, "%s_cntl2=0x%02x\n%s_vbuscntl=0x%02x\n"
		   "%s_vbatcntl=0x%02x\n%s_prtncntl=0x%02x\n", name, sample->cntl2,
		   name, sample->vbuscntl, name, sample->vbatcntl, name, sample->prtncntl);
	seq_printf(seq, "%s_vbus_uv=%u\n%s_vbat_uv=%u\n%s_ibus_ua=%u\n%s_die_decic=%d\n",
		   name, sample->vbus_uv, name, sample->vbat_uv,
		   name, sample->ibus_ua, name, sample->die_decic);
}

static int sm5440_snapshot_show(struct seq_file *seq, void *unused)
{
	struct sm5440_snapshot snapshot;

	(void)unused;
	sm5440_snapshot_capture(seq->private, &snapshot);
	/* Format after releasing io_lock. Never refresh or consume INT on read. */
	seq_puts(seq, "format=sm5440-passive-v1\nregisters_are_cached=1\n"
		 "independently_calibrated=0\npump_enable_supported=0\n");
	seq_printf(seq, "capture_jiffies=%lu\nsample_present=%u\nsample_fresh=%u\n"
		   "sample_age_ms=%llu\nstopped=%u\nfault=%u\nstartup_pending=%u\n"
		   "last_sample_error=%d\nstartup_retained=%u\nstartup_capture_jiffies=%lu\n",
		   snapshot.captured, snapshot.present, snapshot.fresh,
		   (unsigned long long)snapshot.age_ms, snapshot.stopped, snapshot.fault,
		   snapshot.pending, snapshot.last_error, !!snapshot.startup.faults,
		   snapshot.startup_stamp);
	sm5440_snapshot_sample_show(seq, "sample", &snapshot.sample);
	sm5440_snapshot_sample_show(seq, "startup", &snapshot.startup);
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(sm5440_snapshot);

static void sm5440_debugfs_remove(void *data)
{
	struct sm5440_direct *sm = data;

	debugfs_remove(sm->debug_root);
	sm->debug_root = NULL;
}

static void sm5440_debugfs_init(struct sm5440_direct *sm)
{
	struct dentry *file;
	char name[64];

	if (snprintf(name, sizeof(name), "sm5440-%s", dev_name(sm->dev)) >= (int)sizeof(name))
		return;
	sm->debug_root = debugfs_create_dir(name, NULL);
	if (IS_ERR_OR_NULL(sm->debug_root)) {
		sm->debug_root = NULL;
		return;
	}
	file = debugfs_create_file("snapshot", 0400, sm->debug_root, sm,
				   &sm5440_snapshot_fops);
	if (IS_ERR_OR_NULL(file)) {
		sm5440_debugfs_remove(sm);
		return;
	}
	/* Added after stop: devres removes/drains files before freeing driver data.
	 * Use normal debugfs proxies, not the unsafe create_file variant.
	 */
	if (devm_add_action_or_reset(sm->dev, sm5440_debugfs_remove, sm))
		dev_dbg(sm->dev, "passive snapshot unavailable; monitor unchanged\n");
}

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
	unsigned int mode, ready, value;
	u8 events[4], status[4], adc[11];
	int ret, i;

	mutex_lock(&sm->io_lock);
	ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY; /* never adopt a running/reverse pump */
	if (!ret)
		sample->mode_before = mode;
	/* Consume old conversion/fault latches before starting a new conversion.
	 * Vendor IRQ reads INT1..4; retain faults instead of discarding them.
	 */
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5440_INT1, events, sizeof(events));
	if (!ret)
		memcpy(sample->int_before, events, sizeof(events));
	if (!ret)
		ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					 SM5440_ADC_ENABLE | SM5440_ADC_RATE, 0);
	/* A previous conversion can finish between the first latch read and
	 * disabling ADC. Consume that completion AFTER disable as well.
	 */
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_INT4, &ready);
		if (!ret) {
			sample->int4_after_disable = ready;
			events[3] |= ready;
		}
	}
	if (!ret)
		ret = regmap_write(sm->regmap, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
	if (!ret) {
		/* Vendor converter sequence unchanged; never stamp a cache lookup. */
		sample->acquired_ms = ktime_to_ms(ktime_get_boottime());
		ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					 SM5440_ADC_ENABLE | SM5440_ADC_AVG32,
					 SM5440_ADC_ENABLE | SM5440_ADC_AVG32);
	}
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
		sample->int4_wait |= ready;
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
	/* Samsung get_vbatreg()/get_ibuslim()/init_reg_param(): these are
	 * ordinary control registers, not read-to-clear interrupt registers.
	 * Read-only provenance; never change protections to suppress a fault.
	 */
	if (!ret) {
		sample->mode_after = mode;
		ret = regmap_read(sm->regmap, SM5440_CNTL2, &value);
		if (!ret)
			sample->cntl2 = value;
	}
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_VBUSCNTL, &value);
		if (!ret)
			sample->vbuscntl = value;
	}
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_VBATCNTL, &value);
		if (!ret)
			sample->vbatcntl = value;
	}
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_PRTNCNTL, &value);
		if (!ret)
			sample->prtncntl = value;
	}
	if (!ret) {
		memcpy(sample->status, status, sizeof(status));
		memcpy(sample->adc, adc, sizeof(adc));
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

/* A pre-conversion REVBLK latch is not proof of current pump activity.
 * Samsung IRQ uses direct-state/mode context (see passive startup audit).
 * Keep the event, require new conversions, and never exempt live/repeated
 * faults or VBAT_OVP. This classifier is limited to ordinary PC USB.
 */
static bool sm5440_passive_pc_sample(const struct sm5440_sample *sample)
{
	return !(sample->mode_before & SM5440_MODE_MASK) &&
		!(sample->mode_after & SM5440_MODE_MASK) &&
		(sample->int4_wait & SM5440_ADC_READY) && sample->online &&
		sample->vbus_uv >= 4500000 && sample->vbus_uv <= 5500000 &&
		sample->vbat_uv >= 3500000 && sample->vbat_uv < 4300000 &&
		!sample->ibus_ua && sample->die_decic >= 225 &&
		sample->die_decic < 420;
}

static bool sm5440_startup_revblk(const struct sm5440_sample *sample)
{
	return sample->faults == SM5440_FAULT_REVBLK &&
		sm5440_decode_faults(sample->int_before, false, 0) == SM5440_FAULT_REVBLK &&
		!sm5440_decode_faults(sample->status, false, 0) &&
		sm5440_passive_pc_sample(sample);
}

static bool sm5440_startup_matches(const struct sm5440_sample *sample,
				   const struct sm5440_sample *initial)
{
	return !sample->faults && sm5440_passive_pc_sample(sample) &&
		sample->cntl2 == initial->cntl2 &&
		sample->vbuscntl == initial->vbuscntl &&
		sample->vbatcntl == initial->vbatcntl &&
		sample->prtncntl == initial->prtncntl;
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
	sm->last_sample_error = ret;
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
		/* A suspect startup latch is UNKNOWN until two new safe samples.
		 * Failure is permanent; the exemption is consumed once per probe.
		 */
		if (!sm->initial_sample_done && sm5440_startup_revblk(&sample)) {
			sm->startup_sample = sample;
			sm->startup_stamp = jiffies;
			sm->startup_confirmations = 2;
			sm->startup_deadline = jiffies + msecs_to_jiffies(5000);
			dev_warn(sm->dev, "passive startup REVBLK awaiting two fresh confirmations\n");
		} else if (sm->startup_confirmations) {
			if (time_after(jiffies, sm->startup_deadline) ||
			    !sm5440_startup_matches(&sample, &sm->startup_sample)) {
				sm->fault = true;
				dev_err(sm->dev, "passive startup confirmation failed\n");
			} else {
				sm->startup_confirmations--;
				if (!sm->startup_confirmations)
					dev_info(sm->dev, "passive startup REVBLK confirmed inactive; event retained\n");
			}
		}
		sm->initial_sample_done = true;
		sample.valid = true;
		sample.stamp = jiffies;
		sm->sample = sample;
		if (sample.faults) {
			/* Reads consume INT. Only the initial qualified REVBLK may
			 * await confirmation; all other faults latch until unbind.
			 * startup_sample retains the original event independently.
			 */
			if (!sm->startup_confirmations ||
			    !sm5440_startup_revblk(&sample))
				sm->fault = true;
			dev_warn_ratelimited(sm->dev,
				"passive fault bitmap=%#x INT=%*ph STATUS=%*ph INT4-disable=%02x INT4-wait=%02x mode=%02x/%02x CNTL2=%02x VBUSCNTL=%02x VBATCNTL=%02x PRTNCNTL=%02x ADC=%*ph VBUS=%uuV VBAT=%uuV IBUS=%uuA die=%d deciC\n",
				sample.faults, 4, sample.int_before, 4, sample.status,
				sample.int4_after_disable, sample.int4_wait,
				sample.mode_before, sample.mode_after, sample.cntl2,
				sample.vbuscntl, sample.vbatcntl, sample.prtncntl,
				11, sample.adc, sample.vbus_uv, sample.vbat_uv,
				sample.ibus_ua, sample.die_decic);
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
	bool fault, startup_pending;

	mutex_lock(&sm->io_lock);
	sample = sm->sample;
	fault = sm->fault;
	startup_pending = sm->startup_confirmations != 0;
	mutex_unlock(&sm->io_lock);
	if (prop == POWER_SUPPLY_PROP_STATUS) {
		val->intval = POWER_SUPPLY_STATUS_NOT_CHARGING;
		return 0;
	}
	if (prop == POWER_SUPPLY_PROP_HEALTH) {
		if (fault || (!startup_pending && sample.faults))
			val->intval = POWER_SUPPLY_HEALTH_UNSPEC_FAILURE;
		else if (!startup_pending && sample.valid)
			val->intval = POWER_SUPPLY_HEALTH_GOOD;
		else
			val->intval = POWER_SUPPLY_HEALTH_UNKNOWN;
		return 0;
	}
	if (startup_pending || !sample.valid ||
	    time_after(jiffies, sample.stamp + msecs_to_jiffies(2500)))
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
	/* Never carry unconfirmed startup evidence across suspend/unbind. */
	if (sm->startup_confirmations)
		sm->fault = true;
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
	/* Register stop after supplies so work drains before their memory is freed. */
	ret = devm_add_action_or_reset(sm->dev, sm5440_stop, sm);
	if (ret)
		return ret;
	sm5440_debugfs_init(sm);
	/* Added last: unpublish/drain copy readers before debugfs/stop/free. */
	ret = devm_add_action_or_reset(sm->dev, sm5440_unpublish, sm);
	if (ret)
		return ret;
	ret = sm5440_publish(sm);
	if (ret)
		return dev_err_probe(sm->dev, ret, "SM5440 companion already bound\n");
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
