// SPDX-License-Identifier: GPL-2.0-only
/* One explicit native consumer; default-inactive direct charging. */
#include <linux/completion.h>
#include <linux/delay.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/power_supply.h>
#include <linux/string.h>
#include <linux/suspend.h>
#include <linux/usb/pd.h>
#include <linux/workqueue.h>

#include "sm5714-pd-policy.h"
#include "x710-charge-observer.h"
#include "x710-charge-controller.h"

/* These locks protect admission/publication, never supplier operations. */
static DEFINE_MUTEX(x710_controller_request_lock);
static DEFINE_MUTEX(x710_controller_lock);
static DECLARE_COMPLETION(x710_controller_done);
static struct workqueue_struct *x710_controller_wq;
static struct x710_controller_result x710_controller_result;
static u64 x710_controller_generation;
static bool x710_controller_quiescing = true, x710_controller_inflight;
static bool x710_controller_cancelled, x710_controller_unresolved;
static enum x710_controller_command x710_controller_command;
static unsigned int x710_controller_mv, x710_controller_ma;

/* This state belongs exclusively to the ordered worker, including cleanup. */
struct x710_native_controller {
	struct x710_charge_transaction tx;
	struct sm5440_native_owner hardware_owner;
	struct sm5714_pd_snapshot source, fixed;
	struct x710_charge_facts facts;
	struct x710_physical_sample physical;
	u64 generation, lease, pack_instance;
	u32 physical_vbus_uv;
	int die_decic;
	bool die_valid, hardware_owned, hardware_quiesced, pps_failed;
	bool fixed_observed, switching_released, pps_observed;
	int cleanup_error;
};

static struct x710_native_controller x710_controller;

static u64 x710_controller_now(void *unused)
{
	return ktime_to_ms(ktime_get_boottime());
}

static bool x710_controller_current(void *context, u64 epoch)
{
	struct x710_native_controller *c = context;
	bool valid;

	mutex_lock(&x710_controller_lock);
	valid = !x710_controller_quiescing && !x710_controller_cancelled &&
		x710_controller_generation == epoch && c->generation == epoch;
	mutex_unlock(&x710_controller_lock);
	return valid;
}

static bool x710_controller_fresh(u64 start, u64 end, u64 now, unsigned int age)
{
	return start && start <= end && end <= now && now - start <= age;
}

static bool x710_controller_source_same(const struct sm5714_pd_snapshot *a,
					const struct sm5714_pd_snapshot *b)
{
	return a->instance && a->source_generation && a->budget_generation &&
		a->instance == b->instance && a->source_generation == b->source_generation &&
		a->budget_generation == b->budget_generation &&
		a->nr_source_pdos <= SM5714_SOURCE_PDO_MAX &&
		a->nr_source_pdos == b->nr_source_pdos &&
		!memcmp(a->source_pdos, b->source_pdos,
			a->nr_source_pdos * sizeof(a->source_pdos[0])) &&
		a->budget_mv == b->budget_mv && a->budget_ma == b->budget_ma &&
		a->online == b->online && a->usb_type == b->usb_type &&
		a->voltage_uv == b->voltage_uv && a->current_ua == b->current_ua &&
		a->pps_contract == b->pps_contract && a->charge_requested && b->charge_requested;
}

static int x710_controller_source(struct x710_native_controller *c,
				  struct sm5714_pd_snapshot *out)
{
	if (c->source.pps_contract)
		return sm5714_pd_read_owned_snapshot(c->fixed.instance,
			c->fixed.source_generation, c->lease, out);
	return sm5714_pd_read_snapshot(out);
}

static int x710_controller_source_check(struct x710_native_controller *c,
					const struct sm5714_pd_snapshot *s)
{
	if (!x710_controller_source_same(&c->source, s))
		return -ESTALE;
	if (!s->budget_ma || s->voltage_uv != (int)(s->budget_mv * 1000U) ||
	    s->current_ua != (int)(s->budget_ma * 1000U))
		return -ERANGE;
	if (s->pps_contract) {
		if (s->online != 2 || !s->nr_source_pdos ||
		    (s->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS &&
		     s->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS) ||
		    s->budget_mv < SM5714_PPS_MIN_MV || s->budget_mv > SM5714_PPS_MAX_MV ||
		    s->budget_mv % 20 || s->budget_ma > SM5714_PPS_MAX_MA || s->budget_ma % 50)
			return -EPERM;
	} else if (s->online != 1 || s->budget_mv != 9000 ||
		   s->budget_ma > SM5714_FIXED_9V_MA) {
		return -EPERM;
	}
	return 0;
}

static int x710_controller_pack_check(struct x710_native_controller *c,
				      const struct sm5714_pack_snapshot *p,
				      const struct sm5714_pd_snapshot *s)
{
	if (!p->instance || p->instance != c->pack_instance ||
	    !p->state_generation || p->switching_lease != c->lease ||
	    !p->attached || !p->typec_owned || !p->typec_charge || !p->thermal_normal ||
	    !p->battery_present || p->health != POWER_SUPPLY_HEALTH_GOOD ||
	    p->capacity < 5 || p->capacity >= 80 || p->voltage_uv < 3500000 ||
	    p->voltage_uv >= 4300000 || p->pack_decic < 200 || p->pack_decic >= 380 ||
	    p->typec_mv != s->budget_mv || p->typec_ma != s->budget_ma ||
	    p->pps_contract != s->pps_contract)
		return -EPERM;
	return 0;
}

/* Every sleep is outside all supplier/publication locks. Cleanup measurements
 * use the original supplier gates even after consumer cancellation.
 */
static int x710_controller_measure(void *context, struct x710_physical_sample *out)
{
	struct x710_native_controller *c = context;
	struct sm5440_native_result result = {};
	struct sm5440_passive_measurement passive = {};
	u64 start = x710_controller_now(NULL), now;
	int ret;

	memset(out, 0, sizeof(*out));
	c->die_valid = false;
	if (c->hardware_owned) {
		ret = sm5440_native_control(SM5440_NATIVE_ADC_BEGIN,
					    &c->hardware_owner, NULL, &result);
		while (ret == -EINPROGRESS) {
			now = x710_controller_now(NULL);
			if (now < start || now - start > X710_ADC_MAX_AGE_MS)
				return -ETIMEDOUT;
			usleep_range(1000, 2000);
			ret = sm5440_native_control(SM5440_NATIVE_ADC_ADVANCE,
						    &c->hardware_owner, NULL, &result);
		}
		if (ret)
			return ret;
		*out = result.physical;
		c->physical_vbus_uv = result.vbus_uv;
		c->die_decic = result.die_decic;
		c->die_valid = result.die_valid;
	} else {
		ret = sm5440_passive_request_fresh(&passive);
		if (ret)
			return ret;
		*out = (struct x710_physical_sample) {
			.observed_ms = passive.observed_ms, .vbus_mv = passive.vbus_uv / 1000,
			.vbat_mv = passive.vbat_uv / 1000, .ibus_ua = passive.ibus_ua,
			.online = passive.online, .valid = true,
		};
		c->physical_vbus_uv = passive.vbus_uv;
		c->die_decic = passive.die_decic;
		c->die_valid = true;
	}
	now = x710_controller_now(NULL);
	if (!x710_controller_fresh(start, now, now, X710_ADC_MAX_AGE_MS) ||
	    !x710_controller_fresh(out->observed_ms, now, now, X710_ADC_MAX_AGE_MS) ||
	    !out->valid || !out->online || out->pump_on || out->faults || out->ibus_ua ||
	    out->vbat_mv < 3500 || out->vbat_mv >= 4300 ||
	    out->vbus_mv < 4500 || out->vbus_mv > SM5714_PPS_MAX_MV ||
	    !c->die_valid || c->die_decic < 0 || c->die_decic >= 420) {
		memset(out, 0, sizeof(*out));
		return -ERANGE;
	}
	c->physical = *out;
	return 0;
}

static int x710_controller_facts(void *context, struct x710_charge_facts *out)
{
	struct x710_native_controller *c = context;
	struct sm5714_pd_snapshot first = {}, last = {};
	struct sm5714_pack_snapshot a = {}, b = {};
	struct x710_physical_sample physical = {};
	u64 now, oldest;
	unsigned int i;
	int ret;

	memset(out, 0, sizeof(*out));
	if (!x710_controller_current(c, c->generation))
		return -ECANCELED;
	ret = x710_controller_source(c, &first);
	if (!ret)
		ret = x710_controller_source_check(c, &first);
	if (!ret)
		ret = sm5714_battery_read_pack(c->lease, &a);
	if (!ret)
		ret = x710_controller_pack_check(c, &a, &first);
	if (!ret)
		ret = x710_controller_measure(c, &physical);
	if (!ret)
		ret = sm5714_battery_read_pack(c->lease, &b);
	if (!ret)
		ret = x710_controller_source(c, &last);
	if (ret)
		return ret;
	now = x710_controller_now(NULL);
	if (!x710_controller_current(c, c->generation))
		return -ECANCELED;
	if (!x710_controller_source_same(&first, &last) ||
	    a.instance != b.instance || a.state_generation != b.state_generation ||
	    !x710_controller_fresh(first.started_ms, first.completed_ms, now, 500) ||
	    !x710_controller_fresh(last.started_ms, last.completed_ms, now, 500) ||
	    !x710_controller_fresh(a.started_ms, a.completed_ms, now, 500) ||
	    !x710_controller_fresh(b.started_ms, b.completed_ms, now, 500) ||
	    !x710_controller_fresh(physical.observed_ms, now, now, 100))
		return -ESTALE;
	ret = x710_controller_pack_check(c, &b, &last);
	if (ret)
		return ret;
	if (c->physical_vbus_uv + 100000ULL < last.budget_mv * 1000ULL ||
	    c->physical_vbus_uv > last.budget_mv * 1000ULL + 100000)
		return -ERANGE;
	oldest = min(first.started_ms, last.started_ms);
	oldest = min(oldest, min(a.started_ms, b.started_ms));
	oldest = min(oldest, physical.observed_ms);
	*out = (struct x710_charge_facts) {
		.epoch = c->generation, .observed_ms = oldest, .capacity = b.capacity,
		.pack_decic = b.pack_decic, .die_decic = c->die_decic,
		.vbat_mv = b.voltage_uv / 1000, .fixed_mv = c->fixed.budget_mv,
		.attached = true, .battery_present = true, .healthy = true,
		.pack_valid = true, .voltage_valid = true, .soc_valid = true,
		.die_valid = true, .adc_valid = true, .fixed_healthy = true,
		.thermal_normal = true,
		/* Physical OCP/cutoff qualification has not been obtained. */
		.software_ocp_verified = false,
	};
	/* These ranges come from the current source, not a remembered APDO. The
	 * board validator only bounds a requested pair; TCPM selects its PDO.
	 */
	for (i = 0; i < last.nr_source_pdos; i++) {
		u32 pdo = last.source_pdos[i];
		u32 rdo = RDO_PROG(i + 1, c->tx.target_mv, c->tx.target_ma,
				   RDO_USB_COMM | RDO_NO_SUSPEND);

		if (sm5714_validate_pps_request(pdo, rdo)) {
			out->apdo = true;
			out->apdo_min_mv = ((pdo >> 8) & 0xff) * 100;
			out->apdo_max_mv = ((pdo >> 17) & 0xff) * 100;
			out->apdo_ma = (pdo & 0x7f) * 50;
			break;
		}
	}
	if (!out->apdo) {
		memset(out, 0, sizeof(*out));
		return -EPERM;
	}
	c->facts = *out;
	return 0;
}

static int x710_controller_gate(void *context, bool inhibit)
{
	struct x710_native_controller *c = context;
	struct sm5714_fixed_proof proof = {};
	int ret;

	if (inhibit) {
		if (!x710_controller_current(c, c->generation))
			return -ECANCELED;
		ret = sm5714_battery_switching_acquire(&c->lease);
		/* A lease on error is a cleanup obligation, not an authorization. */
		return ret;
	}
	if (!c->lease)
		return 0;
	if (!c->hardware_quiesced || !c->physical.valid || c->physical.pump_on ||
	    c->physical.ibus_ua || !c->fixed_observed)
		return -EPERM;
	proof.observed_ms = c->physical.observed_ms;
	proof.vbus_uv = c->physical_vbus_uv;
	proof.ibus_ua = c->physical.ibus_ua;
	proof.pump_off = true;
	ret = sm5714_pd_release_fixed(c->fixed.instance, c->fixed.source_generation,
				      c->lease, &proof);
	if (!ret) {
		c->switching_released = true;
		c->lease = 0;
	}
	return ret;
}

static int x710_controller_off(void *context)
{
	struct x710_native_controller *c = context;
	struct sm5440_native_result result = {};
	int ret;

	if (!c->hardware_owned)
		return c->hardware_quiesced ? 0 : -EPERM;
	ret = sm5440_native_control(SM5440_NATIVE_RELEASE, &c->hardware_owner, NULL, &result);
	if (ret || !result.hardware_quiesced || result.owned)
		return ret ? ret : -EIO;
	c->hardware_owned = false;
	c->hardware_quiesced = true;
	return 0;
}

static int x710_controller_pps(void *context, unsigned int mv, unsigned int ma)
{
	struct x710_native_controller *c = context;
	struct sm5714_pd_snapshot pps = {};
	int ret;

	if (!x710_controller_current(c, c->generation) || !c->lease ||
	    !c->physical.valid || c->physical.pump_on || c->physical.ibus_ua)
		return -ECANCELED;
	ret = sm5714_pd_request_pps(c->fixed.instance, c->fixed.source_generation,
				    c->lease, mv, ma, &pps);
	c->pps_failed = !!ret;
	if (!ret && (pps.instance != c->fixed.instance ||
		     pps.source_generation != c->fixed.source_generation ||
		     !pps.pps_contract || pps.online != 2 ||
		     pps.budget_mv != mv || pps.budget_ma != ma))
		return -ESTALE;
	if (!ret)
		c->source = pps;
	return ret;
}

static int x710_controller_prepare(void *context, unsigned int ma)
{
	struct x710_native_controller *c = context;
	struct sm5440_native_input input = { .ma = ma };
	struct sm5440_native_result result = {};

	if (!x710_controller_current(c, c->generation) || !c->hardware_owned)
		return -ECANCELED;
	return sm5440_native_control(SM5440_NATIVE_PREPARE, &c->hardware_owner, &input, &result);
}

static int x710_controller_on(void *context)
{
	struct x710_native_controller *c = context;
	struct sm5440_native_input input = {
		.facts = &c->facts, .physical = &c->physical, .source = &c->source,
		.mv = c->tx.target_mv, .ma = c->tx.target_ma,
	};
	struct sm5440_native_result result = {};

	if (!x710_controller_current(c, c->generation) || !c->hardware_owned)
		return -ECANCELED;
	return sm5440_native_control(SM5440_NATIVE_START, &c->hardware_owner, &input, &result);
}

static int x710_controller_fixed(void *context)
{
	struct x710_native_controller *c = context;
	struct sm5714_pd_snapshot fixed = {};
	int ret;

	if (!c->hardware_quiesced || !c->lease)
		return -EPERM;
	if (c->pps_failed) {
		/* Native PPS failure already attempted restore. No hidden retry. */
		ret = sm5714_pd_read_snapshot(&fixed);
		if (ret || fixed.instance != c->fixed.instance ||
		    fixed.source_generation != c->fixed.source_generation)
			return ret ? ret : -ESTALE;
	} else {
		ret = sm5714_pd_restore_fixed(c->fixed.instance, c->fixed.source_generation,
					      c->lease, &fixed);
		if (ret)
			return ret;
	}
	if (fixed.pps_contract || fixed.online != 1 || fixed.budget_mv != c->fixed.budget_mv)
		return -ERANGE;
	c->source = fixed;
	c->fixed_observed = true;
	return 0;
}

static const struct x710_charge_ops x710_controller_ops = {
	.now_ms = x710_controller_now, .current_epoch = x710_controller_current,
	.read_facts = x710_controller_facts, .switching_gate = x710_controller_gate,
	.pump_off = x710_controller_off, .pps_request = x710_controller_pps,
	.measure = x710_controller_measure, .pump_prepare = x710_controller_prepare,
	.pump_on = x710_controller_on, .fixed_restore = x710_controller_fixed,
};

/* Cleanup may ignore consumer cancellation, never supplier/source identity.
 * No second protocol/OFF attempt after a supplier's terminal cleanup failure.
 */
static int x710_controller_cleanup(struct x710_native_controller *c)
{
	struct x710_physical_sample physical = {};
	int ret = 0;

	if (c->hardware_owned)
		ret = x710_controller_off(c);
	if (ret || !c->lease)
		return ret;
	ret = x710_controller_fixed(c);
	if (!ret)
		ret = x710_controller_measure(c, &physical);
	if (!ret && (c->physical_vbus_uv + 100000ULL < c->fixed.budget_mv * 1000ULL ||
		     c->physical_vbus_uv > c->fixed.budget_mv * 1000ULL + 100000))
		ret = -ERANGE;
	if (!ret)
		ret = x710_controller_gate(c, false);
	return ret;
}

static int x710_controller_roundtrip(struct x710_native_controller *c,
				     unsigned int mv, unsigned int ma)
{
	struct x710_observer_owner ordinary = {};
	struct x710_charge_observation observation = {};
	struct sm5440_native_result hardware = {};
	struct x710_charge_facts facts = {};
	unsigned int i;
	bool supported = false;
	int ret;

	ret = x710_charge_request_observation(&ordinary, &observation);
	if (ret)
		return ret;
	c->fixed = observation.source;
	c->source = observation.source;
	c->pack_instance = observation.pack.instance;
	if (!c->pack_instance)
		return -ESTALE;
	if (c->fixed.budget_mv != 9000 ||
	    c->fixed.nr_source_pdos > SM5714_SOURCE_PDO_MAX)
		return -EPERM;
	for (i = 0; i < c->fixed.nr_source_pdos; i++) {
		u32 rdo = RDO_PROG(i + 1, mv, ma, RDO_USB_COMM | RDO_NO_SUSPEND);

		if (sm5714_validate_pps_request(c->fixed.source_pdos[i], rdo))
			supported = true;
	}
	if (!supported || !x710_controller_current(c, c->generation))
		return -EPERM;
	ret = sm5440_native_control(SM5440_NATIVE_CLAIM, NULL, NULL, &hardware);
	c->hardware_owner = hardware.owner;
	c->hardware_owned = hardware.owned;
	c->hardware_quiesced = hardware.hardware_quiesced;
	if (ret)
		return ret;
	c->tx.state = X710_DIRECT_PREPARE;
	c->tx.target_mv = mv;
	c->tx.target_ma = ma;
	ret = x710_controller_facts(c, &facts);
	if (!ret)
		ret = x710_controller_gate(c, true);
	if (!ret)
		ret = x710_controller_facts(c, &facts);
	if (!ret) {
		c->tx.state = X710_PPS_NEGOTIATING;
		ret = x710_controller_pps(c, mv, ma);
	}
	if (!ret)
		ret = x710_controller_facts(c, &facts);
	if (!ret)
		c->pps_observed = true;
	return ret;
}

static void x710_controller_work(struct work_struct *work)
{
	struct x710_native_controller *c = &x710_controller;
	struct x710_controller_result result = {};
	enum x710_controller_command command;
	unsigned int mv, ma;
	int ret;

	mutex_lock(&x710_controller_lock);
	command = x710_controller_command;
	mv = x710_controller_mv;
	ma = x710_controller_ma;
	memset(c, 0, sizeof(*c));
	c->generation = x710_controller_generation;
	c->tx.state = X710_SWITCHING;
	result.started_ms = x710_controller_now(NULL);
	mutex_unlock(&x710_controller_lock);
	if (!x710_controller_current(c, c->generation)) {
		ret = -ECANCELED;
	} else {
		switch (command) {
		case X710_CONTROLLER_OFF_ROUNDTRIP:
			ret = x710_controller_roundtrip(c, mv, ma);
			break;
		case X710_CONTROLLER_START:
			/* Core and hardware activation gates are both default-inactive. */
			ret = x710_charge_start(&c->tx, &c->facts, &x710_controller_ops, c);
			break;
		case X710_CONTROLLER_REFRESH:
			ret = x710_charge_refresh(&c->tx, &x710_controller_ops, c);
			break;
		case X710_CONTROLLER_RETARGET:
			ret = x710_charge_retarget(&c->tx, &x710_controller_ops, c);
			break;
		case X710_CONTROLLER_MONITOR:
			ret = x710_charge_monitor(&c->tx, &x710_controller_ops, c);
			break;
		default:
			ret = x710_charge_stop(&c->tx, &x710_controller_ops, c);
			break;
		}
	}
	if (!ret && !x710_controller_current(c, c->generation))
		ret = -ECANCELED;
	c->tx.state = (c->lease || c->hardware_owned) ? X710_DIRECT_STOPPING : X710_SWITCHING;
	c->cleanup_error = x710_controller_cleanup(c);
	if (!ret)
		ret = c->cleanup_error;
	result.generation = c->generation;
	result.completed_ms = x710_controller_now(NULL);
	result.instance = c->fixed.instance;
	result.source_generation = c->fixed.source_generation;
	result.lease = c->lease;
	result.hardware_owner = c->hardware_owner;
	result.error = ret;
	result.cleanup_error = c->cleanup_error;
	result.hardware_quiesced = c->hardware_quiesced;
	result.pps_observed = c->pps_observed;
	result.fixed_observed = c->fixed_observed;
	result.switching_released = c->switching_released;
	result.unresolved = c->lease || c->hardware_owned || c->cleanup_error;
	result.state = result.unresolved ? X710_CHARGE_FAULT : X710_SWITCHING;
	mutex_lock(&x710_controller_lock);
	result.cancelled = x710_controller_cancelled || x710_controller_quiescing;
	if (!result.error && result.cancelled)
		result.error = -ECANCELED;
	x710_controller_unresolved = result.unresolved;
	x710_controller_result = result;
	x710_controller_inflight = false;
	complete_all(&x710_controller_done);
	mutex_unlock(&x710_controller_lock);
}

static DECLARE_WORK(x710_controller_job, x710_controller_work);

int x710_charge_controller_status(struct x710_controller_result *out)
{
	if (!out)
		return -EINVAL;
	mutex_lock(&x710_controller_lock);
	*out = x710_controller_result;
	out->inflight = x710_controller_inflight;
	out->cancelled = x710_controller_cancelled || x710_controller_quiescing;
	out->unresolved = x710_controller_unresolved;
	mutex_unlock(&x710_controller_lock);
	return 0;
}
EXPORT_SYMBOL_GPL(x710_charge_controller_status);

void x710_charge_controller_cancel(void)
{
	mutex_lock(&x710_controller_lock);
	x710_controller_cancelled = true;
	mutex_unlock(&x710_controller_lock);
}
EXPORT_SYMBOL_GPL(x710_charge_controller_cancel);

int x710_charge_controller_request(enum x710_controller_command command,
				   unsigned int mv, unsigned int ma,
				   struct x710_controller_result *out)
{
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	if (command < X710_CONTROLLER_OFF_ROUNDTRIP || command > X710_CONTROLLER_STOP)
		return -EINVAL;
	if (command == X710_CONTROLLER_OFF_ROUNDTRIP &&
	    (mv < SM5714_PPS_MIN_MV || mv > SM5714_PPS_MAX_MV || mv % 20 ||
	     ma < 100 || ma > SM5714_PPS_MAX_MA || ma % 50))
		return -ERANGE;
	if (!mutex_trylock(&x710_controller_request_lock))
		return -EBUSY;
	mutex_lock(&x710_controller_lock);
	if (x710_controller_quiescing || !x710_controller_wq || x710_controller_unresolved) {
		ret = -ESHUTDOWN;
		goto unlock;
	}
	if (x710_controller_inflight) {
		ret = -EBUSY;
		goto unlock;
	}
	if (x710_controller_generation == U64_MAX) {
		ret = -EOVERFLOW;
		goto unlock;
	}
	x710_controller_generation++;
	x710_controller_command = command;
	x710_controller_mv = mv;
	x710_controller_ma = ma;
	x710_controller_cancelled = false;
	x710_controller_result = (struct x710_controller_result) {};
	x710_controller_inflight = true;
	reinit_completion(&x710_controller_done);
	if (!queue_work(x710_controller_wq, &x710_controller_job)) {
		x710_controller_inflight = false;
		ret = -EBUSY;
		goto unlock;
	}
	mutex_unlock(&x710_controller_lock);
	/* Waiter bound only. TCPM may still drain; cancellation cannot grant retry. */
	ret = wait_for_completion_timeout(&x710_controller_done,
					  msecs_to_jiffies(1000)) ? 0 : -ETIMEDOUT;
	mutex_lock(&x710_controller_lock);
	if (ret) {
		x710_controller_cancelled = true;
	} else {
		*out = x710_controller_result;
		ret = out->error;
	}
unlock:
	mutex_unlock(&x710_controller_lock);
	mutex_unlock(&x710_controller_request_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(x710_charge_controller_request);

static int x710_controller_pm(struct notifier_block *nb, unsigned long action, void *unused)
{
	int ret;

	switch (action) {
	case PM_SUSPEND_PREPARE:
	case PM_HIBERNATION_PREPARE:
	case PM_RESTORE_PREPARE:
		mutex_lock(&x710_controller_lock);
		x710_controller_quiescing = true;
		x710_controller_cancelled = true;
		mutex_unlock(&x710_controller_lock);
		/* Flush, not cancel: a queued operation must publish and drain cleanup. */
		flush_work(&x710_controller_job);
		mutex_lock(&x710_controller_lock);
		ret = x710_controller_unresolved ? NOTIFY_BAD : NOTIFY_OK;
		mutex_unlock(&x710_controller_lock);
		return ret;
	case PM_POST_SUSPEND:
	case PM_POST_HIBERNATION:
	case PM_POST_RESTORE:
		mutex_lock(&x710_controller_lock);
		x710_controller_quiescing = false;
		mutex_unlock(&x710_controller_lock);
		return NOTIFY_OK;
	default:
		return NOTIFY_DONE;
	}
}

/* Drain before ordinary observer/session PM closes the suppliers. */
static struct notifier_block x710_controller_notifier = {
	.notifier_call = x710_controller_pm, .priority = 100,
};

static int __init x710_controller_init(void)
{
	int ret;

	x710_controller_wq = alloc_ordered_workqueue("x710-charge-controller", WQ_MEM_RECLAIM);
	if (!x710_controller_wq)
		return -ENOMEM;
	ret = register_pm_notifier(&x710_controller_notifier);
	if (ret) {
		destroy_workqueue(x710_controller_wq);
		x710_controller_wq = NULL;
		return ret;
	}
	mutex_lock(&x710_controller_lock);
	x710_controller_quiescing = false;
	mutex_unlock(&x710_controller_lock);
	return 0;
}
device_initcall(x710_controller_init);
MODULE_DESCRIPTION("X710 native charging coordinator, direct activation unavailable");
MODULE_LICENSE("GPL");
