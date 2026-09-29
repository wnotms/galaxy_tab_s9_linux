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
	return f && f->epoch && f->attached && f->battery_present && f->healthy &&
		f->pack_valid && f->voltage_valid && f->soc_valid && f->die_valid &&
		f->adc_valid && f->fixed_healthy && f->apdo && f->thermal_normal &&
		f->software_ocp_verified && !f->suspended && !f->fault &&
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
	return ops && ops->current_epoch && ops->read_facts && ops->switching_gate &&
		ops->pump_off && ops->pps_request && ops->measure && ops->pump_prepare &&
		ops->pump_on && ops->fixed_restore;
}

static int x710_fresh_eligible(struct x710_charge_transaction *tx,
			      const struct x710_charge_ops *ops, void *ctx)
{
	struct x710_charge_facts facts = {};
	int ret;

	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	ret = ops->read_facts(ctx, &facts);
	if (ret)
		return ret;
	if (facts.epoch != tx->epoch || !x710_charge_eligible(&facts))
		return -EPERM;
	return 0;
}

static int x710_measure_safe(struct x710_charge_transaction *tx,
			     const struct x710_charge_ops *ops, void *ctx,
			     unsigned int target, bool running)
{
	struct x710_physical_sample sample = {};
	int ret;

	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	ret = ops->measure(ctx, &sample);
	if (ret)
		return ret;
	if (!ops->current_epoch(ctx, tx->epoch))
		return -ECANCELED;
	if (!sample.valid || !sample.online || sample.faults ||
	    sample.pump_on != running || sample.vbat_mv < 3500 ||
	    sample.vbat_mv >= 4300 || sample.vbus_mv > 10500 ||
	    target < 100 || sample.vbus_mv + 100 < target ||
	    sample.vbus_mv > target + 100 ||
	    sample.ibus_ma > (running ? tx->target_ma : 100))
		return -ERANGE;
	return 0;
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
	if (!tx->armed)
		return -EACCES;
	if (tx->state != X710_SWITCHING || !x710_charge_eligible(facts) ||
	    tx->target_mv < 8200 || tx->target_mv > 10500 || tx->target_mv % 20 ||
	    tx->target_ma < 1000 || tx->target_ma > 1800 || tx->target_ma % 50)
		return -EPERM;
	tx->epoch = facts->epoch;
	tx->fixed_mv = facts->fixed_mv;
	ret = x710_fresh_eligible(tx, ops, ctx);
	if (ret)
		return ret;
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
		ret = ops->pump_on(ctx);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, true);
	if (ret)
		return x710_fallback(tx, ops, ctx, ret);
	tx->state = X710_DIRECT_ACTIVE;
	tx->last_error = 0;
	return 0;
}

int x710_charge_refresh(struct x710_charge_transaction *tx,
			const struct x710_charge_ops *ops, void *ctx)
{
	int ret;

	if (!tx || !x710_ops_valid(ops))
		return -EINVAL;
	if (tx->state != X710_DIRECT_ACTIVE)
		return -EPERM;
	if (!tx->armed)
		return x710_fallback(tx, ops, ctx, -EACCES);
	/* Fedora measured REVBLK: pump OFF before every source refresh. */
	ret = ops->pump_off(ctx);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = ops->pps_request(ctx, tx->target_mv, tx->target_ma);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, false);
	if (!ret)
		ret = x710_fresh_eligible(tx, ops, ctx);
	if (!ret)
		ret = ops->pump_on(ctx);
	if (!ret)
		ret = x710_measure_safe(tx, ops, ctx, tx->target_mv, true);
	return ret ? x710_fallback(tx, ops, ctx, ret) : 0;
}

int x710_charge_stop(struct x710_charge_transaction *tx,
		     const struct x710_charge_ops *ops, void *ctx)
{
	if (!tx || !x710_ops_valid(ops))
		return -EINVAL;
	if (!tx->switching_inhibited && tx->state == X710_SWITCHING)
		return 0;
	return x710_fallback(tx, ops, ctx, 0);
}

MODULE_DESCRIPTION("X710 offline charging transaction core, no live activation adapter");
MODULE_LICENSE("GPL");
