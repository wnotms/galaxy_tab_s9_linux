// SPDX-License-Identifier: GPL-2.0-only
/* Actual native acquisition/lifecycle worker; direct activation unavailable. */
#include <linux/completion.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/power_supply.h>
#include <linux/string.h>
#include <linux/suspend.h>
#include <linux/workqueue.h>

#include "x710-charge-observer.h"
#include "x710-charging-policy.h"

static DEFINE_MUTEX(x710_observer_request_lock);
static DEFINE_MUTEX(x710_observer_lock);
static DECLARE_COMPLETION(x710_observer_done);
static struct workqueue_struct *x710_observer_wq;
static struct x710_observer_owner x710_observer_owner;
static struct x710_charge_observation x710_observer_result;
static u64 x710_observer_generation, x710_observer_job_generation;
static bool x710_observer_quiescing = true, x710_observer_inflight;
static int x710_observer_error = -ESHUTDOWN;

static u64 x710_observer_now(void)
{
	return ktime_to_ms(ktime_get_boottime());
}

static bool x710_observer_current(u64 generation)
{
	bool valid;

	mutex_lock(&x710_observer_lock);
	valid = !x710_observer_quiescing &&
		x710_observer_generation == generation;
	mutex_unlock(&x710_observer_lock);
	return valid;
}

static bool x710_observer_bracket(u64 start, u64 end, u64 now)
{
	return start && start <= end && end <= now &&
		now - start <= X710_FACTS_MAX_AGE_MS;
}

static int x710_observer_source(const struct x710_observer_owner *owner,
				struct sm5714_pd_snapshot *out)
{
	if (owner->lease)
		return sm5714_pd_read_owned_snapshot(owner->instance,
			owner->source_generation, owner->lease, out);
	return sm5714_pd_read_snapshot(out);
}

static bool x710_observer_same_source(const struct sm5714_pd_snapshot *a,
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
		a->pps_contract == b->pps_contract &&
		a->charge_requested && b->charge_requested;
}

static bool x710_observer_same_pack(const struct sm5714_pack_snapshot *a,
				    const struct sm5714_pack_snapshot *b)
{
	return a->instance && a->state_generation && a->instance == b->instance &&
		a->state_generation == b->state_generation &&
		a->switching_lease == b->switching_lease &&
		a->typec_mv == b->typec_mv && a->typec_ma == b->typec_ma &&
		a->typec_owned == b->typec_owned && a->typec_charge == b->typec_charge &&
		a->pps_contract == b->pps_contract && a->thermal_normal == b->thermal_normal;
}

static int x710_observer_source_valid(const struct sm5714_pd_snapshot *source,
				     const struct x710_observer_owner *owner)
{
	if (!source->instance || !source->source_generation || !source->budget_generation ||
	    source->nr_source_pdos > SM5714_SOURCE_PDO_MAX || !source->charge_requested ||
	    !source->budget_ma)
		return -EPERM;
	if (owner->lease) {
		if (source->instance != owner->instance ||
		    source->source_generation != owner->source_generation ||
		    !source->pps_contract || source->online != 2 || !source->nr_source_pdos ||
		    (source->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS &&
		     source->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS) ||
		    source->budget_mv < SM5714_PPS_MIN_MV ||
		    source->budget_mv > SM5714_PPS_MAX_MV || source->budget_mv % 20 ||
		    source->budget_ma > SM5714_PPS_MAX_MA || source->budget_ma % 50)
			return -EPERM;
	} else if (source->pps_contract || source->online != 1 ||
		   (source->budget_mv != 5000 && source->budget_mv != 9000) ||
		   source->budget_ma > (source->budget_mv == 5000 ?
			SM5714_FIXED_5V_MA : SM5714_FIXED_9V_MA)) {
		return -EPERM;
	}
	if (source->voltage_uv != (int)(source->budget_mv * 1000U) ||
	    source->current_ua != (int)(source->budget_ma * 1000U))
		return -ERANGE;
	return 0;
}

static int x710_observer_pack_valid(const struct sm5714_pack_snapshot *pack,
				   const struct sm5714_pd_snapshot *source,
				   const struct x710_observer_owner *owner)
{
	if (pack->switching_lease != owner->lease || !pack->battery_present ||
	    !pack->attached || !pack->typec_owned || !pack->typec_charge ||
	    !pack->thermal_normal || pack->health != POWER_SUPPLY_HEALTH_GOOD ||
	    pack->capacity < 5 || pack->capacity >= 80 || pack->voltage_uv < 3500000 ||
	    pack->voltage_uv >= 4300000 || pack->pack_decic < 200 || pack->pack_decic >= 380 ||
	    pack->typec_mv != source->budget_mv || pack->typec_ma != source->budget_ma ||
	    pack->pps_contract != source->pps_contract)
		return -EPERM;
	return 0;
}

/* No publication/core mutex across any native supplier operation. */
static int x710_observer_collect(const struct x710_observer_owner *owner,
				 u64 generation, struct x710_charge_observation *out)
{
	struct x710_charge_observation sample = {};
	struct sm5714_pd_snapshot source_after = {};
	struct sm5714_pack_snapshot pack_before = {};
	u64 now;
	int ret;

	memset(out, 0, sizeof(*out));
	sample.generation = generation;
	sample.started_ms = x710_observer_now();
	if (!x710_observer_current(generation))
		return -ECANCELED;
	ret = x710_observer_source(owner, &sample.source);
	if (!ret)
		ret = x710_observer_source_valid(&sample.source, owner);
	if (!ret)
		ret = sm5714_battery_read_pack(owner->lease, &pack_before);
	if (!ret)
		ret = x710_observer_pack_valid(&pack_before, &sample.source, owner);
	if (!ret && !x710_observer_current(generation))
		ret = -ECANCELED;
	if (!ret)
		ret = sm5440_passive_request_fresh(&sample.physical);
	if (!ret && !x710_observer_current(generation))
		ret = -ECANCELED;
	if (!ret)
		ret = sm5714_battery_read_pack(owner->lease, &sample.pack);
	if (!ret)
		ret = x710_observer_source(owner, &source_after);
	if (ret)
		return ret;
	now = x710_observer_now();
	if (!x710_observer_current(generation) ||
	    !x710_observer_same_source(&sample.source, &source_after) ||
	    !x710_observer_same_pack(&pack_before, &sample.pack))
		return -ESTALE;
	if (!x710_observer_bracket(sample.started_ms, now, now) ||
	    !x710_observer_bracket(sample.source.started_ms, sample.source.completed_ms, now) ||
	    !x710_observer_bracket(source_after.started_ms, source_after.completed_ms, now) ||
	    !x710_observer_bracket(pack_before.started_ms, pack_before.completed_ms, now) ||
	    !x710_observer_bracket(sample.pack.started_ms, sample.pack.completed_ms, now) ||
	    !sample.physical.observed_ms || sample.physical.observed_ms > now ||
	    now - sample.physical.observed_ms > SM5440_FRESH_REQUEST_MS)
		return -ESTALE;
	ret = x710_observer_pack_valid(&sample.pack, &source_after, owner);
	if (ret)
		return ret;
	/* The provider itself verifies mode-OFF/faults; do not invent pump state
	 * from logical source properties. Recheck physical bounds and zero IBUS.
	 */
	if (!sample.physical.online || sample.physical.ibus_ua ||
	    sample.physical.vbat_uv < 3500000 || sample.physical.vbat_uv >= 4300000 ||
	    sample.physical.die_decic < 0 || sample.physical.die_decic >= 420 ||
	    sample.physical.vbus_uv + 100000ULL < sample.source.budget_mv * 1000ULL ||
	    sample.physical.vbus_uv > sample.source.budget_mv * 1000ULL + 100000)
		return -ERANGE;
	sample.oldest_ms = min(sample.source.started_ms, pack_before.started_ms);
	sample.oldest_ms = min(sample.oldest_ms, sample.physical.observed_ms);
	sample.oldest_ms = min(sample.oldest_ms, sample.pack.started_ms);
	sample.oldest_ms = min(sample.oldest_ms, source_after.started_ms);
	sample.completed_ms = now;
	*out = sample;
	return 0;
}

static void x710_observer_work(struct work_struct *work)
{
	struct x710_charge_observation sample = {};
	struct x710_observer_owner owner;
	u64 generation;
	int ret;

	mutex_lock(&x710_observer_lock);
	owner = x710_observer_owner;
	generation = x710_observer_job_generation;
	mutex_unlock(&x710_observer_lock);
	ret = x710_observer_collect(&owner, generation, &sample);
	mutex_lock(&x710_observer_lock);
	if (x710_observer_quiescing || generation != x710_observer_generation)
		ret = -ECANCELED;
	x710_observer_error = ret;
	x710_observer_result = ret ? (struct x710_charge_observation){} : sample;
	x710_observer_inflight = false;
	complete_all(&x710_observer_done);
	mutex_unlock(&x710_observer_lock);
}
static DECLARE_WORK(x710_observer_job, x710_observer_work);

int x710_charge_request_observation(const struct x710_observer_owner *owner,
				    struct x710_charge_observation *out)
{
	u64 generation, now;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	if (!owner || (!!owner->instance != !!owner->lease) ||
	    (!!owner->source_generation != !!owner->lease))
		return -EINVAL;
	if (!mutex_trylock(&x710_observer_request_lock))
		return -EBUSY;
	mutex_lock(&x710_observer_lock);
	if (x710_observer_quiescing || !x710_observer_wq) {
		ret = -ESHUTDOWN;
		goto unlock;
	}
	if (x710_observer_inflight) {
		ret = -EBUSY;
		goto unlock;
	}
	if (x710_observer_generation == U64_MAX) {
		x710_observer_quiescing = true;
		ret = -EOVERFLOW;
		goto unlock;
	}
	generation = ++x710_observer_generation;
	x710_observer_job_generation = generation;
	x710_observer_owner = *owner;
	x710_observer_result = (struct x710_charge_observation){};
	x710_observer_error = -EINPROGRESS;
	x710_observer_inflight = true;
	reinit_completion(&x710_observer_done);
	if (!queue_work(x710_observer_wq, &x710_observer_job)) {
		x710_observer_inflight = false;
		ret = -EBUSY;
		goto unlock;
	}
	mutex_unlock(&x710_observer_lock);
	ret = wait_for_completion_timeout(&x710_observer_done,
					  msecs_to_jiffies(X710_FACTS_MAX_AGE_MS)) ? 0 : -ETIMEDOUT;
	mutex_lock(&x710_observer_lock);
	if (x710_observer_quiescing || generation != x710_observer_generation)
		ret = -ECANCELED;
	if (!ret)
		ret = x710_observer_error;
	now = x710_observer_now();
	if (!ret && (x710_observer_inflight || !x710_observer_result.oldest_ms ||
	    now < x710_observer_result.completed_ms ||
	    now - x710_observer_result.oldest_ms > X710_FACTS_MAX_AGE_MS ||
	    now < x710_observer_result.physical.observed_ms ||
	    now - x710_observer_result.physical.observed_ms > SM5440_FRESH_REQUEST_MS))
		ret = -ESTALE;
	if (!ret)
		*out = x710_observer_result;
	else {
		/* A timed-out worker cannot publish into a later connection/request.
		 * Keep inflight set until it drains; no second converter request.
		 */
		if (generation == x710_observer_generation && generation != U64_MAX)
			x710_observer_generation++;
		x710_observer_result = (struct x710_charge_observation){};
	}
unlock:
	mutex_unlock(&x710_observer_lock);
	mutex_unlock(&x710_observer_request_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(x710_charge_request_observation);

static int x710_observer_pm(struct notifier_block *nb, unsigned long action, void *unused)
{
	switch (action) {
	case PM_SUSPEND_PREPARE:
	case PM_HIBERNATION_PREPARE:
	case PM_RESTORE_PREPARE:
		mutex_lock(&x710_observer_lock);
		x710_observer_quiescing = true;
		x710_observer_result = (struct x710_charge_observation){};
		mutex_unlock(&x710_observer_lock);
		cancel_work_sync(&x710_observer_job);
		mutex_lock(&x710_observer_lock);
		x710_observer_error = -ESHUTDOWN;
		x710_observer_inflight = false;
		complete_all(&x710_observer_done);
		mutex_unlock(&x710_observer_lock);
		return NOTIFY_OK;
	case PM_POST_SUSPEND:
	case PM_POST_HIBERNATION:
	case PM_POST_RESTORE:
		mutex_lock(&x710_observer_lock);
		x710_observer_quiescing = false;
		mutex_unlock(&x710_observer_lock);
		return NOTIFY_OK;
	default:
		return NOTIFY_DONE;
	}
}
static struct notifier_block x710_observer_notifier = { .notifier_call = x710_observer_pm };

static int __init x710_observer_init(void)
{
	int ret;

	x710_observer_wq = alloc_ordered_workqueue("x710-charge-observer", WQ_MEM_RECLAIM);
	if (!x710_observer_wq)
		return -ENOMEM;
	ret = register_pm_notifier(&x710_observer_notifier);
	if (ret) {
		destroy_workqueue(x710_observer_wq);
		x710_observer_wq = NULL;
		return ret;
	}
	mutex_lock(&x710_observer_lock);
	x710_observer_quiescing = false;
	mutex_unlock(&x710_observer_lock);
	return 0;
}
device_initcall(x710_observer_init);

MODULE_DESCRIPTION("X710 native OFF charging observation worker; no activation");
MODULE_LICENSE("GPL");
