// SPDX-License-Identifier: GPL-2.0-only
/* Test274 passive delivery diagnosis; no ON/PPS/I2C/charging policy operations.
 * Provider: Test272 sm5440_passive_request_fresh(), genuine OFF-mode conversion.
 * See docs/SM5440_FRESH_OBSERVER.md. Explicit load only; first error stops.
 */
#include <linux/debugfs.h>
#include <linux/delay.h>
#include <linux/err.h>
#include <linux/errno.h>
#include <linux/kthread.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/seq_file.h>

#include "sm5440-hw.h"

#define OBSERVER_CALLS 8U
#define OBSERVER_INTERVAL_MS 1000U

enum observer_state {
	OBSERVER_RUNNING,
	OBSERVER_COMPLETED,
	OBSERVER_STOPPED,
	OBSERVER_CANCELLED,
};

struct observer_row {
	u64 requested_ms, returned_ms;
	int provider_status, status;
	struct sm5440_passive_measurement raw;
};

static DEFINE_MUTEX(result_lock);
static struct observer_row rows[OBSERVER_CALLS];
static unsigned int nr_rows;
static enum observer_state state = OBSERVER_RUNNING;
static struct task_struct *observer_task;
static struct dentry *observer_root;

/* Software delivery evidence only, never an arming/protection certificate.
 * Preserve raw failed facts in rows for diagnosis; status!=0 means unusable.
 */
static int observer_check(u64 start, u64 end, int provider_status,
			  const struct sm5440_passive_measurement *raw)
{
	if (provider_status)
		return provider_status;
	if (!raw)
		return -EINVAL;
	if (end < start || end - start > SM5440_FRESH_REQUEST_MS)
		return -ETIMEDOUT;
	if (!raw->observed_ms || raw->observed_ms < start ||
	    raw->observed_ms > end || end - raw->observed_ms > SM5440_FRESH_REQUEST_MS)
		return -ESTALE;
	if (!raw->online)
		return -ENODATA;
	if (raw->ibus_ua)
		return -EBUSY;
	if (raw->vbus_uv < 4500000 || raw->vbus_uv > 9500000 ||
	    raw->vbat_uv < 3500000 || raw->vbat_uv >= 4300000 ||
	    raw->die_decic < 225 || raw->die_decic >= 420)
		return -ERANGE;
	return 0;
}

static int observer_thread(void *unused)
{
	unsigned int i;

	for (i = 0; i < OBSERVER_CALLS; i++) {
		struct observer_row row = {};

		if (kthread_should_stop())
			goto cancelled;
		row.requested_ms = ktime_to_ms(ktime_get_boottime());
		/* No result/provider/charger/TCPM mutex held across this sleepable API. */
		row.provider_status = sm5440_passive_request_fresh(&row.raw);
		row.returned_ms = ktime_to_ms(ktime_get_boottime());
		row.status = observer_check(row.requested_ms, row.returned_ms,
					    row.provider_status, &row.raw);
		mutex_lock(&result_lock);
		rows[nr_rows++] = row;
		if (row.status)
			state = OBSERVER_STOPPED;
		else if (nr_rows == OBSERVER_CALLS)
			state = OBSERVER_COMPLETED;
		mutex_unlock(&result_lock);
		if (row.status || i + 1 == OBSERVER_CALLS)
			return 0;
		/* Stop wakes the task; interruption must never start an extra call. */
		if (msleep_interruptible(OBSERVER_INTERVAL_MS))
			goto cancelled;
	}
	return 0;
cancelled:
	mutex_lock(&result_lock);
	state = OBSERVER_CANCELLED;
	mutex_unlock(&result_lock);
	return 0;
}

static int observer_result_show(struct seq_file *s, void *unused)
{
	unsigned int i;

	/* Cache only: reading results cannot request a conversion or change state. */
	mutex_lock(&result_lock);
	seq_puts(s, "format=sm5440-fresh-observer-v1\n");
	seq_printf(s, "state=%u\ncount=%u\nmaximum_calls=%u\ninterval_ms=%u\n",
		   state, nr_rows, OBSERVER_CALLS, OBSERVER_INTERVAL_MS);
	seq_puts(s, "PPS_authorized=0\npump_ON_authorized=0\nindependently_calibrated=0\n");
	for (i = 0; i < nr_rows; i++) {
		const struct observer_row *r = &rows[i];
		const struct sm5440_passive_measurement *m = &r->raw;

		seq_printf(s, "row=%u request_ms=%llu return_ms=%llu provider_status=%d status=%d usable=%u acquisition_ms=%llu raw_vbus_uv=%u raw_vbat_uv=%u raw_ibus_ua=%u raw_die_decic=%d raw_online=%u\n",
			   i + 1, r->requested_ms, r->returned_ms, r->provider_status,
			   r->status, !r->status, m->observed_ms, m->vbus_uv,
			   m->vbat_uv, m->ibus_ua, m->die_decic, m->online);
	}
	mutex_unlock(&result_lock);
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(observer_result);

static int __init observer_init(void)
{
	struct dentry *file;
	int ret;

	observer_root = debugfs_create_dir("sm5440-fresh-observer", NULL);
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
	observer_task = kthread_run(observer_thread, NULL, "sm5440-observe");
	if (IS_ERR(observer_task)) {
		ret = PTR_ERR(observer_task);
		goto remove;
	}
	return 0;
remove:
	debugfs_remove(observer_root);
	return ret;
}

static void __exit observer_exit(void)
{
	/* Join before removing cached results; no lock held over the drain. */
	kthread_stop(observer_task);
	debugfs_remove(observer_root);
}
module_init(observer_init);
module_exit(observer_exit);
MODULE_LICENSE("GPL");
MODULE_DESCRIPTION("Bounded passive SM5440 fresh-delivery observer; no pump/PPS");
