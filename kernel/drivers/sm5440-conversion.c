// SPDX-License-Identifier: GPL-2.0-only
/* X710 vendor single-shot sequence and arithmetic, bounded native provenance.
 * Linked by the explicit native session. No pump/PD operation, automatic
 * acquisition or protection qualification.
 */
#include <linux/compiler.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/regmap.h>

#include "sm5440-conversion.h"
#include "sm5440-hw.h"

#define SM5440_CONVERSION_REARM_MS 20U /* vendor set_adc_mode(ONESHOT) */
#define SM5440_CONVERSION_POLLS 64U /* bound duplicate polls even within one ms */
#define SM5440_CONVERSION_FIELDS (SM5440_ADC_ENABLE | SM5440_ADC_RATE | SM5440_ADC_AVG32)

static int sm5440_conversion_clock(struct sm5440_conversion *a, u64 *now)
{
	*now = ktime_to_ms(ktime_get_boottime());
	if (!*now || *now < a->last_clock_ms)
		return -ETIME;
	a->last_clock_ms = *now;
	if (!a->generation || !a->epoch || READ_ONCE(*a->generation) != a->epoch)
		return -ECANCELED;
	if (a->requested_ms && *now - a->requested_ms > X710_MONITOR_DEADLINE_MS)
		return -ETIMEDOUT;
	return 0;
}

static int sm5440_conversion_status(struct regmap *map, struct sm5440_conversion *a)
{
	u8 events[4];
	unsigned int mode;
	int i, ret;

	ret = regmap_bulk_read(map, SM5440_INT1, events, sizeof(events));
	if (ret)
		return ret;
	for (i = 0; i < 4; i++)
		a->events[i] |= events[i];
	if (a->state == SM5440_CONVERSION_WAIT && (events[3] & SM5440_ADC_READY))
		a->ready = true;
	ret = regmap_bulk_read(map, SM5440_STATUS1, a->status, sizeof(a->status));
	if (!ret)
		ret = regmap_read(map, SM5440_CNTL5, &mode);
	if (ret)
		return ret;
	/* INT latches contain transitions, not the present VBUSPOK level. Apply
	 * live lost-mode/POK checks only to STATUS, retaining active UVLO events.
	 */
	a->faults |= sm5440_decode_faults(a->events, false, 0);
	if (a->running && (a->events[2] & BIT(6)))
		a->faults |= SM5440_FAULT_VBUS_UVLO;
	a->faults |= sm5440_decode_faults(a->status, a->running, (mode & SM5440_MODE_MASK) >> 2);
	if (a->faults)
		return -EIO;
	if ((mode & SM5440_MODE_MASK) != (a->running ? BIT(2) : 0))
		return -EBUSY;
	if (!(a->status[2] & BIT(5)) || (a->status[2] & BIT(6)))
		return -ENOLINK;
	return 0;
}

static int sm5440_conversion_readback(struct regmap *map, u8 reg, u8 expected)
{
	unsigned int value;
	int ret = regmap_read(map, reg, &value);

	if (!ret && value != expected)
		ret = -EIO;
	return ret;
}

static int sm5440_conversion_cleanup(struct regmap *map, struct sm5440_conversion *a)
{
	unsigned int control;
	int ret, err;

	if (a->cleanup_attempted)
		return a->cleanup_error;
	a->cleanup_attempted = true;
	if (!a->owned)
		return 0;
	/* Do not re-enable any converter, including after uncertain enable writes. */
	ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	if (ret && a->defer_cleanup)
		goto out; /* managed active owner must get OFF priority immediately */
	err = regmap_read(map, SM5440_ADCCNTL1, &control);
	if (!err && (control & SM5440_ADC_ENABLE))
		err = -EBUSY;
	if (!ret)
		ret = err;
	if (ret && a->defer_cleanup)
		goto out;
	if (err)
		goto out;
	a->adc_off_verified = true;
	err = regmap_write(map, SM5440_ADCCNTL2, a->before_channels);
	if (err && a->defer_cleanup) {
		ret = err;
		goto out;
	}
	if (!err)
		err = sm5440_conversion_readback(map, SM5440_ADCCNTL2, a->before_channels);
	if (!ret)
		ret = err;
	if (ret && a->defer_cleanup)
		goto out;
	err = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_CONVERSION_FIELDS,
				 a->before_control);
	if (err && a->defer_cleanup) {
		ret = err;
		goto out;
	}
	if (!err)
		err = sm5440_conversion_readback(map, SM5440_ADCCNTL1,
				(control & ~SM5440_CONVERSION_FIELDS) |
				(a->before_control & SM5440_CONVERSION_FIELDS));
	if (!err && ((control ^ a->before_control) & ~SM5440_CONVERSION_FIELDS))
		err = -EIO;
	if (!ret)
		ret = err;
	if (!ret)
		a->owned = false;
out:
	a->cleanup_error = ret;
	return ret;
}

static int sm5440_conversion_fail(struct regmap *map, struct sm5440_conversion *a, int ret)
{
	if (!a->operation_error)
		a->operation_error = ret;
	a->sample.valid = false;
	a->state = SM5440_CONVERSION_FAULT;
	a->enabled = false;
	if (!a->defer_cleanup)
		sm5440_conversion_cleanup(map, a);
	return a->operation_error;
}

int sm5440_conversion_begin(struct regmap *map, struct sm5440_conversion *a)
{
	unsigned int id, control, channels;
	u64 now;
	int ret;

	if (!map || !a)
		return -EINVAL;
	if (a->state != SM5440_CONVERSION_IDLE || a->owned || a->cleanup_attempted ||
	    a->requested_ms || a->operation_error || a->cleanup_error)
		return -EALREADY;
	if (!a->enabled)
		return -EPERM;
	ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	a->requested_ms = now;
	ret = regmap_read(map, SM5440_DEVICEID, &id);
	if (!ret && (id & 0xf) != 1)
		ret = -ENODEV;
	if (!ret)
		ret = sm5440_conversion_status(map, a);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL1, &control);
	if (!ret && (control & SM5440_ADC_ENABLE))
		ret = -EBUSY; /* never adopt another converter's in-flight completion */
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL2, &channels);
	if (!ret)
		ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	a->before_control = control;
	a->before_channels = channels;
	a->owned = true;
	ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	if (!ret)
		ret = sm5440_conversion_readback(map, SM5440_ADCCNTL1, control);
	if (!ret)
		ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	a->disabled_ms = now;
	a->state = SM5440_CONVERSION_REARM;
	return -EINPROGRESS;
}

int sm5440_conversion_advance(struct regmap *map, struct sm5440_conversion *a)
{
	unsigned int value;
	u64 now;
	int ret;

	if (!map || !a)
		return -EINVAL;
	if (a->state != SM5440_CONVERSION_REARM && a->state != SM5440_CONVERSION_WAIT)
		return -EALREADY;
	ret = sm5440_conversion_clock(a, &now);
	if (!ret && ++a->polls > SM5440_CONVERSION_POLLS)
		ret = -ETIMEDOUT;
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	if (a->state == SM5440_CONVERSION_REARM && now - a->disabled_ms < SM5440_CONVERSION_REARM_MS)
		return -EINPROGRESS;
	ret = sm5440_conversion_status(map, a);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	if (a->state == SM5440_CONVERSION_REARM) {
		/* Old ADC_READY remains in raw events but never sets this request's
		 * ready flag. Only a WAIT-state latch read can complete the conversion.
		 */
		ret = sm5440_conversion_readback(map, SM5440_ADCCNTL1, a->before_control);
		if (!ret)
			ret = regmap_write(map, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
		if (!ret)
			ret = sm5440_conversion_readback(map, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
		if (!ret)
			ret = sm5440_conversion_clock(a, &now);
		if (ret)
			return sm5440_conversion_fail(map, a, ret);
		a->acquired_ms = now; /* oldest plausible acquisition, never publication */
		a->expected_control = (a->before_control & ~SM5440_CONVERSION_FIELDS) |
				      SM5440_ADC_ENABLE | SM5440_ADC_AVG32;
		ret = regmap_update_bits(map, SM5440_ADCCNTL1, SM5440_CONVERSION_FIELDS,
					 a->expected_control);
		if (!ret)
			ret = sm5440_conversion_readback(map, SM5440_ADCCNTL1, a->expected_control);
		if (!ret)
			ret = sm5440_conversion_clock(a, &now);
		if (ret)
			return sm5440_conversion_fail(map, a, ret);
		a->state = SM5440_CONVERSION_WAIT;
		return -EINPROGRESS;
	}
	ret = sm5440_conversion_readback(map, SM5440_ADCCNTL1, a->expected_control);
	if (!ret)
		ret = sm5440_conversion_readback(map, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
	if (!ret)
		ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	if (!a->ready)
		return -EINPROGRESS;
	ret = regmap_bulk_read(map, SM5440_ADC_VBUS, a->adc, sizeof(a->adc));
	if (!ret)
		ret = sm5440_conversion_status(map, a);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL1, &value);
	if (!ret && value != a->expected_control)
		ret = -EIO;
	if (!ret)
		ret = sm5440_conversion_readback(map, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
	if (!ret)
		ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	a->vbus_uv = sm5440_vbus_uv(a->adc[0], a->adc[1]);
	a->ibus_ua = sm5440_ibus_ua(a->adc[4], a->adc[5]);
	a->die_decic = sm5440_die_decic(a->adc[8]);
	a->vbat_uv = sm5440_vbat_uv(a->adc[9], a->adc[10]);
	/* Transport plausibility only; actual target/current/thermal bounds live
	 * in the transaction core. Keep raw microvolts and625uA current precision.
	 */
	if (a->vbat_uv < 2500000 || a->vbat_uv > 4600000)
		return sm5440_conversion_fail(map, a, -ERANGE);
	a->data_acquired = true;
	a->state = SM5440_CONVERSION_MEASURED;
	/* Current/fault supervisor must be able to stop the pump BEFORE converter
	 * restoration. Raw data is not published valid until checked finish.
	 */
	if (a->defer_cleanup)
		return -EINPROGRESS;
	return sm5440_conversion_finish(map, a);
}

int sm5440_conversion_finish(struct regmap *map, struct sm5440_conversion *a)
{
	u64 now;
	int ret;

	if (!map || !a)
		return -EINVAL;
	if (a->state != SM5440_CONVERSION_MEASURED || !a->data_acquired)
		return -EALREADY;
	ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	ret = sm5440_conversion_cleanup(map, a);
	if (!ret)
		ret = sm5440_conversion_status(map, a);
	if (!ret)
		ret = sm5440_conversion_clock(a, &now);
	if (ret)
		return sm5440_conversion_fail(map, a, ret);
	a->completed_ms = now;
	a->sample.observed_ms = a->acquired_ms;
	a->sample.vbus_mv = a->vbus_uv / 1000;
	a->sample.vbat_mv = a->vbat_uv / 1000;
	a->sample.ibus_ua = a->ibus_ua;
	a->sample.faults = a->faults;
	a->sample.online = true;
	a->sample.pump_on = a->running;
	a->sample.valid = true;
	a->state = SM5440_CONVERSION_DONE;
	a->enabled = false;
	return 0;
}

int sm5440_conversion_cancel(struct regmap *map, struct sm5440_conversion *a)
{
	int ret;

	if (!map || !a)
		return -EINVAL;
	if (a->state == SM5440_CONVERSION_DONE ||
	    (a->state == SM5440_CONVERSION_FAULT &&
	     (!a->defer_cleanup || !a->owned || a->cleanup_attempted)))
		return -EALREADY;
	ret = sm5440_conversion_fail(map, a, -ECANCELED);
	sm5440_conversion_cleanup(map, a); /* explicitly drain a managed deferred request */
	return ret;
}
