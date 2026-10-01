// SPDX-License-Identifier: GPL-2.0-only
/* Default-inactive X710 charging transaction core. A live hardware adapter is
 * deliberately NOT supplied until passive ADC/software-OCP/PM acceptance.
 * No pump register, TCPM protocol engine or auto-retry thread is in this file.
 * The same production C functions run in host fault-injection tests.
 */
#include <linux/errno.h>
#include <linux/module.h>

#include "x710-charging-policy.h"

bool x710_charge_eligible(const struct x710_charge_facts *f)
{
	/* Bringup limits, narrower than X710 vendor (>18,<42C, endSOC95).
	 * Invalid or absent measurements can never be replaced by defaults.
	 */
	return f && f->epoch && f->observed_ms && f->attached &&
		f->battery_present && f->healthy &&
		f->pack_valid && f->voltage_valid && f->soc_valid && f->die_valid &&
		f->adc_valid && f->fixed_healthy && f->apdo && f->thermal_normal &&
		f->software_ocp_verified && !f->suspended && !f->fault &&
		f->apdo_min_mv && f->apdo_min_mv <= f->apdo_max_mv && f->apdo_ma &&
		f->capacity >= 5 && f->capacity < 80 &&
		f->vbat_mv >= 3500 && f->vbat_mv < 4300 &&
		f->pack_decic >= 200 && f->pack_decic < 380 &&
		f->die_decic >= 0 && f->die_decic < 550 &&
		(f->fixed_mv == 5000 || f->fixed_mv == 9000);
}

enum x710_thermal_zone x710_vendor_zone(int decic, enum x710_thermal_zone previous)
{
	/* X710 r04 wire thresholds; sec_bat_set_threshold() uses19 deciC.
	 * Pure audit model only: does not alter the validated Stage1 thermistor
	 * policy or import the vendor's aggregate zone-current votes.
	 */
	int cold = 0, cool3 = 50, cool2 = 150, cool1 = 180;
	int warm = 420, hot = 500;

	if (previous == X710_OVERHEAT) {
		hot -= 19;
		warm -= 19;
	} else if (previous == X710_WARM) {
		warm -= 19;
	}
	if (previous <= X710_COOL1)
		cool1 += 19;
	if (previous <= X710_COOL2)
		cool2 += 19;
	if (previous <= X710_COOL3)
		cool3 += 19;
	if (previous == X710_COLD)
		cold += 19;
	if (decic >= hot)
		return X710_OVERHEAT;
	if (decic >= warm)
		return X710_WARM;
	if (decic <= cold)
		return X710_COLD;
	if (decic <= cool3)
		return X710_COOL3;
	if (decic <= cool2)
		return X710_COOL2;
	if (decic <= cool1)
		return X710_COOL1;
	return X710_NORMAL;
}

int x710_pps_target(unsigned int vbat_mv, unsigned int offer_min_mv,
		    unsigned int offer_max_mv, unsigned int offer_ma,
		    unsigned int *target_mv, unsigned int *target_ma)
{
	u64 mv;
	unsigned int ma, minimum, maximum;

	if (!target_mv || !target_ma || vbat_mv < 3500 || vbat_mv >= 4300 ||
	    !offer_min_mv || offer_min_mv > offer_max_mv)
		return -ERANGE;
	minimum = offer_min_mv > 8200 ? offer_min_mv : 8200;
	maximum = offer_max_mv < 10500 ? offer_max_mv : 10500;
	ma = offer_ma < 1800 ? offer_ma : 1800;
	ma -= ma % 50;
	if (minimum > maximum || ma < 1000)
		return -ERANGE;
	/* Vendor _calc_pps_v_init_offset: r_ttl320000uohm +200mV.
	 * X710 mainline initial cap1800mA, never vendor's full battery target.
	 */
	mv = (u64)vbat_mv * 2 + (u64)ma * 320 / 1000 + 200;
	if (mv < minimum)
		mv = minimum;
	mv = (mv + 19) / 20 * 20;
	/* A source ceiling too low for headroom is not silently clamped down. */
	if (mv > maximum)
		return -ERANGE;
	*target_mv = mv;
	*target_ma = ma;
	return 0;
}

unsigned int x710_retry_seconds(unsigned int failures)
{
	/* Fedora bounded retry reference, NOT an enabled retry policy. */
	if (!failures)
		return 0;
	if (failures >= 5)
		return 300;
	return 1U << failures;
}

static bool x710_ops_valid(const struct x710_charge_ops *ops)
{
	return ops && ops->now_ms && ops->current_epoch && ops->read_facts &&
		ops->switching_gate &&
		ops->pump_off && ops->pps_request && ops->measure && ops->pump_prepare &&
		ops->pump_on && ops->fixed_restore;
}

static int x710_now(struct x710_charge_transaction *tx,
		    const struct x710_charge_ops *ops, void *ctx, u64 *now)
{
	*now = ops->now_ms(ctx);
	if (!*now || *now < tx->last_clock_ms)
		return -ETIME;
	tx->last_clock_ms = *now;
	return 0;
}

static bool x710_fresh(u64 observed, u64 now, unsigned int maximum_age)
{
	return observed && observed <= now && now - observed <= maximum_age;
}

static bool x710_target_supported(const struct x710_charge_transaction *tx,
				 const struct x710_charge_facts *facts)
{
	return tx->target_mv >= 8200 && tx->target_mv <= 10500 &&
		!(tx->target_mv % 20) && tx->target_ma >= 1000 &&
		tx->target_ma <= 1800 && !(tx->target_ma % 50) &&
		tx->target_mv >= facts->apdo_min_mv &&
		tx->target_mv <= facts->apdo_max_mv && tx->target_ma <= facts->apdo_ma;
}

static int x710_fresh_eligible(struct x710_charge_transaction *tx,
			      const struct x710_charge_ops *ops, void *ctx)
{
	struct x710_charge_facts facts = {};
	u64 now;
	int ret;

	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	ret = ops->read_facts(ctx, &facts);
	if (ret)
		return ret;
	/* An epoch can change while the provider is acquiring its snapshot. */
	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	ret = x710_now(tx, ops, ctx, &now);
	if (ret)
		return ret;
	if (!x710_fresh(facts.observed_ms, now, X710_FACTS_MAX_AGE_MS))
		return -ESTALE;
	if (facts.epoch != tx->epoch || !x710_charge_eligible(&facts) ||
	    !x710_target_supported(tx, &facts))
		return -EPERM;
	tx->last_facts_ms = facts.observed_ms;
	return 0;
}

static int x710_measure_safe(struct x710_charge_transaction *tx,
			     const struct x710_charge_ops *ops, void *ctx,
			     unsigned int target, bool running)
{
	struct x710_physical_sample sample = {};
	u64 now;
	int ret;

	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	ret = ops->measure(ctx, &sample);
	if (ret)
		return ret;
	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	ret = x710_now(tx, ops, ctx, &now);
	if (ret)
		return ret;
	if (!x710_fresh(sample.observed_ms, now, X710_ADC_MAX_AGE_MS))
		return -ESTALE;
	if (!sample.valid || !sample.online || sample.faults ||
	    sample.pump_on != running || sample.vbat_mv < 3500 ||
	    sample.vbat_mv >= 4300 || sample.vbus_mv > 10500 ||
	    target < 100 || sample.vbus_mv + 100 < target ||
	    sample.vbus_mv > target + 100 ||
	    sample.ibus_ua > (running ? tx->target_ma * 1000 : 100000))
		return -ERANGE;
	return 0;
}

static int x710_monitor_deadline(struct x710_charge_transaction *tx,
				const struct x710_charge_ops *ops, void *ctx,
				u64 *now)
{
	int ret = x710_now(tx, ops, ctx, now);

	if (ret)
		return ret;
	if (!x710_fresh(tx->last_monitor_ms, *now, X710_MONITOR_DEADLINE_MS))
		return -ETIME;
	return 0;
}

static int x710_on_observed(struct x710_charge_transaction *tx,
			     const struct x710_charge_ops *ops, void *ctx)
{
	u64 start, end;
	int ret;

	ret = x710_now(tx, ops, ctx, &start);
	/* Recheck immediately before ON and reserve the observation window.
	 * Scheduling/negotiation delays cannot turn an old snapshot into a grant.
	 */
	if (!ret && !x710_fresh(tx->last_facts_ms, start,
			       X710_FACTS_MAX_AGE_MS - X710_MONITOR_DEADLINE_MS))
		ret = -ESTALE;
	if (!ret)
		ret = ops->pump_on(ctx);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, true);
	if (!ret)
		ret = x710_now(tx, ops, ctx, &end);
	if (!ret && end - start > X710_MONITOR_DEADLINE_MS)
		ret = -ETIME;
	if (!ret)
		tx->last_monitor_ms = end;
	return ret;
}

/* Failures remain visible even after a successful fixed fallback. OFF failure
 * is not hidden by another operation, and cannot authorize a voltage change.
 */
static int x710_fallback(struct x710_charge_transaction *tx,
			 const struct x710_charge_ops *ops, void *ctx, int error)
{
	int ret;

	tx->last_error = error;
	if (error)
		tx->armed = false;
	tx->state = X710_DIRECT_STOPPING;
	ret = ops->pump_off(ctx);
	if (ret)
		goto fault;
	if (!ops->current_epoch(ctx, tx->epoch)) {
		tx->state = X710_CHARGE_OFF;
		return error ? error : -ECANCELED;
	}
	tx->state = X710_FIXED_RESTORE;
	ret = ops->fixed_restore(ctx);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->fixed_mv, false);
	if (!ret && ops->current_epoch(ctx, tx->epoch))
		ret = ops->switching_gate(ctx, false);
	else if (!ret)
		ret = -ECANCELED;
	if (ret)
		goto fault;
	tx->switching_inhibited = false;
	tx->state = X710_SWITCHING;
	return error;
fault:
	tx->state = X710_CHARGE_FAULT;
	tx->armed = false;
	tx->last_error = ret;
	return ret;
}

int x710_charge_start(struct x710_charge_transaction *tx,
		      const struct x710_charge_facts *facts,
		      const struct x710_charge_ops *ops, void *ctx)
{
	int ret;

	if (!tx || !x710_ops_valid(ops))
		return -EINVAL;
	if (tx->suspended)
		return -EBUSY;
	if (!tx->armed)
		return -EACCES;
	if (tx->state != X710_SWITCHING || !x710_charge_eligible(facts) ||
	    !x710_target_supported(tx, facts))
		return -EPERM;
	tx->epoch = facts->epoch;
	tx->fixed_mv = facts->fixed_mv;
	ret = x710_fresh_eligible(tx, ops, ctx);
	if (ret) {
		tx->armed = false;
		tx->last_error = ret;
		return ret;
	}
	tx->state = X710_DIRECT_PREPARE;
	/* Ownership must be latched by adapter before any Q4 I/O. On an
	 * ambiguous switching write, retain the inhibit through fallback.
	 */
	tx->switching_inhibited = true;
	ret = ops->switching_gate(ctx, true);
	if (ret)
		return x710_fallback(tx, ops, ctx, ret);
	ret = ops->pump_off(ctx);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (ret)
		return x710_fallback(tx, ops, ctx, ret);
	tx->state = X710_PPS_NEGOTIATING;
	ret = ops->pps_request(ctx, tx->target_mv, tx->target_ma);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, false);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (ret)
		return x710_fallback(tx, ops, ctx, ret);
	tx->state = X710_DIRECT_STARTING;
	ret = ops->pump_prepare(ctx, tx->target_ma);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = x710_on_observed(tx, ops, ctx);
	if (ret)
		return x710_fallback(tx, ops, ctx, ret);
	tx->state = X710_DIRECT_ACTIVE;
	tx->last_error = 0;
	return 0;
}

int x710_charge_refresh(struct x710_charge_transaction *tx,
			const struct x710_charge_ops *ops, void *ctx)
{
	u64 now;
	int ret;

	if (!tx || !x710_ops_valid(ops))
		return -EINVAL;
	if (tx->state != X710_DIRECT_ACTIVE)
		return -EPERM;
	if (!tx->armed || tx->suspended)
		return x710_fallback(tx, ops, ctx, -EACCES);
	/* Fedora measured REVBLK: pump OFF before every source refresh. */
	ret = ops->pump_off(ctx);
	if (!ret)
		ret = x710_monitor_deadline(tx, ops, ctx, &now);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = ops->pps_request(ctx, tx->target_mv, tx->target_ma);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, false);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = x710_on_observed(tx, ops, ctx);
	return ret ? x710_fallback(tx, ops, ctx, ret) : 0;
}

int x710_charge_monitor(struct x710_charge_transaction *tx,
			const struct x710_charge_ops *ops, void *ctx)
{
	u64 start, end;
	int ret;

	if (!tx || !x710_ops_valid(ops))
		return -EINVAL;
	if (tx->state != X710_DIRECT_ACTIVE)
		return -EPERM;
	if (!tx->armed || tx->suspended)
		return x710_fallback(tx, ops, ctx, -EACCES);
	ret = x710_monitor_deadline(tx, ops, ctx, &start);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, true);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = x710_now(tx, ops, ctx, &end);
	if (!ret && end - start > X710_MONITOR_DEADLINE_MS)
		ret = -ETIME;
	if (ret)
		return x710_fallback(tx, ops, ctx, ret);
	tx->last_monitor_ms = end;
	return 0;
}

int x710_charge_stop(struct x710_charge_transaction *tx,
		     const struct x710_charge_ops *ops, void *ctx)
{
	if (!tx)
		return -EINVAL;
	tx->armed = false;
	if (!x710_ops_valid(ops))
		return -EINVAL; /* OFF is not proven with an invalid adapter. */
	if (!tx->switching_inhibited && tx->state == X710_SWITCHING)
		return 0;
	return x710_fallback(tx, ops, ctx, 0);
}

int x710_charge_suspend(struct x710_charge_transaction *tx,
			const struct x710_charge_ops *ops, void *ctx)
{
	if (!tx)
		return -EINVAL;
	/* Fedora ab123e7d sm5440_pm_notify: drain -> OFF -> fixed contract.
	 * The future adapter owns draining/serialization before this call. Unlike
	 * its unchecked restore, propagate failure and retain the PM/arming latch.
	 */
	tx->suspended = true;
	return x710_charge_stop(tx, ops, ctx);
}

int x710_charge_resume(struct x710_charge_transaction *tx)
{
	if (!tx || !tx->suspended)
		return -EINVAL;
	/* Only a proven quiesced transaction can clear the PM latch. An OFF/
	 * fixed-restore/epoch failure may not resume an unknown charging path.
	 * No I/O, retry, old PPS restoration or grant is performed here.
	 */
	if (tx->state != X710_SWITCHING || tx->switching_inhibited || tx->armed)
		return -EBUSY;
	tx->suspended = false;
	return 0;
}

MODULE_DESCRIPTION("X710 offline charging transaction core, no live activation adapter");
MODULE_LICENSE("GPL");
