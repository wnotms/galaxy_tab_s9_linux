// SPDX-License-Identifier: GPL-2.0-only
/* Actual owned TCPM consumer: one explicit pump-OFF roundtrip, no pump ON. */
#include <linux/atomic.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/power_supply.h>
#include <linux/string.h>
#include <linux/suspend.h>
#include <linux/usb/pd.h>

#include "sm5440-hw.h"
#include "sm5714-pd-policy.h"
#include "x710-pd-session.h"

/* Consumer serialization only; providers never acquire this mutex. */
static DEFINE_MUTEX(x710_session_lock);
static atomic_t x710_session_quiescing = ATOMIC_INIT(1);
static bool x710_session_unresolved;

static u64 x710_session_now(void)
{
	return ktime_to_ms(ktime_get_boottime());
}

static int x710_session_pack(u64 lease)
{
	struct sm5714_pack_snapshot sample = {};
	u64 now;
	int ret = sm5714_battery_read_pack(lease, &sample);

	if (ret)
		return ret;
	now = x710_session_now();
	if (!sample.instance || !sample.state_generation || sample.switching_lease != lease ||
	    !sample.started_ms || sample.completed_ms < sample.started_ms ||
	    now < sample.completed_ms || now - sample.started_ms > 500)
		return -ESTALE;
	/* Existing conservative bring-up window, not vendor maximum ratings. */
	if (!sample.attached || !sample.typec_owned || !sample.typec_charge ||
	    !sample.battery_present || sample.health != POWER_SUPPLY_HEALTH_GOOD ||
	    sample.capacity < 5 || sample.capacity >= 80 || sample.voltage_uv < 3500000 ||
	    sample.voltage_uv >= 4300000 || sample.pack_decic < 200 || sample.pack_decic >= 380)
		return -EPERM;
	return 0;
}

static int x710_session_measure(unsigned int mv, struct sm5714_fixed_proof *proof)
{
	struct sm5440_passive_measurement sample = {};
	u64 now;
	int ret;

	memset(proof, 0, sizeof(*proof));
	ret = sm5440_passive_request_fresh(&sample);
	if (ret)
		return ret;
	now = x710_session_now();
	/* The real fresh API verifies OFF before and after conversion. Preserve
	 * oldest acquisition time; never substitute logical TCPM voltage/cache.
	 */
	if (!sample.observed_ms || now < sample.observed_ms ||
	    now - sample.observed_ms > SM5440_FRESH_REQUEST_MS)
		return -ESTALE;
	if (!sample.online || sample.ibus_ua || sample.vbat_uv < 3500000 ||
	    sample.vbat_uv >= 4300000 || sample.die_decic < 0 ||
	    sample.die_decic >= 550 || sample.vbus_uv < 4500000 ||
	    sample.vbus_uv > SM5714_PPS_MAX_MV * 1000U ||
	    (mv && (sample.vbus_uv + 100000ULL < mv * 1000ULL ||
		    sample.vbus_uv > mv * 1000ULL + 100000)))
		return -ERANGE;
	proof->observed_ms = sample.observed_ms;
	proof->vbus_uv = sample.vbus_uv;
	proof->ibus_ua = sample.ibus_ua;
	proof->pump_off = true;
	return 0;
}

static bool x710_session_target(const struct sm5714_pd_snapshot *source,
				unsigned int mv, unsigned int ma)
{
	unsigned int i;

	if (source->nr_source_pdos > SM5714_SOURCE_PDO_MAX)
		return false;
	for (i = 0; i < source->nr_source_pdos; i++) {
		u32 rdo = RDO_PROG(i + 1, mv, ma, RDO_USB_COMM | RDO_NO_SUSPEND);

		if (sm5714_validate_pps_request(source->source_pdos[i], rdo))
			return true;
	}
	return false;
}

static int x710_session_same_fixed(const struct sm5714_pd_snapshot *before)
{
	struct sm5714_pd_snapshot after = {};
	int ret = sm5714_pd_read_snapshot(&after);

	if (!ret && (after.instance != before->instance ||
		     after.source_generation != before->source_generation ||
		     after.budget_generation != before->budget_generation))
		ret = -ESTALE;
	return ret;
}

/* Cleanup may run after PM cancellation; it cannot enter/tune PPS. Exact
 * transport identity and lease gates still apply, including atomic release.
 */
static int x710_session_cleanup(struct x710_pd_session_result *result, bool pps_failed)
{
	struct sm5714_pd_snapshot fixed = {};
	struct sm5714_fixed_proof proof = {};
	int ret;

	/* The owned API already attempts fixed cleanup on a mutating failure.
	 * Do not retry its failed protocol restoration. A read-only fixed
	 * snapshot must first prove it succeeded; otherwise retain inhibition.
	 */
	if (pps_failed) {
		ret = sm5714_pd_read_snapshot(&fixed);
		if (ret)
			return ret;
		if (fixed.instance != result->instance ||
		    fixed.source_generation != result->source_generation)
			return -ESTALE;
	}
	/* Unknown pump state must not authorize a voltage change. */
	ret = x710_session_measure(0, &proof);
	if (!ret)
		ret = sm5714_pd_restore_fixed(result->instance, result->source_generation,
					      result->lease, &fixed);
	if (ret)
		return ret;
	result->fixed_observed = true;
	if (fixed.budget_mv != 9000)
		return -ERANGE;
	ret = x710_session_pack(result->lease);
	if (!ret)
		ret = x710_session_measure(fixed.budget_mv, &proof);
	if (!ret)
		ret = sm5714_pd_release_fixed(result->instance, result->source_generation,
					      result->lease, &proof);
	if (!ret)
		result->switching_released = true;
	return ret;
}

int x710_pd_off_roundtrip(unsigned int mv, unsigned int ma,
			  struct x710_pd_session_result *out)
{
	struct x710_pd_session_result result = {};
	struct sm5714_pd_snapshot fixed = {}, pps = {};
	struct sm5714_fixed_proof proof = {};
	bool pps_failed = false;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	if (mv < SM5714_PPS_MIN_MV || mv > SM5714_PPS_MAX_MV || mv % 20 ||
	    ma < 100 || ma > SM5714_PPS_MAX_MA || ma % 50)
		return -ERANGE;
	if (!mutex_trylock(&x710_session_lock))
		return -EBUSY;
	result.started_ms = x710_session_now();
	if (atomic_read(&x710_session_quiescing) || x710_session_unresolved) {
		ret = -ESHUTDOWN;
		goto done;
	}
	ret = sm5714_pd_read_snapshot(&fixed);
	if (ret)
		goto done;
	result.instance = fixed.instance;
	result.source_generation = fixed.source_generation;
	if (fixed.budget_mv != 9000 || !x710_session_target(&fixed, mv, ma)) {
		ret = -EPERM;
		goto done;
	}
	ret = x710_session_pack(0);
	if (!ret)
		ret = x710_session_measure(9000, &proof);
	if (!ret)
		ret = x710_session_same_fixed(&fixed);
	if (!ret && atomic_read(&x710_session_quiescing))
		ret = -ECANCELED;
	if (ret)
		goto done;
	ret = sm5714_battery_switching_acquire(&result.lease);
	if (!ret)
		ret = x710_session_pack(result.lease);
	if (!ret)
		ret = x710_session_measure(9000, &proof);
	if (!ret)
		ret = x710_session_same_fixed(&fixed);
	if (!ret && atomic_read(&x710_session_quiescing))
		ret = -ECANCELED;
	if (!ret) {
		ret = sm5714_pd_request_pps(result.instance, result.source_generation,
					    result.lease, mv, ma, &pps);
		pps_failed = !!ret;
	}
	if (!ret && (pps.instance != result.instance ||
		     pps.source_generation != result.source_generation ||
		     !pps.pps_contract || pps.online != 2 ||
		     pps.budget_mv != mv || pps.budget_ma != ma))
		ret = -ESTALE;
	if (!ret && atomic_read(&x710_session_quiescing))
		ret = -ECANCELED;
	if (!ret)
		ret = x710_session_pack(result.lease);
	if (!ret)
		ret = x710_session_measure(mv, &proof);
	if (!ret)
		result.pps_observed = true;
	if (result.lease) {
		result.cleanup_error = x710_session_cleanup(&result, pps_failed);
		x710_session_unresolved = !result.switching_released;
		if (!ret)
			ret = result.cleanup_error;
	}
done:
	result.error = ret;
	result.completed_ms = x710_session_now();
	*out = result;
	mutex_unlock(&x710_session_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(x710_pd_off_roundtrip);

static int x710_session_pm(struct notifier_block *nb, unsigned long action, void *unused)
{
	int ret;

	switch (action) {
	case PM_SUSPEND_PREPARE:
	case PM_HIBERNATION_PREPARE:
	case PM_RESTORE_PREPARE:
		atomic_set(&x710_session_quiescing, 1);
		mutex_lock(&x710_session_lock);
		ret = x710_session_unresolved ? NOTIFY_BAD : NOTIFY_OK;
		mutex_unlock(&x710_session_lock);
		return ret;
	case PM_POST_SUSPEND:
	case PM_POST_HIBERNATION:
	case PM_POST_RESTORE:
		atomic_set(&x710_session_quiescing, 0);
		return NOTIFY_OK;
	default:
		return NOTIFY_DONE;
	}
}

static struct notifier_block x710_session_notifier = { .notifier_call = x710_session_pm };

static int __init x710_session_init(void)
{
	int ret = register_pm_notifier(&x710_session_notifier);

	if (!ret)
		atomic_set(&x710_session_quiescing, 0);
	return ret;
}
module_init(x710_session_init);
MODULE_DESCRIPTION("X710 explicitly invoked owned PPS roundtrip; pump OFF only");
MODULE_LICENSE("GPL");
