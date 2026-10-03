// SPDX-License-Identifier: GPL-2.0-only
/* X710 vendor set_op_mode/set_ENHIZ, checked mainline register transaction.
 * Not in Kbuild, no live caller/export/activation. See SM5440_PUMP_ACTUATOR.md.
 */
#include <linux/compiler.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>

#include "sm5440-actuator.h"
#include "sm5440-hw.h"
#include "sm5714-pd-policy.h"

static bool sm5440_actuator_offer(const struct sm5714_pd_snapshot *source,
				 unsigned int mv, unsigned int ma)
{
	unsigned int i;

	for (i = 0; i < source->nr_source_pdos; i++)
		if (sm5714_validate_pps_request(source->source_pdos[i],
					 RDO_PROG(i + 1, mv, ma, 0)))
			return true;
	return false;
}

static int sm5440_actuator_error(struct sm5440_actuator *a, int ret)
{
	if (!a->operation_error)
		a->operation_error = ret;
	return ret;
}

static int sm5440_actuator_guard(struct sm5440_actuator *a,
				const struct x710_charge_facts *facts,
				const struct x710_physical_sample *sample,
				const struct sm5714_pd_snapshot *source,
				unsigned int mv, unsigned int ma)
{
	u64 now = ktime_to_ms(ktime_get_boottime());

	if (!a->enabled || !a->switching_inhibited || !a->lease || !a->epoch || !a->generation ||
	    READ_ONCE(*a->generation) != a->epoch || facts->epoch != a->epoch)
		return -ECANCELED;
	if (mv < 8200 || mv > 10500 || mv % 20 || ma < 1000 || ma > 1800 || ma % 50)
		return -ERANGE;
	if (!now || now < a->last_clock_ms)
		return -ETIME;
	a->last_clock_ms = now;
	if (!facts->observed_ms || facts->observed_ms > now ||
	    now - facts->observed_ms > X710_FACTS_MAX_AGE_MS - X710_MONITOR_DEADLINE_MS ||
	    !sample->observed_ms || sample->observed_ms > now ||
	    now - sample->observed_ms > X710_ADC_MAX_AGE_MS ||
	    !a->watchdog.serviced_ms || a->watchdog.serviced_ms > now ||
	    now - a->watchdog.serviced_ms > SM5440_WATCHDOG_SERVICE_MS ||
	    !source->started_ms || source->started_ms > source->completed_ms ||
	    source->completed_ms > now ||
	    now - source->started_ms > X710_FACTS_MAX_AGE_MS - X710_MONITOR_DEADLINE_MS)
		return -ESTALE;
	/* Capability label is not active mode: fixed ONLINE1 never admits ON. */
	if (!a->instance || !a->source_generation || !a->budget_generation ||
	    source->instance != a->instance ||
	    source->source_generation != a->source_generation ||
	    source->budget_generation != a->budget_generation || source->online != 2 ||
	    !source->pps_contract || !source->charge_requested ||
	    (source->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS &&
	     source->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS) ||
	    !source->nr_source_pdos || source->nr_source_pdos > SM5714_SOURCE_PDO_MAX ||
	    source->budget_mv != mv || source->budget_ma != ma ||
	    source->voltage_uv != (int)(mv * 1000) || source->current_ua != (int)(ma * 1000))
		return -EPERM;
	if (!x710_charge_eligible(facts) || facts->die_decic >= 420 ||
	    mv < facts->apdo_min_mv || mv > facts->apdo_max_mv || ma > facts->apdo_ma ||
	    !sample->valid || !sample->online || sample->faults || sample->pump_on ||
	    sample->ibus_ua || sample->vbat_mv < 3500 || sample->vbat_mv >= 4300 ||
	    sample->vbus_mv < mv - 100 || sample->vbus_mv > mv + 100 ||
	    sample->vbus_mv > 10500 || !sm5440_actuator_offer(source, mv, ma))
		return -EPERM;
	return 0;
}

static int sm5440_actuator_status(struct regmap *map, bool running)
{
	unsigned int mode;
	u8 status[4];
	int ret = regmap_read(map, SM5440_CNTL5, &mode);

	if (!ret && (mode & SM5440_MODE_MASK) != (running ? BIT(2) : 0))
		ret = -EBUSY;
	if (!ret)
		ret = regmap_bulk_read(map, SM5440_STATUS1, status, sizeof(status));
	if (!ret && (sm5440_decode_faults(status, running, 1) || (status[2] & BIT(6))))
		ret = -EIO;
	if (!ret && !(status[2] & BIT(5)))
		ret = -ENOLINK;
	return ret;
}

static int sm5440_actuator_update(struct regmap *map, u8 reg, u8 mask,
				  u8 target, u8 before)
{
	unsigned int after;
	int ret = regmap_update_bits(map, reg, mask, target);

	if (!ret)
		ret = regmap_read(map, reg, &after);
	if (!ret && after != ((before & ~mask) | (target & mask)))
		ret = -EIO;
	return ret;
}

/* Verify settings and immutable witnesses again, not cached flags alone. */
static int sm5440_actuator_prepared(struct regmap *map, struct sm5440_actuator *a,
				   unsigned int ma)
{
	static const u8 regs[3] = { 0x16, 0x14, 0x12 };
	static const u8 masks[3] = { 0x7f, 0x3f, 0x1f };
	static const u8 witnesses[10] = { 0x0c, 0x0d, 0x0e, 0x0f, 0x11,
				       0x13, 0x15, 0x19, 0x1a, 0x1b };
	u8 target[3];
	unsigned int value, khz;
	int i, ret;

	if (a->controls.state != SM5440_CONTROL_PREPARED || !a->controls.pending ||
	    a->controls.attempted != 7 || !a->controls.witness_valid ||
	    a->controls.operation_error || a->controls.restore_error ||
	    a->watchdog.state != SM5440_WATCHDOG_ARMED || !a->watchdog.owned ||
	    a->watchdog.epoch != a->epoch || a->watchdog.operation_error ||
	    a->watchdog.before != a->controls.witness[0] ||
	    (a->watchdog.expected & 0xf1) != 0xc0)
		return -EPERM;
	ret = regmap_read(map, SM5440_DEVICEID, &value);
	if (!ret && (value & 0xf) != 1)
		ret = -ENODEV;
	if (ret)
		return ret;
	khz = ma <= 1100 ? 450 : ma <= 1700 ? 650 : 850;
	target[0] = sm5440_ibus_code(ma);
	target[1] = sm5440_vbat_code(4440);
	target[2] = sm5440_frequency_code(khz);
	for (i = 0; i < 3; i++) {
		ret = regmap_read(map, regs[i], &value);
		if (!ret && value != ((a->controls.before[i] & ~masks[i]) | target[i]))
			ret = -EIO;
		if (ret)
			return ret;
	}
	for (i = 0; i < 10; i++) {
		u8 expected = i == 0 ? a->watchdog.expected :
			i == 4 && a->enhiz_owned ? a->cntl6_before & ~SM5440_ENHIZ :
			a->controls.witness[i];

		ret = regmap_read(map, witnesses[i], &value);
		if (!ret && value != expected)
			ret = -EIO;
		if (ret)
			return ret;
	}
	return 0;
}

int sm5440_actuator_stop(struct regmap *map, struct sm5440_actuator *a)
{
	unsigned int mode, cntl6;
	int ret, err;

	if (!map || !a)
		return -EINVAL;
	if (a->cleanup_attempted)
		return a->cleanup_error;
	a->cleanup_attempted = true;
	a->attempted = true; /* stop/PM must never permit a later rearm */
	a->enabled = false;
	a->off_verified = false;
	/* Safety stop also works before admission/cancelled; never writes ON. */
	ret = regmap_update_bits(map, SM5440_CNTL5, SM5440_MODE_MASK, 0);
	err = regmap_read(map, SM5440_CNTL5, &mode);
	if (!err && (mode & SM5440_MODE_MASK))
		err = -EBUSY;
	if (!ret)
		ret = err;
	if (err)
		goto out;
	a->off_verified = true;
	a->mode_possible = false;
	if (a->enhiz_owned) {
		err = regmap_read(map, SM5440_CNTL6, &cntl6);
		if (!err)
			err = sm5440_actuator_update(map, SM5440_CNTL6, SM5440_ENHIZ,
					      a->cntl6_before, cntl6);
		if (!err && ((cntl6 ^ a->cntl6_before) & ~SM5440_ENHIZ))
			err = -EIO;
		if (!err)
			a->enhiz_owned = false;
		if (!ret)
			ret = err;
	}
	/* Restoring CNTL1 first preserves the settings layer's original witness. */
	err = sm5440_watchdog_restore_off(map, &a->watchdog);
	if (!ret)
		ret = err;
	err = sm5440_control_restore(map, &a->controls);
	if (!ret)
		ret = err;
out:
	a->cleanup_error = ret;
	return ret;
}

int sm5440_actuator_start(struct regmap *map, struct sm5440_actuator *a,
			  const struct x710_charge_facts *facts,
			  const struct x710_physical_sample *sample,
			  const struct sm5714_pd_snapshot *source,
			  unsigned int mv, unsigned int ma)
{
	unsigned int cntl6, mode;
	int ret;

	if (!map || !a || !facts || !sample || !source)
		return -EINVAL;
	if (a->attempted)
		return -EALREADY;
	a->attempted = true;
	ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (ret) {
		if (a->controls.pending || a->watchdog.owned)
			goto fail; /* no ON, but do not strand an already owned preparation */
		return sm5440_actuator_error(a, ret);
	}
	ret = sm5440_actuator_status(map, false);
	if (!ret)
		ret = sm5440_actuator_prepared(map, a, ma);
	if (!ret)
		ret = regmap_read(map, SM5440_CNTL6, &cntl6);
	if (!ret && cntl6 != 0x09 && cntl6 != 0x89)
		ret = -EPERM; /* source-proved PWM/HIZ values only */
	if (!ret)
		ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (ret)
		goto fail;
	a->cntl6_before = cntl6;
	a->enhiz_owned = true; /* uncertain I2C may have changed ENHIZ */
	ret = sm5440_actuator_update(map, SM5440_CNTL6, SM5440_ENHIZ, 0, cntl6);
	if (!ret)
		ret = sm5440_actuator_status(map, false);
	if (!ret)
		ret = regmap_read(map, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY;
	if (!ret)
		ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (ret)
		goto fail;
	a->mode_possible = true;
	a->off_verified = false;
	ret = sm5440_actuator_update(map, SM5440_CNTL5, SM5440_MODE_MASK, BIT(2), mode);
	if (!ret)
		ret = sm5440_actuator_status(map, true);
	if (!ret)
		ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (!ret) {
		a->active_mv = mv;
		a->active_ma = ma;
		return 0; /* register ON only; caller still requires fresh post-ON ADC */
	}
fail:
	sm5440_actuator_error(a, ret);
	sm5440_actuator_stop(map, a);
	return ret;
}

/* Fedora sm5440_renegotiate_pps(): mode OFF across every Request, retaining
 * prepared fields/ENHIZ/WDT. No I/O or lock is held across TCPM/ADC waits here.
 */
int sm5440_actuator_pause(struct regmap *map, struct sm5440_actuator *a)
{
	unsigned int mode, adc;
	u64 now;
	int ret;

	if (!map || !a)
		return -EINVAL;
	if (a->paused || a->cleanup_attempted)
		return -EALREADY;
	if (!a->attempted && !a->controls.pending && !a->watchdog.owned && !a->mode_possible)
		return -EPERM;
	if (!a->enabled || !a->attempted || !a->mode_possible || a->off_verified ||
	    a->operation_error || !a->active_mv || !a->active_ma || !a->generation ||
	    !a->epoch || READ_ONCE(*a->generation) != a->epoch)
		ret = -ECANCELED;
	else if (a->pause_sequence == ~0ULL)
		ret = -EOVERFLOW;
	else
		ret = sm5440_actuator_status(map, true);
	if (!ret)
		ret = sm5440_actuator_prepared(map, a, a->active_ma);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL1, &adc);
	if (!ret && (adc & SM5440_ADC_ENABLE))
		ret = -EBUSY; /* single owner must drain measurement before Request */
	if (!ret)
		ret = regmap_read(map, SM5440_CNTL5, &mode);
	now = ktime_to_ms(ktime_get_boottime());
	if (!ret && (!now || now < a->last_clock_ms || !a->watchdog.serviced_ms ||
		     now < a->watchdog.serviced_ms ||
		     now - a->watchdog.serviced_ms > SM5440_WATCHDOG_SERVICE_MS ||
		     READ_ONCE(*a->generation) != a->epoch))
		ret = -ETIME;
	if (ret)
		goto fail;
	a->paused = true; /* ownership before a possibly uncertain OFF write */
	a->resume_attempted = false;
	a->pause_started_ms = now;
	a->paused_budget_generation = a->budget_generation;
	a->pause_sequence++;
	a->last_clock_ms = now;
	ret = sm5440_actuator_update(map, SM5440_CNTL5, SM5440_MODE_MASK, 0, mode);
	if (ret) {
		/* First OFF is uncertain: retain ownership/WDT, do not hide it behind
		 * another OFF attempt from terminal cleanup or an outer fallback.
		 */
		sm5440_actuator_error(a, ret);
		a->cleanup_attempted = true;
		a->enabled = false;
		a->cleanup_error = ret;
		return ret;
	}
	a->mode_possible = false;
	a->off_verified = true;
	if (!ret)
		ret = sm5440_actuator_status(map, false);
	now = ktime_to_ms(ktime_get_boottime());
	if (!ret && (!now || now < a->last_clock_ms ||
		     now - a->pause_started_ms > SM5440_WATCHDOG_SERVICE_MS ||
		     now - a->watchdog.serviced_ms > SM5440_WATCHDOG_SERVICE_MS ||
		     READ_ONCE(*a->generation) != a->epoch))
		ret = -ETIME;
	if (ret)
		goto fail;
	a->last_clock_ms = now;
	return 0;
fail:
	sm5440_actuator_error(a, ret);
	sm5440_actuator_stop(map, a);
	return ret;
}

/* Source receipt binds to the actual post-pause native producer generation;
 * never change it merely to admit an old budget or capability-only label.
 */
int sm5440_actuator_resume(struct regmap *map, struct sm5440_actuator *a,
			   const struct x710_charge_facts *facts,
			   const struct x710_physical_sample *sample,
			   const struct sm5714_pd_snapshot *source,
			   unsigned int mv, unsigned int ma)
{
	unsigned int value, mode, khz;
	u64 now;
	int ret;

	if (!map || !a)
		return -EINVAL;
	if (!a->paused || a->resume_attempted || a->cleanup_attempted)
		return -EALREADY;
	a->resume_attempted = true;
	if (!facts || !sample || !source) {
		ret = -EINVAL;
		goto fail;
	}
	now = ktime_to_ms(ktime_get_boottime());
	if (!a->off_verified || a->mode_possible || !a->pause_started_ms ||
	    !now || now < a->pause_started_ms ||
	    now - a->pause_started_ms > SM5440_WATCHDOG_SERVICE_MS ||
	    !a->active_ma || ma > a->active_ma || source->started_ms < a->pause_started_ms ||
	    sample->observed_ms < source->completed_ms ||
	    source->budget_generation <= a->paused_budget_generation ||
	    source->instance != a->instance || source->source_generation != a->source_generation) {
		ret = -ESTALE;
		goto fail;
	}
	a->budget_generation = source->budget_generation;
	ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (!ret)
		ret = sm5440_actuator_status(map, false);
	if (!ret)
		ret = sm5440_actuator_prepared(map, a, a->active_ma);
	if (!ret)
		ret = regmap_read(map, SM5440_ADCCNTL1, &value);
	if (!ret && value & SM5440_ADC_ENABLE)
		ret = -EBUSY;
	if (ret)
		goto fail;
	/* Approved current can only decrease while verified OFF. Original saved
	 * bytes remain the terminal cleanup target; no vendor current margin.
	 */
	if (ma < a->active_ma) {
		ret = regmap_read(map, 0x16, &value);
		if (!ret)
			ret = sm5440_actuator_update(map, 0x16, 0x7f, sm5440_ibus_code(ma), value);
		khz = ma <= 1100 ? 450 : ma <= 1700 ? 650 : 850;
		if (!ret)
			ret = regmap_read(map, 0x12, &value);
		if (!ret)
			ret = sm5440_actuator_update(map, 0x12, 0x1f, sm5440_frequency_code(khz), value);
		if (ret)
			goto fail;
	}
	ret = sm5440_actuator_prepared(map, a, ma);
	if (!ret)
		ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (!ret)
		ret = regmap_read(map, SM5440_CNTL5, &mode);
	if (!ret && mode & SM5440_MODE_MASK)
		ret = -EBUSY;
	if (!ret)
		ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (ret)
		goto fail;
	a->mode_possible = true;
	a->off_verified = false;
	ret = sm5440_actuator_update(map, SM5440_CNTL5, SM5440_MODE_MASK, BIT(2), mode);
	if (!ret)
		ret = sm5440_actuator_status(map, true);
	if (!ret)
		ret = sm5440_actuator_guard(a, facts, sample, source, mv, ma);
	if (ret)
		goto fail;
	a->active_mv = mv;
	a->active_ma = ma;
	a->paused = false;
	return 0; /* fresh post-ON supervisor/core observation is still required */
fail:
	sm5440_actuator_error(a, ret);
	sm5440_actuator_stop(map, a);
	return ret;
}
