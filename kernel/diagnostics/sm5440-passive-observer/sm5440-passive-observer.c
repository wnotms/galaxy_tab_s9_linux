// SPDX-License-Identifier: GPL-2.0-only
/* Test291: one OFF-mode diagnostic observation, never a charging/fresh grant.
 * Uses Test290 API. No I2C, PPS, pumpON, retry or automatic activation.
 * See docs/SM5440_PASSIVE_OBSERVER.md; retain owned task lifetime from Test276.
 */
#include <linux/debugfs.h>
#include <linux/err.h>
#include <linux/errno.h>
#include <linux/kthread.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/sched/task.h>
#include <linux/seq_file.h>

#include "sm5440-hw.h"

enum observer_state {
	OBSERVER_RUNNING,
	OBSERVER_COMPLETED,
	OBSERVER_STOPPED,
	OBSERVER_CANCELLED,
};

struct observer_row {
	u64 requested_ms, returned_ms;
	int provider_status, status;
	struct sm5440_passive_observation raw;
};

static DEFINE_MUTEX(result_lock);
static struct observer_row row;
static unsigned int nr_rows;
static enum observer_state state = OBSERVER_RUNNING;
static struct task_struct *observer_task;
static struct dentry *observer_root;

/* Validate diagnostic provenance, not the separate legacy100ms freshness. */
static int observer_check(u64 start, u64 end, int provider_status,
			  const struct sm5440_passive_observation *raw)
{
	const struct sm5440_passive_measurement *m;

	if (provider_status)
		return provider_status;
	if (!raw)
		return -EINVAL;
	if (!start || end < start || end - start > SM5440_PASSIVE_OBSERVATION_MS)
		return -ETIMEDOUT;
	m = &raw->measurement;
	if (!m->observed_ms || !raw->acquisition_seq ||
	    raw->request_ms < start || m->observed_ms < raw->request_ms ||
	    raw->completed_ms < m->observed_ms ||
	    raw->returned_ms < raw->completed_ms || raw->returned_ms > end ||
	    raw->oldest_age_ms != raw->returned_ms - m->observed_ms)
		return -ESTALE;
	if (!m->online)
		return -ENODATA;
	if (m->ibus_ua)
		return -EBUSY;
	if (m->vbus_uv < 4500000 || m->vbus_uv > 9500000 ||
	    m->vbat_uv < 3500000 || m->vbat_uv >= 4300000 ||
	    m->die_decic < 225 || m->die_decic >= 420)
		return -ERANGE;
	return 0;
}

static int observer_thread(void *unused)
{
	struct observer_row result = {};

	if (kthread_should_stop()) {
		mutex_lock(&result_lock);
		state = OBSERVER_CANCELLED;
		mutex_unlock(&result_lock);
		return 0;
	}
	result.requested_ms = ktime_to_ms(ktime_get_boottime());
	/* No result/charger/TCPM lock held over the external sleepable request. */
	result.provider_status = sm5440_passive_observe(&result.raw);
	result.returned_ms = ktime_to_ms(ktime_get_boottime());
	result.status = observer_check(result.requested_ms, result.returned_ms,
				       result.provider_status, &result.raw);
	mutex_lock(&result_lock);
	row = result;
	nr_rows = 1;
	state = result.status ? OBSERVER_STOPPED : OBSERVER_COMPLETED;
	mutex_unlock(&result_lock);
	return 0;
}

static int observer_result_show(struct seq_file *s, void *unused)
{
	const struct sm5440_passive_observation *o = &row.raw;
	const struct sm5440_passive_measurement *m = &o->measurement;

	/* Cache only: reading evidence cannot start a conversion or retry. */
	mutex_lock(&result_lock);
	seq_puts(s, "format=sm5440-passive-observer-v1\n");
	seq_printf(s, "state=%u\ncount=%u\nmaximum_calls=1\ncollection_budget_ms=%u\n",
		   state, nr_rows, SM5440_PASSIVE_OBSERVATION_MS);
	seq_puts(s, "PPS_authorized=0\npump_ON_authorized=0\nlegacy_fresh_authorized=0\nindependently_calibrated=0\n");
	if (nr_rows)
		seq_printf(s, "row=1 request_ms=%llu return_ms=%llu provider_status=%d status=%d diagnostic_valid=%u provider_request_ms=%llu acquisition_ms=%llu completed_ms=%llu provider_return_ms=%llu oldest_age_ms=%llu acquisition_seq=%llu request_epoch=%lu raw_vbus_uv=%u raw_vbat_uv=%u raw_ibus_ua=%u raw_die_decic=%d raw_online=%u\n",
			   row.requested_ms, row.returned_ms, row.provider_status,
			   row.status, !row.status, o->request_ms, m->observed_ms,
			   o->completed_ms, o->returned_ms, o->oldest_age_ms,
			   o->acquisition_seq, o->request_epoch, m->vbus_uv,
			   m->vbat_uv, m->ibus_ua, m->die_decic, m->online);
	mutex_unlock(&result_lock);
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(observer_result);

static int __init observer_init(void)
{
	struct dentry *file;
	int ret;

	observer_root = debugfs_create_dir("sm5440-passive-observer", NULL);
	if (IS_ERR(observer_root))
		return PTR_ERR(observer_root);
	if (!observer_root)
		return -ENOMEM;
	file = debugfs_create_file("result", 0400, observer_root, NULL,
				   &observer_result_fops);
	if (IS_ERR_OR_NULL(file)) {
		ret = IS_ERR(file) ? PTR_ERR(file) : -ENOMEM;
		goto remove;
	}
	/* The bounded worker can return before unload. Pinned
	 * kthread.c requires caller ownership when stopping an exited thread.
	 * Create parked: take the reference BEFORE the worker can run/return.
	 */
	observer_task = kthread_create(observer_thread, NULL, "sm5440-passive");
	if (IS_ERR(observer_task)) {
		ret = PTR_ERR(observer_task);
		goto remove;
	}
	get_task_struct(observer_task);
	wake_up_process(observer_task);
	return 0;
remove:
	debugfs_remove(observer_root);
	return ret;
}

static void __exit observer_exit(void)
{
	/* Join before removing cached results; no lock held over the drain. */
	kthread_stop_put(observer_task);
	debugfs_remove(observer_root);
}
module_init(observer_init);
module_exit(observer_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("One passive SM5440 diagnostic observation; no charging/fresh grant");
