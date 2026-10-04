// SPDX-License-Identifier: GPL-2.0-only
/* Samsung X710 sm5440_set_adc_mode(CONTINUOUS): disable,50ms,RATE1,enable.
 * Samsung sm5440_init_reg_param(): AVG32/0xdf channels. Fedora ab123e7d
 * independently uses AVG32|CONTINUOUS|ENABLE. Keep every other control bit.
 * This is a bounded pump-OFF timing experiment, not charging admission.
 */
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/regmap.h>

#include "sm5440-hw.h"
#include "sm5440-timing.h"

#define SM5440_TIMING_FIELDS (SM5440_ADC_ENABLE | SM5440_ADC_RATE | SM5440_ADC_AVG32)

static u64 sm5440_timing_now(void)
{
	return ktime_to_ms(ktime_get_boottime());
}

static int sm5440_timing_clock(struct sm5440_timing *t, u64 now)
{
	if (!now || now < t->last_ms || now < t->started_ms)
		return -ESTALE;
	t->last_ms = now;
	return now - t->started_ms > SM5440_TIMING_WINDOW_MS ? -ETIMEDOUT : 0;
}

static int sm5440_timing_off(struct regmap *map, u8 *mode)
{
	unsigned int value;
	int ret = regmap_read(map, SM5440_CNTL5, &value);

	if (ret)
		return ret;
	*mode = value;
	return value & SM5440_MODE_MASK ? -EBUSY : 0;
}

static int sm5440_timing_controls(struct regmap *map, struct sm5440_timing *t,
				 struct sm5440_timing_sample *sample, bool enabled)
{
	unsigned int control, channels;
	int ret = regmap_read(map, SM5440_ADCCNTL1, &control);

	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL2, &channels);
	if (ret)
		return ret;
	sample->control = control;
	sample->channels = channels;
	if (control != ((t->control_before & ~SM5440_TIMING_FIELDS) |
			SM5440_ADC_AVG32 | SM5440_ADC_RATE |
			(enabled ? SM5440_ADC_ENABLE : 0)) ||
	    channels != SM5440_ADC_CHANNELS)
		return -EIO;
	return 0;
}

static int sm5440_timing_status(struct regmap *map,
			      struct sm5440_timing_sample *sample, bool after)
{
	u8 *status = after ? sample->status_after : sample->status;
	int ret = sm5440_timing_off(map, &sample->mode);

	if (!ret)
		ret = regmap_bulk_read(map, SM5440_STATUS1, status, 4);
	if (ret)
		return ret;
	sample->faults |= sm5440_decode_faults(sample->interrupt, false, 0) |
			  sm5440_decode_faults(status, false, 0);
	if (sample->faults)
		return -EIO;
	/* Attached fixed source only; OFF UVLO is not a healthy attached source. */
	return (status[2] & BIT(5)) && !(status[2] & BIT(6)) ?
		0 : -ENOLINK;
}

int sm5440_timing_begin(struct regmap *map, struct sm5440_timing *t)
{
	struct sm5440_timing_sample initial = {};
	unsigned int id, control, channels;
	int ret;

	if (t->attempted)
		return -EALREADY;
	t->attempted = true;
	t->started_ms = sm5440_timing_now();
	t->last_ms = t->started_ms;
	if (!t->started_ms)
		return -ESTALE;
	ret = regmap_read(map, SM5440_DEVICEID, &id);
	if (!ret && (id & 0xf) != 1)
		ret = -ENODEV;
	if (!ret)
		ret = sm5440_timing_off(map, &initial.mode);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL1, &control);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL2, &channels);
	if (ret)
		return ret;
	if (control & SM5440_ADC_ENABLE)
		return -EBUSY;
	t->control_before = control;
	t->channels_before = channels;
	t->saved = true;
	/* Mark before a write which may reach hardware despite an I2C error. */
	t->changed = true;
	ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL1, &control);
	if (!ret && control != t->control_before)
		ret = -EIO;
	if (!ret) {
		t->disabled_ms = sm5440_timing_now();
		ret = sm5440_timing_clock(t, t->disabled_ms);
	}
	return ret;
}

int sm5440_timing_step(struct regmap *map, struct sm5440_timing *t)
{
	struct sm5440_timing_sample *sample;
	u64 now = sm5440_timing_now();
	int ret;

	if (!t->attempted || !t->saved || !t->disabled_ms || t->finished)
		return -EINVAL;
	if (t->count == SM5440_TIMING_SAMPLES)
		return 1;
	ret = sm5440_timing_clock(t, now);
	if (ret)
		return ret;
	if (++t->polls > SM5440_TIMING_POLLS)
		return -ETIMEDOUT;
	sample = &t->sample[t->count];
	if (!t->enabled) {
		unsigned int control;

		if (now - t->disabled_ms < SM5440_TIMING_REARM_MS)
			return 0;
		ret = sm5440_timing_off(map, &sample->mode);
		if (!ret)
			ret = regmap_read(map, SM5440_ADCCNTL1, &control);
		if (!ret && control != t->control_before)
			ret = -EIO;
		if (!ret)
			ret = regmap_bulk_read(map, SM5440_INT1, t->initial_interrupt, 4);
		if (!ret)
			ret = regmap_bulk_read(map, SM5440_STATUS1, t->initial_status, 4);
		if (ret)
			return ret;
		/* Old READY is consumed before enable and cannot count as a sample. */
		if (sm5440_decode_faults(t->initial_interrupt, false, 0) ||
		    sm5440_decode_faults(t->initial_status, false, 0))
			return -EIO;
		if (!(t->initial_status[2] & BIT(5)) ||
		    (t->initial_status[2] & BIT(6)))
			return -ENOLINK;
		ret = regmap_write(map, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
		if (!ret)
			ret = regmap_update_bits(map, SM5440_ADCCNTL1,
				SM5440_TIMING_FIELDS, SM5440_ADC_AVG32 | SM5440_ADC_RATE);
		if (!ret)
			ret = sm5440_timing_controls(map, t, sample, false);
		if (ret)
			return ret;
		t->enabled_ms = sm5440_timing_now();
		t->cleared_ms = t->enabled_ms;
		t->ready_deadline_ms = t->enabled_ms;
		ret = sm5440_timing_clock(t, t->enabled_ms);
		if (!ret)
			ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_ADC_ENABLE,
						 SM5440_ADC_ENABLE);
		if (!ret)
			ret = sm5440_timing_controls(map, t, sample, true);
		if (ret)
			return ret;
		t->enabled = true;
		return 0;
	}
	if (now < t->ready_deadline_ms ||
	    now - t->ready_deadline_ms > SM5440_TIMING_READY_MS)
		return -ETIMEDOUT;
	sample->cleared_ms = t->cleared_ms;
	sample->ready_begin_ms = now;
	ret = regmap_bulk_read(map, SM5440_INT1, sample->interrupt, 4);
	sample->ready_end_ms = sm5440_timing_now();
	/* Retain the actual previous-clear bracket on every pending read. */
	if (!ret)
		ret = sm5440_timing_clock(t, sample->ready_end_ms);
	if (!ret)
		ret = sm5440_timing_status(map, sample, false);
	if (!ret)
		ret = sm5440_timing_controls(map, t, sample, true);
	if (ret)
		return ret;
	/* Oldest bound is the read call's start, not a fabricated chip instant. */
	t->cleared_ms = sample->ready_begin_ms;
	if (!(sample->interrupt[3] & SM5440_ADC_READY))
		return 0;
	sample->adc_begin_ms = sm5440_timing_now();
	ret = regmap_bulk_read(map, SM5440_ADC_VBUS, sample->adc, 11);
	if (!ret)
		ret = sm5440_timing_status(map, sample, true);
	if (!ret)
		ret = sm5440_timing_controls(map, t, sample, true);
	sample->adc_end_ms = sm5440_timing_now();
	if (!ret)
		ret = sm5440_timing_clock(t, sample->adc_end_ms);
	if (!ret && sample->ready_end_ms - t->ready_deadline_ms > SM5440_TIMING_READY_MS)
		ret = -ETIMEDOUT;
	if (!ret && (sm5440_vbus_uv(sample->adc[0], sample->adc[1]) < 4500000 ||
		     sm5440_vbus_uv(sample->adc[0], sample->adc[1]) > 9500000 ||
		     sm5440_vbat_uv(sample->adc[9], sample->adc[10]) < 3500000 ||
		     sm5440_vbat_uv(sample->adc[9], sample->adc[10]) >= 4440000 ||
		     sm5440_ibus_ua(sample->adc[4], sample->adc[5]) ||
		     sm5440_die_decic(sample->adc[8]) >= 420))
		ret = -ERANGE;
	if (ret)
		return ret;
	/* Do not call these conversion instants/coherent channel snapshots. READY
	 * observations and raw read brackets are evidence for offline analysis.
	 */
	t->ready_deadline_ms = sample->ready_end_ms;
	t->count++;
	return t->count == SM5440_TIMING_SAMPLES ? 1 : 0;
}

int sm5440_timing_finish(struct regmap *map, struct sm5440_timing *t, int error)
{
	unsigned int control, channels;
	u8 mode;
	int ret = 0;

	if (!t->attempted)
		return error ? error : -EINVAL;
	if (t->finished)
		return -EALREADY;
	t->finished = true;
	t->error = error;
	if (t->changed && t->saved) {
		/* One cleanup attempt. Disable even after uncertain enable; never
		 * restore an enabled converter or write any pump/protection register.
		 */
		ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
		if (!ret)
			ret = regmap_read(map, SM5440_ADCCNTL1, &control);
		if (!ret && (control & SM5440_ADC_ENABLE))
			ret = -EIO;
		if (!ret)
			ret = sm5440_timing_off(map, &mode);
		if (!ret)
			ret = regmap_write(map, SM5440_ADCCNTL2, t->channels_before);
		if (!ret)
			ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_TIMING_FIELDS,
						 t->control_before & ~SM5440_ADC_ENABLE);
		if (!ret)
			ret = regmap_read(map, SM5440_ADCCNTL1, &control);
		if (!ret)
			ret = regmap_read(map, SM5440_ADCCNTL2, &channels);
		if (!ret) {
			t->control_after = control;
			t->channels_after = channels;
			if (control != t->control_before || channels != t->channels_before)
				ret = -EIO;
		}
		t->restored = !ret;
	}
	t->completed_ms = sm5440_timing_now();
	/* Keep hardware cleanup separate even when the observation deadline fails. */
	if (!error)
		t->error = sm5440_timing_clock(t, t->completed_ms);
	t->cleanup_error = ret;
	return t->error ? t->error : ret;
}
