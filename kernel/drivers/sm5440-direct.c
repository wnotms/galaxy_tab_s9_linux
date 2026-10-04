// SPDX-License-Identifier: GPL-2.0-only
/* X710 Stage3B PASSIVE monitor. No pump-ON, PPS, Q4, reset, active protection,
 * reverse/bypass or writable power_supply property exists in this driver.
 * Hardware provenance: Samsung sm5440_charger.c/.h, cross-checked Fedora
 * ab123e7d. See docs/SM5440_REGISTER_AUDIT.md; register writes are limited to
 * mode-OFF and traced converter controls. Unaccepted ADC => unavailable.
 * A separately selected one-conversion condition test may temporarily clear
 * and restore ENHIZ bit7; it never publishes a charging companion.
 */
#include <linux/atomic.h>
#include <linux/delay.h>
#include <linux/debugfs.h>
#include <linux/i2c.h>
#include <linux/jiffies.h>
#include <linux/ktime.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/pm.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>
#include <linux/seq_file.h>
#include <linux/string.h>
#include <linux/wait.h>
#include <linux/workqueue.h>

#include "sm5440-hw.h"
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
#include "sm5440-timing.h"
#include "sm5714-stage2.h"
#endif
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
#include <linux/usb/pd.h>
#include "sm5440-control.h"
#include "sm5714-stage2.h"
#endif

struct sm5440_sample {
	u32 vbus_uv;
	u32 vbat_uv;
	u32 ibus_ua;
	int die_decic;
	u32 faults;
	/* BOOTTIME before converter enable: oldest plausible ADC acquisition. */
	u64 acquired_ms;
	/* After complete checked reads, immediately before cache publication. */
	u64 completed_ms;
	u64 acquisition_seq;
	/* Startup diagnostic only; never consulted by charging/admission. */
	u64 adc_read_completed_ms, gauge_started_ms, gauge_completed_ms;
	int gauge_ret, gauge_uv;
	bool gauge_attempted;
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	u8 cntl6_before, cntl6_during, cntl6_restored;
	bool cntl6_before_valid, cntl6_during_valid, cntl6_restored_valid;
	int condition_error, restore_error;
	u8 pre_status[4];
	bool pre_status_valid;
#endif
	/* Preserve read-to-clear INT separately from live STATUS. */
	u8 int_before[4], status[4], adc[11];
	u8 int4_after_disable, int4_wait, mode_before, mode_after;
	u8 cntl2, vbuscntl, vbatcntl, prtncntl;
	bool online;
	bool valid;
	unsigned long stamp;
};

#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
/* Worker-local evidence is copied under io_lock; no foreign supplier pointer. */
struct sm5440_context {
	struct sm5440_sample initial, confirmation, before, handoff;
	struct sm5440_control controls;
	struct sm5714_pd_snapshot standby;
	u64 instance, source_generation, budget_generation, lease;
	u64 started_ms, completed_ms, pack_started_ms, pack_completed_ms;
	unsigned int budget_ma;
	unsigned int readiness_checks;
	int capacity, pack_uv, pack_decic, phase, error, cleanup_error;
	bool inactive_revblk, lease_retained;
};
#endif

#ifdef CONFIG_SM5440_ADC_TIMING_TEST
struct sm5440_timing_context {
	struct sm5440_timing acquisition;
	struct sm5714_pd_snapshot source[2];
	struct sm5714_pack_snapshot pack[2];
	unsigned int readiness_checks;
	int admission_error, exit_error, off_error, first_readiness_error;
	bool attempted, off_attempted;
};
#endif

struct sm5440_direct {
	struct device *dev;
	struct regmap *regmap;
	struct mutex io_lock;
	struct delayed_work work;
	struct power_supply *psy;
	struct sm5440_sample sample;
	bool stopped;
	bool fault;
	bool initial_sample_done;
	u8 startup_confirmations;
	unsigned long startup_deadline;
	struct sm5440_sample startup_sample;
	unsigned long startup_stamp;
	int last_sample_error;
	struct dentry *debug_root;
	/* Fresh requests pin lifetime, not a charging grant. */
	atomic_t request_users, request_busy;
	wait_queue_head_t request_wait, users_wait;
	unsigned long sample_seq, request_epoch;
	u64 conversion_seq;
	bool dying;
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	struct sm5440_timing_context timing;
#endif
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	bool condition_attempted, enhiz_restore_pending;
	u8 enhiz_saved;
	struct sm5440_sample condition_sample;
	struct sm5440_context context;
	bool context_attempted;
#endif
};

/* Companion access. Cached lock order: companion_lock -> io_lock.
 * No pointer escapes; unpublish serializes with readers before devres teardown.
 * Poll/PM/debugfs never take companion_lock. No I2C/wait under this lock pair.
 */
static DEFINE_MUTEX(sm5440_companion_lock);
static struct sm5440_direct *sm5440_companion;

#ifndef CONFIG_SM5440_ADC_CONDITION_TEST
static int sm5440_publish(struct sm5440_direct *sm)
{
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	/* Isolated diagnostic: neither cached nor fresh charging API is published. */
	(void)sm;
	return 0;
#else
	int ret = 0;

	mutex_lock(&sm5440_companion_lock);
	if (sm5440_companion)
		ret = -EBUSY;
	else
		sm5440_companion = sm;
	mutex_unlock(&sm5440_companion_lock);
	return ret;
#endif
}
#endif

static void sm5440_unpublish(void *data)
{
	struct sm5440_direct *sm = data;

	mutex_lock(&sm5440_companion_lock);
	if (sm5440_companion == sm)
		sm5440_companion = NULL;
	WRITE_ONCE(sm->dying, true);
	mutex_unlock(&sm5440_companion_lock);
	wake_up_all(&sm->request_wait);
	wait_event(sm->users_wait, !atomic_read(&sm->request_users));
	/* A last user decrements/wakes while holding the registry. Wait for its
	 * final wake/unlock before devres may free the waitqueue and state.
	 */
	mutex_lock(&sm5440_companion_lock);
	mutex_unlock(&sm5440_companion_lock);
}

/* io_lock held; shared refusal rules for cached and new conversion copies. */
static int sm5440_sample_ready_locked(struct sm5440_direct *sm)
{
	lockdep_assert_held(&sm->io_lock);
	if (READ_ONCE(sm->dying))
		return -ENODEV;
	if (READ_ONCE(sm->stopped))
		return -ESHUTDOWN;
	if (sm->fault || sm->sample.faults || sm->last_sample_error)
		return -EIO;
	if (!sm->initial_sample_done || !sm->sample.valid ||
	    sm->startup_confirmations)
		return -EAGAIN;
	if ((sm->sample.mode_before | sm->sample.mode_after) & SM5440_MODE_MASK)
		return -EBUSY;
	return 0;
}

static int sm5440_copy_sample_locked(struct sm5440_direct *sm,
				     struct sm5440_passive_measurement *out, u64 now)
{
	int ret = sm5440_sample_ready_locked(sm);

	if (ret)
		return ret;
	if (!sm->sample.acquired_ms || sm->sample.acquired_ms > now ||
	    now - sm->sample.acquired_ms > SM5440_FRESH_REQUEST_MS)
		return -ESTALE;
	out->observed_ms = sm->sample.acquired_ms;
	out->vbus_uv = sm->sample.vbus_uv;
	out->vbat_uv = sm->sample.vbat_uv;
	out->ibus_ua = sm->sample.ibus_ua;
	out->die_decic = sm->sample.die_decic;
	out->online = sm->sample.online;
	return 0;
}

int sm5440_passive_read_cached(struct sm5440_passive_measurement *out)
{
	struct sm5440_direct *sm;
	u64 now;
	int ret = 0;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	mutex_lock(&sm5440_companion_lock);
	sm = sm5440_companion;
	if (!sm) {
		ret = -ENODEV;
		goto unlock;
	}
	/* Do not hold the lifetime registry while waiting on worker I2C. */
	if (!mutex_trylock(&sm->io_lock)) {
		ret = -EBUSY;
		goto unlock;
	}
	now = ktime_to_ms(ktime_get_boottime());
	ret = sm5440_copy_sample_locked(sm, out, now);
	mutex_unlock(&sm->io_lock);
unlock:
	mutex_unlock(&sm5440_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5440_passive_read_cached);

/* Sleepable, OFF-mode only. No registry/charger lock across the wait, no
 * second converter, no cancellation of ordinary monitoring on a timeout.
 * This is a100ms evidence validity guard, NOT hardware cutoff/realtime proof.
 */
int sm5440_passive_request_fresh(struct sm5440_passive_measurement *out)
{
	struct sm5440_direct *sm;
	unsigned long seq, epoch;
	u64 start, now, started_seq;
	long remaining;
	bool reserved = false;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	start = ktime_to_ms(ktime_get_boottime());
	mutex_lock(&sm5440_companion_lock);
	sm = sm5440_companion;
	if (sm)
		atomic_inc(&sm->request_users);
	mutex_unlock(&sm5440_companion_lock);
	if (!sm)
		return -ENODEV;
	if (atomic_cmpxchg(&sm->request_busy, 0, 1)) {
		ret = -EBUSY;
		goto put;
	}
	reserved = true;
	if (!mutex_trylock(&sm->io_lock)) {
		ret = -EBUSY;
		goto put;
	}
	ret = sm5440_sample_ready_locked(sm);
	if (ret)
		goto unlock;
	seq = sm->sample_seq;
	started_seq = sm->conversion_seq;
	epoch = sm->request_epoch;
	now = ktime_to_ms(ktime_get_boottime());
	if (now < start || now - start >= SM5440_FRESH_REQUEST_MS) {
		ret = -ETIMEDOUT;
		goto unlock;
	}
	remaining = msecs_to_jiffies(SM5440_FRESH_REQUEST_MS - (now - start));
	/* PM sets stopped/epoch under this same lock BEFORE drain: never queue
	 * after quiesce has canceled work. Running work may finish an old sample;
	 * that completion will be refused, not relabeled as this acquisition.
	 */
	/* Match schedule_delayed_work(): pinned7.2 uses system_percpu_wq.
	 * A different queue would forfeit same-work non-reentrancy.
	 */
	mod_delayed_work(system_percpu_wq, &sm->work, 0);
	mutex_unlock(&sm->io_lock);
	if (!wait_event_timeout(sm->request_wait,
		READ_ONCE(sm->sample_seq) != seq || READ_ONCE(sm->stopped) ||
		READ_ONCE(sm->fault) || READ_ONCE(sm->dying) ||
		READ_ONCE(sm->request_epoch) != epoch, remaining)) {
		ret = -ETIMEDOUT;
		goto put;
	}
	if (!mutex_trylock(&sm->io_lock)) {
		ret = -EBUSY;
		goto put;
	}
	now = ktime_to_ms(ktime_get_boottime());
	if (sm->request_epoch != epoch)
		ret = -ESHUTDOWN;
	else if (now < start || now - start > SM5440_FRESH_REQUEST_MS)
		ret = -ETIMEDOUT;
	else if (sm->sample_seq == seq)
		ret = sm5440_sample_ready_locked(sm) ?: -EAGAIN;
	else if (sm->sample.acquisition_seq <= started_seq)
		ret = -ESTALE;
	else {
		ret = sm5440_copy_sample_locked(sm, out, now);
		if (!ret && out->observed_ms < start)
			ret = -ESTALE;
	}
unlock:
	mutex_unlock(&sm->io_lock);
put:
	if (ret)
		memset(out, 0, sizeof(*out));
	if (reserved)
		atomic_set(&sm->request_busy, 0);
	mutex_lock(&sm5440_companion_lock);
	if (atomic_dec_and_test(&sm->request_users))
		wake_up_all(&sm->users_wait);
	mutex_unlock(&sm5440_companion_lock);
	/* No provider access after dropping its user; include final release delay. */
	now = ktime_to_ms(ktime_get_boottime());
	if (!ret && (now < start || now - start > SM5440_FRESH_REQUEST_MS)) {
		memset(out, 0, sizeof(*out));
		ret = -ETIMEDOUT;
	}
	return ret;
}
EXPORT_SYMBOL_GPL(sm5440_passive_request_fresh);

/* A slow, newly acquired OFF-mode sample may be useful diagnostic evidence
 * while still FAILING the legacy100ms freshness/delivery contract. Keep this
 * API and its output type separate: no active consumer or userspace writer.
 * Lifetime/reservation/PM serialization match the original request API.
 */
int sm5440_passive_observe(struct sm5440_passive_observation *out)
{
	struct sm5440_direct *sm;
	unsigned long seq, epoch;
	u64 start, now, started_seq;
	long remaining;
	bool reserved = false;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	start = ktime_to_ms(ktime_get_boottime());
	mutex_lock(&sm5440_companion_lock);
	sm = sm5440_companion;
	if (sm)
		atomic_inc(&sm->request_users);
	mutex_unlock(&sm5440_companion_lock);
	if (!sm)
		return -ENODEV;
	if (atomic_cmpxchg(&sm->request_busy, 0, 1)) {
		ret = -EBUSY;
		goto put;
	}
	reserved = true;
	if (!mutex_trylock(&sm->io_lock)) {
		ret = -EBUSY;
		goto put;
	}
	ret = sm5440_sample_ready_locked(sm);
	if (ret)
		goto unlock;
	seq = sm->sample_seq;
	started_seq = sm->conversion_seq;
	epoch = sm->request_epoch;
	now = ktime_to_ms(ktime_get_boottime());
	if (!start || now < start ||
	    now - start >= SM5440_PASSIVE_OBSERVATION_MS) {
		ret = -ETIMEDOUT;
		goto unlock;
	}
	remaining = msecs_to_jiffies(SM5440_PASSIVE_OBSERVATION_MS - (now - start));
	mod_delayed_work(system_percpu_wq, &sm->work, 0);
	mutex_unlock(&sm->io_lock);
	if (!wait_event_timeout(sm->request_wait,
		READ_ONCE(sm->sample_seq) != seq || READ_ONCE(sm->stopped) ||
		READ_ONCE(sm->fault) || READ_ONCE(sm->dying) ||
		READ_ONCE(sm->request_epoch) != epoch, remaining)) {
		ret = -ETIMEDOUT;
		goto put;
	}
	if (!mutex_trylock(&sm->io_lock)) {
		ret = -EBUSY;
		goto put;
	}
	now = ktime_to_ms(ktime_get_boottime());
	if (sm->request_epoch != epoch)
		ret = -ESHUTDOWN;
	else if (now < start || now - start > SM5440_PASSIVE_OBSERVATION_MS)
		ret = -ETIMEDOUT;
	else
		ret = sm5440_sample_ready_locked(sm);
	if (ret)
		goto unlock;
	if (sm->sample_seq == seq || sm->sample.acquisition_seq <= started_seq ||
	    !sm->sample.acquired_ms || sm->sample.acquired_ms < start ||
	    sm->sample.completed_ms < sm->sample.acquired_ms ||
	    sm->sample.completed_ms > now) {
		ret = -ESTALE;
		goto unlock;
	}
	out->measurement.observed_ms = sm->sample.acquired_ms;
	out->measurement.vbus_uv = sm->sample.vbus_uv;
	out->measurement.vbat_uv = sm->sample.vbat_uv;
	out->measurement.ibus_ua = sm->sample.ibus_ua;
	out->measurement.die_decic = sm->sample.die_decic;
	out->measurement.online = sm->sample.online;
	out->request_ms = start;
	out->completed_ms = sm->sample.completed_ms;
	out->acquisition_seq = sm->sample.acquisition_seq;
	out->request_epoch = epoch;
unlock:
	mutex_unlock(&sm->io_lock);
put:
	if (reserved)
		atomic_set(&sm->request_busy, 0);
	mutex_lock(&sm5440_companion_lock);
	if (atomic_dec_and_test(&sm->request_users))
		wake_up_all(&sm->users_wait);
	mutex_unlock(&sm5440_companion_lock);
	/* No provider access after dropping its user; do not restamp acquisition. */
	now = ktime_to_ms(ktime_get_boottime());
	if (!ret) {
		if (now < out->completed_ms || now < start ||
		    now - start > SM5440_PASSIVE_OBSERVATION_MS)
			ret = -ETIMEDOUT;
		else {
			out->returned_ms = now;
			out->oldest_age_ms = now - out->measurement.observed_ms;
		}
	}
	if (ret)
		memset(out, 0, sizeof(*out));
	return ret;
}
EXPORT_SYMBOL_GPL(sm5440_passive_observe);

/* Diagnostic copy only. No register access or charging authorization. */
struct sm5440_snapshot {
	struct sm5440_sample sample, startup;
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	struct sm5440_timing_context timing;
#endif
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	struct sm5440_sample condition;
	bool condition_attempted, enhiz_restore_pending;
	struct sm5440_context context;
#endif
	unsigned long captured, startup_stamp;
	u64 age_ms;
	int last_error;
	u8 pending;
	bool present, stopped, fault, fresh;
};

static void sm5440_snapshot_capture(struct sm5440_direct *sm,
				    struct sm5440_snapshot *snapshot)
{
	mutex_lock(&sm->io_lock);
	snapshot->sample = sm->sample;
	snapshot->startup = sm->startup_sample;
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	snapshot->timing = sm->timing;
#endif
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	snapshot->condition = sm->condition_sample;
	snapshot->context = sm->context;
	snapshot->condition_attempted = sm->condition_attempted;
	snapshot->enhiz_restore_pending = sm->enhiz_restore_pending;
#endif
	snapshot->captured = jiffies;
	snapshot->startup_stamp = sm->startup_stamp;
	snapshot->last_error = sm->last_sample_error;
	snapshot->pending = sm->startup_confirmations;
	snapshot->present = sm->initial_sample_done;
	/* PM sets stopped before taking io_lock and draining the worker. */
	snapshot->stopped = READ_ONCE(sm->stopped);
	snapshot->fault = sm->fault;
	mutex_unlock(&sm->io_lock);
	snapshot->fresh = snapshot->present && snapshot->sample.valid &&
		!snapshot->stopped && !snapshot->fault && !snapshot->pending &&
		!snapshot->sample.faults && !time_before(snapshot->captured,
			snapshot->sample.stamp) && !time_after(snapshot->captured,
			snapshot->sample.stamp + msecs_to_jiffies(2500));
	/* Keep long fault-cache ages in 64 bits; zero without present is unknown. */
	snapshot->age_ms = snapshot->present ?
		jiffies64_to_msecs((u64)(snapshot->captured - snapshot->sample.stamp)) : 0;
}

static void sm5440_snapshot_sample_show(struct seq_file *seq, const char *name,
				       const struct sm5440_sample *sample)
{
	seq_printf(seq, "%s_valid=%u\n%s_stamp_jiffies=%lu\n%s_faults=0x%x\n",
		   name, sample->valid, name, sample->stamp, name, sample->faults);
	seq_printf(seq, "%s_gauge_attempted=%u\n%s_adc_read_completed_ms=%llu\n"
		   "%s_gauge_started_ms=%llu\n%s_gauge_completed_ms=%llu\n"
		   "%s_gauge_ret=%d\n%s_gauge_uv=%d\n", name, sample->gauge_attempted,
		   name, (unsigned long long)sample->adc_read_completed_ms,
		   name, (unsigned long long)sample->gauge_started_ms,
		   name, (unsigned long long)sample->gauge_completed_ms,
		   name, sample->gauge_ret, name, sample->gauge_uv);
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	seq_printf(seq, "%s_cntl6_before_valid=%u\n%s_cntl6_before=0x%02x\n"
		   "%s_cntl6_during_valid=%u\n%s_cntl6_during=0x%02x\n"
		   "%s_cntl6_restored_valid=%u\n%s_cntl6_restored=0x%02x\n"
		   "%s_condition_error=%d\n%s_restore_error=%d\n", name,
		   sample->cntl6_before_valid, name, sample->cntl6_before, name,
		   sample->cntl6_during_valid, name, sample->cntl6_during, name,
		   sample->cntl6_restored_valid, name, sample->cntl6_restored, name,
		   sample->condition_error, name, sample->restore_error);
	seq_printf(seq, "%s_pre_status_valid=%u\n%s_pre_status=%*ph\n", name,
		   sample->pre_status_valid, name, 4, sample->pre_status);
	seq_printf(seq, "%s_acquired_ms=%llu\n%s_completed_ms=%llu\n%s_acquisition_seq=%llu\n",
		   name, (unsigned long long)sample->acquired_ms,
		   name, (unsigned long long)sample->completed_ms,
		   name, (unsigned long long)sample->acquisition_seq);
#endif
	seq_printf(seq, "%s_int=%*ph\n%s_status=%*ph\n%s_adc=%*ph\n", name,
		   4, sample->int_before, name, 4, sample->status, name, 11, sample->adc);
	seq_printf(seq, "%s_int4_disable=0x%02x\n%s_int4_wait=0x%02x\n",
		   name, sample->int4_after_disable, name, sample->int4_wait);
	seq_printf(seq, "%s_mode_before=0x%02x\n%s_mode_after=0x%02x\n",
		   name, sample->mode_before, name, sample->mode_after);
	seq_printf(seq, "%s_cntl2=0x%02x\n%s_vbuscntl=0x%02x\n"
		   "%s_vbatcntl=0x%02x\n%s_prtncntl=0x%02x\n", name, sample->cntl2,
		   name, sample->vbuscntl, name, sample->vbatcntl, name, sample->prtncntl);
	seq_printf(seq, "%s_vbus_uv=%u\n%s_vbat_uv=%u\n%s_ibus_ua=%u\n%s_die_decic=%d\n",
		   name, sample->vbus_uv, name, sample->vbat_uv,
		   name, sample->ibus_ua, name, sample->die_decic);
}

#ifdef CONFIG_SM5440_ADC_TIMING_TEST
static void sm5440_timing_show(struct seq_file *seq,
			       const struct sm5440_timing_context *c)
{
	const struct sm5440_timing *t = &c->acquisition;
	unsigned int i;

	seq_printf(seq, "timing_test=1\ntiming_attempted=%u\ntiming_admission_error=%d\n"
		   "timing_exit_error=%d\ntiming_error=%d\ntiming_cleanup_error=%d\n"
		   "timing_count=%u\ntiming_polls=%u\ntiming_restored=%u\n"
		   "timing_started_ms=%llu\ntiming_disabled_ms=%llu\n"
		   "timing_enabled_ms=%llu\ntiming_completed_ms=%llu\n",
		   c->attempted, c->admission_error, c->exit_error, t->error,
		   t->cleanup_error, t->count, t->polls, t->restored,
		   t->started_ms, t->disabled_ms, t->enabled_ms, t->completed_ms);
	seq_printf(seq, "timing_controls=%02x/%02x/%02x/%02x\n"
		   "timing_initial_int=%*ph\ntiming_initial_status=%*ph\n",
		   t->control_before, t->channels_before, t->control_after,
		   t->channels_after, 4, t->initial_interrupt, 4, t->initial_status);
	seq_printf(seq, "timing_off_attempted=%u\ntiming_off_error=%d\n",
		   c->off_attempted, c->off_error);
	seq_printf(seq, "timing_readiness_checks=%u\n", c->readiness_checks);
	seq_printf(seq, "timing_first_readiness_error=%d\n", c->first_readiness_error);
	for (i = 0; i < 2; i++)
		seq_printf(seq, "timing_source%u=%llu/%llu/%llu/%llu/%llu/%u/%u/%d\n"
			   "timing_pack%u=%llu/%llu/%llu/%llu/%d/%d/%d\n",
			   i, c->source[i].instance, c->source[i].source_generation,
			   c->source[i].budget_generation, c->source[i].started_ms,
			   c->source[i].completed_ms, c->source[i].budget_mv,
			   c->source[i].budget_ma, c->source[i].online,
			   i, c->pack[i].instance, c->pack[i].state_generation,
			   c->pack[i].started_ms, c->pack[i].completed_ms,
			   c->pack[i].capacity, c->pack[i].voltage_uv, c->pack[i].pack_decic);
	/* Include the partial failed slot as well as all completed samples. */
	for (i = 0; i < SM5440_TIMING_SAMPLES && i <= t->count; i++) {
		const struct sm5440_timing_sample *a = &t->sample[i];

		seq_printf(seq, "timing_sample%u_times=%llu/%llu/%llu/%llu/%llu\n"
			   "timing_sample%u_int=%*ph\ntiming_sample%u_status=%*ph\n"
			   "timing_sample%u_status_after=%*ph\ntiming_sample%u_adc=%*ph\n"
			   "timing_sample%u_controls=%02x/%02x/%02x\n"
			   "timing_sample%u_faults=0x%x\n", i, a->cleared_ms,
			   a->ready_begin_ms, a->ready_end_ms, a->adc_begin_ms, a->adc_end_ms,
			   i, 4, a->interrupt, i, 4, a->status, i, 4, a->status_after,
			   i, 11, a->adc, i, a->mode, a->control, a->channels, i, a->faults);
	}
}
#endif

static int sm5440_snapshot_show(struct seq_file *seq, void *unused)
{
	struct sm5440_snapshot snapshot;

	(void)unused;
	sm5440_snapshot_capture(seq->private, &snapshot);
	/* Format after releasing io_lock. Never refresh or consume INT on read. */
	seq_puts(seq, "format=sm5440-passive-v1\nregisters_are_cached=1\n"
		 "independently_calibrated=0\npump_enable_supported=0\n");
	seq_printf(seq, "capture_jiffies=%lu\nsample_present=%u\nsample_fresh=%u\n"
		   "sample_age_ms=%llu\nstopped=%u\nfault=%u\nstartup_pending=%u\n"
		   "last_sample_error=%d\nstartup_retained=%u\nstartup_capture_jiffies=%lu\n",
		   snapshot.captured, snapshot.present, snapshot.fresh,
		   (unsigned long long)snapshot.age_ms, snapshot.stopped, snapshot.fault,
		   snapshot.pending, snapshot.last_error, !!snapshot.startup.faults,
		   snapshot.startup_stamp);
	sm5440_snapshot_sample_show(seq, "sample", &snapshot.sample);
	sm5440_snapshot_sample_show(seq, "startup", &snapshot.startup);
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	sm5440_timing_show(seq, &snapshot.timing);
#endif
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	seq_printf(seq, "condition_test=1\ncondition_attempted=%u\n"
		   "enhiz_restore_pending=%u\n", snapshot.condition_attempted,
		   snapshot.enhiz_restore_pending);
	sm5440_snapshot_sample_show(seq, "condition", &snapshot.condition);
	seq_printf(seq, "context_phase=%d\ncontext_error=%d\ncontext_cleanup_error=%d\n"
		   "context_instance=%llu\ncontext_source_generation=%llu\n"
		   "context_budget_generation=%llu\ncontext_lease=%llu\n"
		   "context_lease_retained=%u\ncontext_inactive_revblk=%u\n"
		   "context_budget_ma=%u\ncontext_capacity=%d\ncontext_pack_uv=%d\n"
		   "context_pack_decic=%d\ncontext_settings_pending=%u\n",
		   snapshot.context.phase, snapshot.context.error,
		   snapshot.context.cleanup_error,
		   (unsigned long long)snapshot.context.instance,
		   (unsigned long long)snapshot.context.source_generation,
		   (unsigned long long)snapshot.context.budget_generation,
		   (unsigned long long)snapshot.context.lease,
		   snapshot.context.lease_retained, snapshot.context.inactive_revblk,
		   snapshot.context.budget_ma, snapshot.context.capacity,
		   snapshot.context.pack_uv, snapshot.context.pack_decic,
		   snapshot.context.controls.pending);
	seq_printf(seq, "context_started_ms=%llu\ncontext_completed_ms=%llu\n"
		   "context_pack_started_ms=%llu\ncontext_pack_completed_ms=%llu\n"
		   "context_controls_state=%u\ncontext_controls_attempted=0x%x\n"
		   "context_controls_off_verified=%u\ncontext_controls_operation_error=%d\n"
		   "context_controls_restore_error=%d\ncontext_controls_witness_valid=%u\n"
		   "context_controls_before=%*ph\ncontext_controls_witness=%*ph\n"
		   "context_controls_status_before=%*ph\ncontext_controls_status_after=%*ph\n",
		   (unsigned long long)snapshot.context.started_ms,
		   (unsigned long long)snapshot.context.completed_ms,
		   (unsigned long long)snapshot.context.pack_started_ms,
		   (unsigned long long)snapshot.context.pack_completed_ms,
		   snapshot.context.controls.state, snapshot.context.controls.attempted,
		   snapshot.context.controls.off_verified, snapshot.context.controls.operation_error,
		   snapshot.context.controls.restore_error, snapshot.context.controls.witness_valid,
		   SM5440_CONTROL_SETTINGS, snapshot.context.controls.before,
		   SM5440_CONTROL_WITNESSES, snapshot.context.controls.witness,
		   4, snapshot.context.controls.status_before, 4, snapshot.context.controls.status_after);
	sm5440_snapshot_sample_show(seq, "context_initial", &snapshot.context.initial);
	sm5440_snapshot_sample_show(seq, "context_confirmation", &snapshot.context.confirmation);
	sm5440_snapshot_sample_show(seq, "context_before", &snapshot.context.before);
	sm5440_snapshot_sample_show(seq, "context_handoff", &snapshot.context.handoff);
	seq_printf(seq, "context_readiness_checks=%u\ncontext_standby_instance=%llu\n"
		   "context_standby_source_generation=%llu\ncontext_standby_started_ms=%llu\n"
		   "context_standby_completed_ms=%llu\ncontext_standby_budget_mv=%u\n"
		   "context_standby_budget_ma=%u\ncontext_standby_usb_type=%d\n"
		   "context_standby_nr_source_pdos=%u\ncontext_standby_source_pdos=%*ph\n",
		   snapshot.context.readiness_checks,
		   (unsigned long long)snapshot.context.standby.instance,
		   (unsigned long long)snapshot.context.standby.source_generation,
		   (unsigned long long)snapshot.context.standby.started_ms,
		   (unsigned long long)snapshot.context.standby.completed_ms,
		   snapshot.context.standby.budget_mv, snapshot.context.standby.budget_ma,
		   snapshot.context.standby.usb_type, snapshot.context.standby.nr_source_pdos,
		   (int)sizeof(snapshot.context.standby.source_pdos), snapshot.context.standby.source_pdos);
#endif
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(sm5440_snapshot);

static void sm5440_debugfs_remove(void *data)
{
	struct sm5440_direct *sm = data;

	debugfs_remove(sm->debug_root);
	sm->debug_root = NULL;
}

static void sm5440_debugfs_init(struct sm5440_direct *sm)
{
	struct dentry *file;
	char name[64];

	if (snprintf(name, sizeof(name), "sm5440-%s", dev_name(sm->dev)) >= (int)sizeof(name))
		return;
	sm->debug_root = debugfs_create_dir(name, NULL);
	if (IS_ERR_OR_NULL(sm->debug_root)) {
		sm->debug_root = NULL;
		return;
	}
	file = debugfs_create_file("snapshot", 0400, sm->debug_root, sm,
				   &sm5440_snapshot_fops);
	if (IS_ERR_OR_NULL(file)) {
		sm5440_debugfs_remove(sm);
		return;
	}
	/* Added after stop: devres removes/drains files before freeing driver data.
	 * Use normal debugfs proxies, not the unsafe create_file variant.
	 */
	if (devm_add_action_or_reset(sm->dev, sm5440_debugfs_remove, sm))
		dev_dbg(sm->dev, "passive snapshot unavailable; monitor unchanged\n");
}

static const struct regmap_config sm5440_regmap = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = SM5440_DEVICEID,
	.cache_type = REGCACHE_NONE,
};

/* Caller holds io_lock. Vendor set_op_mode(): CNTL5[3:2], OFF=0. */
static int sm5440_off(struct sm5440_direct *sm)
{
	unsigned int mode;
	int ret;

	lockdep_assert_held(&sm->io_lock);
	ret = regmap_update_bits(sm->regmap, SM5440_CNTL5,
				 SM5440_MODE_MASK, SM5440_MODE_OFF);
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EIO;
	return ret;
}

static int sm5440_sample_once(struct sm5440_direct *sm,
			      struct sm5440_sample *sample)
{
	unsigned int mode, ready, value;
	u8 events[4], status[4], adc[11];
	int ret, i;

	mutex_lock(&sm->io_lock);
	/* Distinguish an older in-flight conversion even within one clock ms. */
	sample->acquisition_seq = ++sm->conversion_seq;
	ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY; /* never adopt a running/reverse pump */
	if (!ret)
		sample->mode_before = mode;
	/* Consume old conversion/fault latches before starting a new conversion.
	 * Vendor IRQ reads INT1..4; retain faults instead of discarding them.
	 */
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5440_INT1, events, sizeof(events));
	if (!ret)
		memcpy(sample->int_before, events, sizeof(events));
	if (!ret)
		ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					 SM5440_ADC_ENABLE | SM5440_ADC_RATE, 0);
	/* A previous conversion can finish between the first latch read and
	 * disabling ADC. Consume that completion AFTER disable as well.
	 */
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_INT4, &ready);
		if (!ret) {
			sample->int4_after_disable = ready;
			events[3] |= ready;
		}
	}
	if (!ret)
		ret = regmap_write(sm->regmap, SM5440_ADCCNTL2, SM5440_ADC_CHANNELS);
	if (!ret) {
		/* Vendor converter sequence unchanged; never stamp a cache lookup. */
		sample->acquired_ms = ktime_to_ms(ktime_get_boottime());
		ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					 SM5440_ADC_ENABLE | SM5440_ADC_AVG32,
					 SM5440_ADC_ENABLE | SM5440_ADC_AVG32);
	}
	mutex_unlock(&sm->io_lock);
	if (ret)
		return ret;
	/* Single worker; PM/remove synchronously drain it. No mutex is held
	 * across a converter wait. Unknown completion is not a measurement.
	 */
	for (i = 0; i < 12; i++) {
		if (READ_ONCE(sm->stopped))
			return -ESHUTDOWN;
		msleep(25);
		mutex_lock(&sm->io_lock);
		ret = regmap_read(sm->regmap, SM5440_INT4, &ready);
		mutex_unlock(&sm->io_lock);
		if (ret)
			return ret;
		/* Retain watchdog/timer events consumed while waiting. */
		sample->int4_wait |= ready;
		events[3] |= ready;
		if (ready & SM5440_ADC_READY)
			break;
	}
	if (i == 12)
		return -ETIMEDOUT;
	mutex_lock(&sm->io_lock);
	ret = regmap_bulk_read(sm->regmap, SM5440_ADC_VBUS, adc, sizeof(adc));
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5440_STATUS1, status, sizeof(status));
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY;
	/* Samsung get_vbatreg()/get_ibuslim()/init_reg_param(): these are
	 * ordinary control registers, not read-to-clear interrupt registers.
	 * Read-only provenance; never change protections to suppress a fault.
	 */
	if (!ret) {
		sample->mode_after = mode;
		ret = regmap_read(sm->regmap, SM5440_CNTL2, &value);
		if (!ret)
			sample->cntl2 = value;
	}
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_VBUSCNTL, &value);
		if (!ret)
			sample->vbuscntl = value;
	}
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_VBATCNTL, &value);
		if (!ret)
			sample->vbatcntl = value;
	}
	if (!ret) {
		ret = regmap_read(sm->regmap, SM5440_PRTNCNTL, &value);
		if (!ret)
			sample->prtncntl = value;
	}
	if (!ret) {
		memcpy(sample->status, status, sizeof(status));
		memcpy(sample->adc, adc, sizeof(adc));
		for (i = 0; i < 4; i++)
			events[i] |= status[i];
		sample->vbus_uv = sm5440_vbus_uv(adc[0], adc[1]);
		sample->ibus_ua = sm5440_ibus_ua(adc[4], adc[5]);
		sample->die_decic = sm5440_die_decic(adc[8]);
		sample->vbat_uv = sm5440_vbat_uv(adc[9], adc[10]);
		sample->online = !!(status[2] & BIT(5));
		sample->faults = sm5440_decode_faults(events, false, 0);
		/* Implausible pack samples remain unavailable, even if ADC ready.
		 * Passive monitor never authorizes charge based on these values.
		 */
		if (sample->vbat_uv < 2500000 || sample->vbat_uv > 4600000)
			ret = -ERANGE;
	}
	mutex_unlock(&sm->io_lock);
	return ret;
}

/* A pre-conversion REVBLK latch is not proof of current pump activity.
 * Samsung IRQ uses direct-state/mode context (see passive startup audit).
 * Keep the event, require new conversions, and never exempt live/repeated
 * faults or VBAT_OVP. This classifier is limited to ordinary PC USB.
 */
static bool sm5440_passive_pc_sample(const struct sm5440_sample *sample)
{
	return !(sample->mode_before & SM5440_MODE_MASK) &&
		!(sample->mode_after & SM5440_MODE_MASK) &&
		(sample->int4_wait & SM5440_ADC_READY) && sample->online &&
		sample->vbus_uv >= 4500000 && sample->vbus_uv <= 5500000 &&
		sample->vbat_uv >= 3500000 && sample->vbat_uv < 4300000 &&
		!sample->ibus_ua && sample->die_decic >= 225 &&
		sample->die_decic < 420;
}

static bool sm5440_startup_revblk(const struct sm5440_sample *sample)
{
	return sample->faults == SM5440_FAULT_REVBLK &&
		sm5440_decode_faults(sample->int_before, false, 0) == SM5440_FAULT_REVBLK &&
		!sm5440_decode_faults(sample->status, false, 0) &&
		sm5440_passive_pc_sample(sample);
}

static bool sm5440_startup_matches(const struct sm5440_sample *sample,
				   const struct sm5440_sample *initial)
{
	return !sample->faults && sm5440_passive_pc_sample(sample) &&
		sample->cntl2 == initial->cntl2 &&
		sample->vbuscntl == initial->vbuscntl &&
		sample->vbatcntl == initial->vbatcntl &&
		sample->prtncntl == initial->prtncntl;
}

/* Samsung sm5440_set_adc_mode(ONESHOT): disable,20ms,rate0,enable.
 * Keep sample_once's checked converter/latch sequence intact. Its second
 * disable is idempotent; no ADC enable occurs between these two steps.
 * A single drained worker owns this preamble; no lock across the wait.
 */
static int sm5440_adc_rearm(struct sm5440_direct *sm)
{
	unsigned int mode;
	int ret;

	mutex_lock(&sm->io_lock);
	if (READ_ONCE(sm->stopped)) {
		ret = -ESHUTDOWN;
	} else {
		ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
		if (!ret && (mode & SM5440_MODE_MASK))
			ret = -EBUSY;
		if (!ret)
			ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
						 SM5440_ADC_ENABLE, 0);
	}
	mutex_unlock(&sm->io_lock);
	if (ret)
		return ret;
	msleep(20);
	return READ_ONCE(sm->stopped) ? -ESHUTDOWN : 0;
}

#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
/* Samsung init_reg_param() clears ENHIZ before direct-state ADC work, while
 * set_ENHIZ() sets CNTL6[7] for attached+OFF. Isolate only that condition;
 * do not import active init, reset, protection/current writes or pump ON.
 * Single drained worker owns saved state; PM/remove wait without io_lock.
 */
static int sm5440_condition_begin(struct sm5440_direct *sm,
				 struct sm5440_sample *sample)
{
	unsigned int mode, value;
	int ret;

	mutex_lock(&sm->io_lock);
	if (sm->condition_attempted) {
		ret = -EALREADY;
		goto out;
	}
	sm->condition_attempted = true;
	if (READ_ONCE(sm->stopped) || READ_ONCE(sm->dying)) {
		ret = -ESHUTDOWN;
		goto out;
	}
	if (sm->fault) {
		ret = -EIO;
		goto out;
	}
	ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (!ret && (mode & SM5440_MODE_MASK))
		ret = -EBUSY;
	if (!ret) {
		/* Live STATUS immediately before mutation, never an INT latch. */
		ret = regmap_bulk_read(sm->regmap, SM5440_STATUS1,
				       sample->pre_status, sizeof(sample->pre_status));
		if (!ret) {
			sample->pre_status_valid = true;
			if (sm5440_decode_faults(sample->pre_status, false, 0) ||
			    (sample->pre_status[2] & BIT(6)))
				ret = -EIO;
			else if (!(sample->pre_status[2] & BIT(5)))
				ret = -ENOLINK;
		}
	}
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_CNTL6, &value);
	if (ret)
		goto out;
	sm->enhiz_saved = value;
	sample->cntl6_before = value;
	sample->cntl6_before_valid = true;
	ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_ADCCNTL1, &value);
	if (!ret && (value & SM5440_ADC_ENABLE))
		ret = -EIO;
	if (ret)
		goto out;
	/* A failed write may have reached silicon: pending BEFORE attempting it. */
	sm->enhiz_restore_pending = true;
	ret = regmap_update_bits(sm->regmap, SM5440_CNTL6, SM5440_ENHIZ, 0);
	if (!ret)
		ret = regmap_read(sm->regmap, SM5440_CNTL6, &value);
	if (!ret) {
		sample->cntl6_during = value;
		sample->cntl6_during_valid = true;
		if (value != (sm->enhiz_saved & ~SM5440_ENHIZ))
			ret = -EIO;
	}
out:
	mutex_unlock(&sm->io_lock);
	return ret;
}

/* Always try bit-only restoration, even when OFF/ADC-off verification failed.
 * Never claim success from a write alone; retain pending on ANY cleanup error.
 * A caller returns the first conversion error separately from cleanup failure.
 */
static int sm5440_condition_restore(struct sm5440_direct *sm,
				   struct sm5440_sample *sample)
{
	unsigned int value;
	int ret = 0, err;

	mutex_lock(&sm->io_lock);
	if (!sm->enhiz_restore_pending)
		goto out;
	ret = sm5440_off(sm);
	err = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	if (!ret)
		ret = err;
	err = regmap_read(sm->regmap, SM5440_ADCCNTL1, &value);
	if (!err && (value & SM5440_ADC_ENABLE))
		err = -EIO;
	if (!ret)
		ret = err;
	err = regmap_update_bits(sm->regmap, SM5440_CNTL6, SM5440_ENHIZ,
				 sm->enhiz_saved & SM5440_ENHIZ);
	if (!ret)
		ret = err;
	err = regmap_read(sm->regmap, SM5440_CNTL6, &value);
	if (!err) {
		sample->cntl6_restored = value;
		sample->cntl6_restored_valid = true;
		if (value != sm->enhiz_saved)
			err = -EIO;
	}
	if (!ret)
		ret = err;
	err = regmap_read(sm->regmap, SM5440_CNTL5, &value);
	if (!err && (value & SM5440_MODE_MASK))
		err = -EIO;
	if (!ret)
		ret = err;
	if (!ret)
		sm->enhiz_restore_pending = false;
	else
		sm->fault = true;
out:
	sample->restore_error = ret;
	mutex_unlock(&sm->io_lock);
	return ret;
}

static int sm5440_condition_cycle(struct sm5440_direct *sm,
				 struct sm5440_sample *sample)
{
	int ret, restore;

	ret = sm5440_condition_begin(sm, sample);
	if (!ret)
		ret = sm5440_adc_rearm(sm);
	if (!ret)
		ret = sm5440_sample_once(sm, sample);
	sample->condition_error = ret;
	restore = sm5440_condition_restore(sm, sample);
	return ret ? ret : restore;
}
#endif

/* Near-time comparison, not sensor calibration or a charging grant.
 * Called only for startup evidence, after sample_once has released io_lock.
 * The standard SM5714 property reads fresh SRAM under its own sram_lock.
 * No SM5440/companion lock may cross this supplier call.
 */
static void sm5440_startup_gauge(struct sm5440_sample *sample)
{
	union power_supply_propval value = {};
	struct power_supply *gauge;

	sample->adc_read_completed_ms = ktime_to_ms(ktime_get_boottime());
	sample->gauge_attempted = true;
	sample->gauge_uv = 0;
	sample->gauge_started_ms = ktime_to_ms(ktime_get_boottime());
	gauge = power_supply_get_by_name("sm5714-battery");
	if (!gauge) {
		sample->gauge_ret = -ENODEV;
	} else {
		sample->gauge_ret = power_supply_get_property(gauge,
					POWER_SUPPLY_PROP_VOLTAGE_NOW, &value);
		if (!sample->gauge_ret)
			sample->gauge_uv = value.intval;
		power_supply_put(gauge);
	}
	sample->gauge_completed_ms = ktime_to_ms(ktime_get_boottime());
}

#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
/* USB_TYPE labels source capabilities, not the active protocol mode.
 * Match the stable standard snapshot producer; ONLINE=1/!pps remains mandatory.
 * Linux7.2 tcpm_pd_select_pdo()/tcpm_psy_get_online(), Test273 fixed9/PD_PPS.
 */
static bool sm5440_context_pd_capable(int type)
{
	return type == POWER_SUPPLY_USB_TYPE_PD || type == POWER_SUPPLY_USB_TYPE_PD_PPS ||
		type == POWER_SUPPLY_USB_TYPE_PD_SPR_AVS ||
		type == POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS;
}

/* Readiness only: TCPM may expose fixed5V standby before its normal9V request.
 * No PDO selection/setter or physical grant here. Never wait on an APDO-only
 *9V offer, weak source, invalid snapshot or changed source epoch.
 */
static bool sm5440_context_waitable_fixed5(const struct sm5714_pd_snapshot *s)
{
	u64 now = ktime_to_ms(ktime_get_boottime());
	unsigned int i;

	if (!s->instance || !s->source_generation || !s->started_ms ||
	    now < s->completed_ms || s->completed_ms < s->started_ms ||
	    now - s->started_ms > SM5440_PASSIVE_OBSERVATION_MS ||
	    s->online != 1 || !sm5440_context_pd_capable(s->usb_type) ||
	    s->pps_contract || !s->charge_requested || s->budget_mv != 5000 ||
	    s->budget_ma < 100 || s->budget_ma > SM5714_FIXED_5V_MA ||
	    s->voltage_uv != 5000000 || s->current_ua != s->budget_ma * 1000U ||
	    !s->nr_source_pdos || s->nr_source_pdos > SM5714_SOURCE_PDO_MAX)
		return false;
	for (i = 0; i < s->nr_source_pdos; i++)
		if (pdo_type(s->source_pdos[i]) == PDO_TYPE_FIXED &&
		    pdo_fixed_voltage(s->source_pdos[i]) == 9000 &&
		    pdo_max_current(s->source_pdos[i]) >= 1000)
			return true;
	return false;
}

static void sm5440_context_publish(struct sm5440_direct *sm,
				   struct sm5440_context *context, int phase)
{
	context->phase = phase;
	mutex_lock(&sm->io_lock);
	sm->context = *context;
	mutex_unlock(&sm->io_lock);
}

static int sm5440_context_source(struct sm5440_direct *sm,
				 const struct sm5714_pd_snapshot *before,
				 struct sm5714_pd_snapshot *after, u64 lease)
{
	u64 now;
	int ret;

	if (READ_ONCE(sm->stopped) || READ_ONCE(sm->dying))
		return -ESHUTDOWN;
	ret = sm5714_pd_read_snapshot(after);
	if (ret)
		return ret;
	now = ktime_to_ms(ktime_get_boottime());
	if (!after->started_ms || now < after->completed_ms ||
	    after->completed_ms < after->started_ms ||
	    now - after->started_ms > SM5440_PASSIVE_OBSERVATION_MS)
		return -ESTALE;
	if (!after->instance || !after->source_generation || after->budget_mv != 9000 ||
	    after->budget_ma < 1000 || after->budget_ma > SM5714_FIXED_9V_MA ||
	    after->online != 1 || !sm5440_context_pd_capable(after->usb_type) ||
	    after->voltage_uv != 9000000 ||
	    after->current_ua != after->budget_ma * 1000U ||
	    !after->charge_requested || after->pps_contract)
		return -EPERM;
	if (before && (before->instance != after->instance ||
		       before->source_generation != after->source_generation ||
		       before->budget_generation != after->budget_generation))
		return -ESTALE;
	if (lease) {
		ret = sm5714_battery_switching_check(lease);
		if (ret)
			return ret;
	}
	return READ_ONCE(sm->stopped) || READ_ONCE(sm->dying) ? -ESHUTDOWN : 0;
}

static int sm5440_context_pack(struct sm5440_context *c)
{
	static const enum power_supply_property props[] = {
		POWER_SUPPLY_PROP_PRESENT, POWER_SUPPLY_PROP_HEALTH,
		POWER_SUPPLY_PROP_CAPACITY, POWER_SUPPLY_PROP_VOLTAGE_NOW,
		POWER_SUPPLY_PROP_TEMP,
	};
	struct power_supply *psy;
	union power_supply_propval value;
	int values[ARRAY_SIZE(props)] = {}, ret = 0;
	unsigned int i;

	c->pack_started_ms = ktime_to_ms(ktime_get_boottime());
	psy = power_supply_get_by_name("sm5714-battery");
	if (!psy)
		return -ENODEV;
	for (i = 0; i < ARRAY_SIZE(props); i++) {
		ret = power_supply_get_property(psy, props[i], &value);
		if (ret)
			break;
		values[i] = value.intval;
	}
	power_supply_put(psy);
	c->pack_completed_ms = ktime_to_ms(ktime_get_boottime());
	c->capacity = values[2];
	c->pack_uv = values[3];
	c->pack_decic = values[4];
	if (ret)
		return ret;
	if (!c->pack_started_ms || c->pack_completed_ms < c->pack_started_ms ||
	    c->pack_completed_ms - c->pack_started_ms > SM5440_PASSIVE_OBSERVATION_MS)
		return -ESTALE;
	if (values[0] != 1 || values[1] != POWER_SUPPLY_HEALTH_GOOD ||
	    c->capacity < 5 || c->capacity >= 80 || c->pack_uv < 3500000 ||
	    c->pack_uv >= 4300000 || c->pack_decic < 200 || c->pack_decic >= 380)
		return -EPERM;
	return 0;
}

/* Diagnostic converter, always disable/readback before returning. No core
 * charger/TCPC lock across rearm/conversion/supplier calls. Never a100ms grant.
 */
static int sm5440_context_observe(struct sm5440_direct *sm,
				  struct sm5440_sample *sample)
{
	unsigned int value;
	int ret, cleanup, err;

	memset(sample, 0, sizeof(*sample));
	ret = sm5440_adc_rearm(sm);
	if (!ret)
		ret = sm5440_sample_once(sm, sample);
	if (!ret)
		sm5440_startup_gauge(sample);
	mutex_lock(&sm->io_lock);
	cleanup = sm5440_off(sm);
	err = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	if (!cleanup)
		cleanup = err;
	err = regmap_read(sm->regmap, SM5440_ADCCNTL1, &value);
	if (!err && (value & SM5440_ADC_ENABLE))
		err = -EIO;
	if (!cleanup)
		cleanup = err;
	mutex_unlock(&sm->io_lock);
	sample->restore_error = cleanup;
	sample->completed_ms = ktime_to_ms(ktime_get_boottime());
	if (!ret)
		ret = cleanup;
	sample->valid = !ret;
	return ret;
}

static bool sm5440_context_physical(const struct sm5440_sample *sample)
{
	u64 now = ktime_to_ms(ktime_get_boottime());

	return sample->acquired_ms && now >= sample->completed_ms &&
		sample->completed_ms >= sample->acquired_ms &&
		now - sample->acquired_ms <= SM5440_PASSIVE_OBSERVATION_MS &&
		!(sample->mode_before & SM5440_MODE_MASK) &&
		!(sample->mode_after & SM5440_MODE_MASK) && sample->online &&
		!(sample->status[2] & BIT(6)) &&
		(sample->int4_wait & SM5440_ADC_READY) &&
		sample->vbus_uv >= 8500000 && sample->vbus_uv <= 9500000 &&
		!sample->ibus_ua && sample->die_decic >= 225 && sample->die_decic < 420 &&
		sample->vbat_uv >= 2500000 && sample->vbat_uv <= 4600000 &&
		!sm5440_decode_faults(sample->status, false, 0);
}

/* Preserve a preexisting OFF latch, never mask live or repeated REVBLK. The
 * original and both new confirmations remain diagnostic evidence only.
 */
static bool sm5440_context_inactive(const struct sm5440_sample *sample)
{
	return sm5440_context_physical(sample) && sample->faults == SM5440_FAULT_REVBLK &&
		sm5440_decode_faults(sample->int_before, false, 0) == SM5440_FAULT_REVBLK;
}

static int sm5440_context_restore_settings(struct sm5440_direct *sm,
					  struct sm5440_control *controls)
{
	int ret;

	mutex_lock(&sm->io_lock);
	ret = sm5440_control_restore(sm->regmap, controls);
	mutex_unlock(&sm->io_lock);
	return ret;
}

static int sm5440_fixed_context_cycle(struct sm5440_direct *sm,
				     struct sm5440_sample *sample)
{
	struct sm5440_context c = {};
	struct sm5714_pd_snapshot fixed = {}, after = {};
	struct sm5440_sample *confirm;
	bool waitable;
	int ret = -ENODATA, i;

	mutex_lock(&sm->io_lock);
	if (sm->context_attempted) {
		mutex_unlock(&sm->io_lock);
		return -EALREADY;
	}
	sm->context_attempted = true;
	mutex_unlock(&sm->io_lock);
	c.started_ms = ktime_to_ms(ktime_get_boottime());
	sm5440_context_publish(sm, &c, 1);
	/* Only initializing state or source-bound5V standby gets readiness waits.
	 * No register/charging mutation; no retry after an actual admission/fault.
	 */
	for (i = 0; i < 40; i++) {
		ret = sm5440_context_source(sm, NULL, &fixed, 0);
		c.readiness_checks++;
		if (ktime_to_ms(ktime_get_boottime()) < c.started_ms ||
		    ktime_to_ms(ktime_get_boottime()) - c.started_ms > 4000) {
			ret = -ETIMEDOUT;
			break;
		}
		waitable = ret == -EPERM && sm5440_context_waitable_fixed5(&fixed);
		if ((!ret || waitable) && c.standby.instance &&
		    (c.standby.instance != fixed.instance ||
		     c.standby.source_generation != fixed.source_generation)) {
			ret = -ESTALE;
			break;
		}
		if (!c.standby.instance && waitable)
			c.standby = fixed;
		if (!waitable && ret != -ENODEV && ret != -ENODATA &&
		    ret != -EAGAIN && ret != -EBUSY)
			break;
		if (READ_ONCE(sm->stopped) || READ_ONCE(sm->dying)) {
			ret = -ESHUTDOWN;
			break;
		}
		msleep(100);
	}
	if (i == 40 && c.standby.instance)
		ret = -ETIMEDOUT;
	if (ret)
		goto done;
	c.instance = fixed.instance;
	c.source_generation = fixed.source_generation;
	c.budget_generation = fixed.budget_generation;
	c.budget_ma = fixed.budget_ma;
	sm5440_context_publish(sm, &c, 2);
	ret = sm5440_context_pack(&c);
	if (ret)
		goto done;
	sm5440_context_publish(sm, &c, 3);
	ret = sm5440_context_observe(sm, &c.initial);
	if (!ret && !sm5440_context_physical(&c.initial))
		ret = -ERANGE;
	if (ret)
		goto done;
	c.before = c.initial;
	if (c.initial.faults) {
		if (!sm5440_context_inactive(&c.initial)) {
			ret = -EIO;
			goto done;
		}
		sm5440_context_publish(sm, &c, 4);
		for (i = 0; i < 2; i++) {
			confirm = i ? &c.before : &c.confirmation;
			ret = sm5440_context_source(sm, &fixed, &after, 0);
			if (!ret)
				ret = sm5440_context_observe(sm, confirm);
			if (!ret && (confirm->faults || !sm5440_context_physical(confirm) ||
				     confirm->cntl2 != c.initial.cntl2 ||
				     confirm->vbuscntl != c.initial.vbuscntl ||
				     confirm->vbatcntl != c.initial.vbatcntl ||
				     confirm->prtncntl != c.initial.prtncntl))
				ret = -EIO;
			if (ret)
				goto done;
		}
		c.inactive_revblk = true;
	}
	ret = sm5440_context_pack(&c);
	if (!ret)
		ret = sm5440_context_source(sm, &fixed, &after, 0);
	if (!ret && (!sm5440_context_physical(&c.before) || c.before.faults))
		ret = -ESTALE;
	if (ret)
		goto done;
	sm5440_context_publish(sm, &c, 5);
	ret = sm5714_battery_switching_acquire(&c.lease);
	/* Nonzero even on error means inhibited/diagnostic, not authorization. */
	c.lease_retained = !!c.lease;
	if (!ret && !c.lease)
		ret = -EIO;
	if (ret)
		goto done;
	sm5440_context_publish(sm, &c, 6);
	ret = sm5440_context_source(sm, &fixed, &after, c.lease);
	if (!ret)
		ret = sm5440_context_observe(sm, &c.handoff);
	if (!ret && (c.handoff.faults || !sm5440_context_physical(&c.handoff)))
		ret = -EIO;
	if (!ret)
		ret = sm5440_context_pack(&c);
	if (!ret)
		ret = sm5440_context_source(sm, &fixed, &after, c.lease);
	if (!ret && !sm5440_context_physical(&c.handoff))
		ret = -ESTALE;
	if (ret)
		goto done;
	sm5440_context_publish(sm, &c, 7);
	mutex_lock(&sm->io_lock);
	if (READ_ONCE(sm->stopped) || READ_ONCE(sm->dying))
		ret = -ESHUTDOWN;
	else
		ret = sm5440_control_prepare(sm->regmap, c.budget_ma, &c.controls);
	mutex_unlock(&sm->io_lock);
	if (ret)
		goto done;
	ret = sm5440_context_source(sm, &fixed, &after, c.lease);
	if (!ret && !sm5440_context_physical(&c.handoff))
		ret = -ESTALE;
	if (ret)
		goto cleanup;
	sm5440_context_publish(sm, &c, 8);
	ret = sm5440_condition_cycle(sm, sample);
	if (!ret) {
		sm5440_startup_gauge(sample);
		sample->completed_ms = ktime_to_ms(ktime_get_boottime());
		if (!sm5440_context_physical(sample) || sample->faults ||
		    sample->gauge_ret || sample->vbat_uv < 3500000 ||
		    sample->vbat_uv >= 4300000 ||
		    sample->gauge_uv < 3500000 || sample->gauge_uv >= 4300000 ||
		    abs((int)sample->vbat_uv - sample->gauge_uv) > 100000)
			ret = -ERANGE;
	}
	if (!ret)
		ret = sm5440_context_pack(&c);
	if (!ret)
		ret = sm5440_context_source(sm, &fixed, &after, c.lease);
cleanup:
	sm5440_context_publish(sm, &c, 9);
	/* No second ENHIZ cleanup attempt in this worker. Unknown condition
	 * restoration prevents claiming/restoring a complete settings witness.
	 */
	if (READ_ONCE(sm->enhiz_restore_pending))
		c.cleanup_error = sample->restore_error ? sample->restore_error : -EIO;
	else
		c.cleanup_error = sm5440_context_restore_settings(sm, &c.controls);
	if (!ret)
		ret = c.cleanup_error;
done:
	c.error = ret;
	c.completed_ms = ktime_to_ms(ktime_get_boottime());
	/* Test314 already makes one cleanup attempt on prepare failure. Retain
	 * pending/error, do not silently retry it here or release switching.
	 */
	if (!c.cleanup_error)
		c.cleanup_error = c.controls.restore_error;
	if (!c.cleanup_error)
		c.cleanup_error = c.initial.restore_error;
	if (!c.cleanup_error)
		c.cleanup_error = c.confirmation.restore_error;
	if (!c.cleanup_error)
		c.cleanup_error = c.before.restore_error;
	if (!c.cleanup_error)
		c.cleanup_error = c.handoff.restore_error;
	sm5440_context_publish(sm, &c, ret ? c.phase : 10);
	return ret;
}
#endif

#ifdef CONFIG_SM5440_ADC_TIMING_TEST
static bool sm5440_timing_same_source(const struct sm5714_pd_snapshot *a,
				      const struct sm5714_pd_snapshot *b)
{
	return a->instance == b->instance &&
		a->source_generation == b->source_generation &&
		a->budget_generation == b->budget_generation &&
		a->budget_mv == b->budget_mv && a->budget_ma == b->budget_ma;
}

static int sm5440_timing_facts(struct sm5714_pd_snapshot *source,
			      struct sm5714_pack_snapshot *pack)
{
	struct sm5714_pd_snapshot after;
	u64 now;
	int ret = sm5714_pd_read_snapshot(source);

	if (!ret)
		ret = sm5714_battery_read_pack(0, pack);
	if (!ret)
		ret = sm5714_pd_read_snapshot(&after);
	if (ret)
		return ret;
	now = ktime_to_ms(ktime_get_boottime());
	if (!source->instance || !source->source_generation ||
	    !source->budget_generation || !sm5440_timing_same_source(source, &after) ||
	    source->online != 1 || after.online != 1 || source->pps_contract ||
	    after.pps_contract || !source->charge_requested || !after.charge_requested ||
	    !source->budget_ma ||
	    (source->budget_mv != 5000 && source->budget_mv != 9000) ||
	    source->budget_ma > (source->budget_mv == 5000 ?
		SM5714_FIXED_5V_MA : SM5714_FIXED_9V_MA))
		return -ESTALE;
	if (!pack->instance || !pack->state_generation || pack->switching_lease ||
	    !pack->battery_present || !pack->attached || !pack->thermal_normal ||
	    !pack->typec_owned || !pack->typec_charge || pack->pps_contract ||
	    pack->health != POWER_SUPPLY_HEALTH_GOOD || pack->capacity < 5 ||
	    pack->capacity >= 80 || pack->voltage_uv < 3500000 ||
	    pack->voltage_uv >= 4300000 || pack->pack_decic < 200 ||
	    pack->pack_decic >= 380 || pack->typec_mv != source->budget_mv ||
	    pack->typec_ma != source->budget_ma)
		return -ERANGE;
	if (!source->started_ms || source->started_ms > source->completed_ms ||
	    source->completed_ms > now || now - source->started_ms > 500 ||
	    !pack->started_ms || pack->started_ms > pack->completed_ms ||
	    pack->completed_ms > now || now - pack->started_ms > 500 ||
	    !after.started_ms || after.started_ms > after.completed_ms ||
	    after.completed_ms > now || now - after.started_ms > 500)
		return -ESTALE;
	return 0;
}

static void sm5440_timing_cycle(struct sm5440_direct *sm)
{
	struct sm5440_timing_context c = {};
	int ret;

	c.attempted = true;
	/* Existing startup/admission and frozen converter have already passed.
	 * Suppliers and waits are always outside io_lock. No lease/PD setters.
	 */
	/* TCPM may still be attaching when the first healthy OFF sample arrives.
	 * Only EAGAIN/EBUSY permit bounded read-only readiness retries, before any new
	 * converter write. A source/pack fault is not retried or reclassified.
	 */
	for (c.readiness_checks = 1; c.readiness_checks <= 20; c.readiness_checks++) {
		if (READ_ONCE(sm->stopped)) {
			ret = -ESHUTDOWN;
			break;
		}
		ret = sm5440_timing_facts(&c.source[0], &c.pack[0]);
		if (ret && !c.first_readiness_error)
			c.first_readiness_error = ret;
		if ((ret != -EAGAIN && ret != -EBUSY) || c.readiness_checks == 20)
			break;
		msleep(100);
	}
	c.admission_error = ret;
	if (ret)
		goto publish;
	ret = sm5440_adc_rearm(sm);
	if (ret)
		goto publish;
	mutex_lock(&sm->io_lock);
	if (READ_ONCE(sm->stopped))
		ret = -ESHUTDOWN;
	else
		ret = sm5440_timing_begin(sm->regmap, &c.acquisition);
	mutex_unlock(&sm->io_lock);
	while (!ret) {
		msleep(5);
		mutex_lock(&sm->io_lock);
		if (READ_ONCE(sm->stopped))
			ret = -ESHUTDOWN;
		else
			ret = sm5440_timing_step(sm->regmap, &c.acquisition);
		mutex_unlock(&sm->io_lock);
	}
	if (ret == 1)
		ret = 0;
	mutex_lock(&sm->io_lock);
	if (ret) {
		/* An unexpected mode/fault must get one checked OFF attempt before
		 * converter restoration; retain the original error and OFF outcome.
		 */
		c.off_attempted = true;
		c.off_error = sm5440_off(sm);
	}
	ret = sm5440_timing_finish(sm->regmap, &c.acquisition, ret);
	mutex_unlock(&sm->io_lock);
	if (!ret) {
		ret = sm5440_timing_facts(&c.source[1], &c.pack[1]);
		if (!ret && (!sm5440_timing_same_source(&c.source[0], &c.source[1]) ||
			    c.pack[0].instance != c.pack[1].instance ||
			    c.pack[0].state_generation != c.pack[1].state_generation))
			ret = -ESTALE;
		c.exit_error = ret;
	}
publish:
	mutex_lock(&sm->io_lock);
	/* A late stop still refuses, even after converter cleanup completed. */
	if (!ret && READ_ONCE(sm->stopped))
		ret = -ESHUTDOWN;
	if (ret && !c.acquisition.error)
		c.acquisition.error = ret;
	sm->timing = c;
	if (ret) {
		sm->fault = true;
		dev_err(sm->dev, "OFF continuous ADC diagnostic stopped: %d; cleanup=%d\n",
			ret, c.acquisition.cleanup_error);
	}
	mutex_unlock(&sm->io_lock);
}
#endif

static void sm5440_poll(struct work_struct *work)
{
	struct sm5440_direct *sm = container_of(to_delayed_work(work),
					       struct sm5440_direct, work);
	struct sm5440_sample sample = {};
	int ret;

	if (READ_ONCE(sm->stopped) || READ_ONCE(sm->fault))
		return;
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	ret = sm5440_fixed_context_cycle(sm, &sample);
#else
	ret = sm5440_adc_rearm(sm);
	if (!ret)
		ret = sm5440_sample_once(sm, &sample);
#endif
	if (!ret && (!sm->initial_sample_done || sm->startup_confirmations)) {
#ifndef CONFIG_SM5440_ADC_CONDITION_TEST
		sm5440_startup_gauge(&sample);
#endif
		dev_info(sm->dev,
			 "startup voltage pair seq=%llu ADC-start=%llums ADC-read=%llums VBAT=%uuV gauge-start=%llums gauge-end=%llums gauge-ret=%d gauge=%duV\n",
			 (unsigned long long)sample.acquisition_seq,
			 (unsigned long long)sample.acquired_ms,
			 (unsigned long long)sample.adc_read_completed_ms,
			 sample.vbat_uv,
			 (unsigned long long)sample.gauge_started_ms,
			 (unsigned long long)sample.gauge_completed_ms,
			 sample.gauge_ret, sample.gauge_uv);
	}
	mutex_lock(&sm->io_lock);
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	sm->condition_sample = sample;
#endif
	sm->last_sample_error = ret;
	if (ret) {
		sm->sample.valid = false;
		if (ret != -ESHUTDOWN) {
			sm->fault = true;
			/* Best effort OFF is not proof when I2C has failed. */
			dev_err(sm->dev, "passive ADC fault %d; OFF verification=%d\n",
				ret, sm5440_off(sm));
			regmap_update_bits(sm->regmap, SM5440_ADCCNTL1,
					   SM5440_ADC_ENABLE, 0);
		}
	} else {
		/* A suspect startup latch is UNKNOWN until two new safe samples.
		 * Failure is permanent; the exemption is consumed once per probe.
		 */
		if (!sm->initial_sample_done && sm5440_startup_revblk(&sample)) {
			sm->startup_sample = sample;
			sm->startup_stamp = jiffies;
			sm->startup_confirmations = 2;
			sm->startup_deadline = jiffies + msecs_to_jiffies(5000);
			dev_warn(sm->dev, "passive startup REVBLK awaiting two fresh confirmations\n");
		} else if (sm->startup_confirmations) {
			if (time_after(jiffies, sm->startup_deadline) ||
			    !sm5440_startup_matches(&sample, &sm->startup_sample)) {
				sm->fault = true;
				dev_err(sm->dev, "passive startup confirmation failed\n");
			} else {
				sm->startup_confirmations--;
				if (!sm->startup_confirmations)
					dev_info(sm->dev, "passive startup REVBLK confirmed inactive; event retained\n");
			}
		}
		sm->initial_sample_done = true;
		sample.valid = true;
		sample.stamp = jiffies;
		sample.completed_ms = ktime_to_ms(ktime_get_boottime());
		sm->sample = sample;
		if (sample.faults) {
			/* Reads consume INT. Only the initial qualified REVBLK may
			 * await confirmation; all other faults latch until unbind.
			 * startup_sample retains the original event independently.
			 */
			if (!sm->startup_confirmations ||
			    !sm5440_startup_revblk(&sample))
				sm->fault = true;
			dev_warn_ratelimited(sm->dev,
				"passive fault bitmap=%#x INT=%*ph STATUS=%*ph INT4-disable=%02x INT4-wait=%02x mode=%02x/%02x CNTL2=%02x VBUSCNTL=%02x VBATCNTL=%02x PRTNCNTL=%02x ADC=%*ph VBUS=%uuV VBAT=%uuV IBUS=%uuA die=%d deciC\n",
				sample.faults, 4, sample.int_before, 4, sample.status,
				sample.int4_after_disable, sample.int4_wait,
				sample.mode_before, sample.mode_after, sample.cntl2,
				sample.vbuscntl, sample.vbatcntl, sample.prtncntl,
				11, sample.adc, sample.vbus_uv, sample.vbat_uv,
				sample.ibus_ua, sample.die_decic);
		}
		dev_dbg(sm->dev, "passive VBUS=%uuV VBAT=%uuV IBUS=%uuA die=%d deciC faults=%#x\n",
			sample.vbus_uv, sample.vbat_uv, sample.ibus_ua,
			sample.die_decic, sample.faults);
	}
	WRITE_ONCE(sm->sample_seq, sm->sample_seq + 1);
	mutex_unlock(&sm->io_lock);
	wake_up_all(&sm->request_wait);
	power_supply_changed(sm->psy);
#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	if (!READ_ONCE(sm->stopped) && !READ_ONCE(sm->fault) &&
	    sm->initial_sample_done && !sm->startup_confirmations) {
		sm5440_timing_cycle(sm);
		return; /* One experiment per bind; no second conversion/retry. */
	}
#endif
#ifndef CONFIG_SM5440_ADC_CONDITION_TEST
	if (!READ_ONCE(sm->stopped) && !READ_ONCE(sm->fault))
		schedule_delayed_work(&sm->work, msecs_to_jiffies(1000));
#endif
}

static int sm5440_get_property(struct power_supply *psy,
			       enum power_supply_property prop,
			       union power_supply_propval *val)
{
	struct sm5440_direct *sm = power_supply_get_drvdata(psy);
	struct sm5440_sample sample;
	bool fault, startup_pending;

	mutex_lock(&sm->io_lock);
	sample = sm->sample;
	fault = sm->fault;
	startup_pending = sm->startup_confirmations != 0;
	mutex_unlock(&sm->io_lock);
	if (prop == POWER_SUPPLY_PROP_STATUS) {
		val->intval = POWER_SUPPLY_STATUS_NOT_CHARGING;
		return 0;
	}
	if (prop == POWER_SUPPLY_PROP_HEALTH) {
		if (fault || (!startup_pending && sample.faults))
			val->intval = POWER_SUPPLY_HEALTH_UNSPEC_FAILURE;
		else if (!startup_pending && sample.valid)
			val->intval = POWER_SUPPLY_HEALTH_GOOD;
		else
			val->intval = POWER_SUPPLY_HEALTH_UNKNOWN;
		return 0;
	}
	if (startup_pending || !sample.valid ||
	    time_after(jiffies, sample.stamp + msecs_to_jiffies(2500)))
		return -ENODATA;
	switch (prop) {
	case POWER_SUPPLY_PROP_ONLINE:
		val->intval = sample.online;
		break;
	case POWER_SUPPLY_PROP_VOLTAGE_NOW:
		val->intval = sample.vbus_uv;
		break;
	case POWER_SUPPLY_PROP_CURRENT_NOW:
		val->intval = sample.ibus_ua;
		break;
	case POWER_SUPPLY_PROP_TEMP:
		val->intval = sample.die_decic;
		break;
	default:
		return -EINVAL;
	}
	return 0;
}

static enum power_supply_property sm5440_props[] = {
	POWER_SUPPLY_PROP_STATUS, POWER_SUPPLY_PROP_HEALTH, POWER_SUPPLY_PROP_ONLINE,
	POWER_SUPPLY_PROP_VOLTAGE_NOW, POWER_SUPPLY_PROP_CURRENT_NOW,
	POWER_SUPPLY_PROP_TEMP,
};

static const struct power_supply_desc sm5440_desc = {
	.name = "sm5440-passive",
	.type = POWER_SUPPLY_TYPE_MAINS,
	/* OFF-only diagnostic cache can stop on fault or become stale. It is
	 * not a continuously available thermal sensor. Keep TEMP/ENODATA and
	 * fault gates; avoid power_supply's automatic tripless thermal zone.
	 * Pack temperature remains the independent SM5714/IIO safety input.
	 */
	.no_thermal = true,
	.properties = sm5440_props,
	.num_properties = ARRAY_SIZE(sm5440_props),
	.get_property = sm5440_get_property,
};

static int sm5440_quiesce(struct sm5440_direct *sm)
{
	int ret, adc_ret;

	/* Serialize stop with new-request scheduling, never hold across drain. */
	mutex_lock(&sm->io_lock);
	WRITE_ONCE(sm->stopped, true);
	WRITE_ONCE(sm->request_epoch, sm->request_epoch + 1);
	sm->sample.valid = false;
	mutex_unlock(&sm->io_lock);
	wake_up_all(&sm->request_wait);
	cancel_delayed_work_sync(&sm->work);
	mutex_lock(&sm->io_lock);
	sm->sample.valid = false;
	/* Never carry unconfirmed startup evidence across suspend/unbind. */
	if (sm->startup_confirmations)
		sm->fault = true;
	ret = sm5440_off(sm);
	adc_ret = regmap_update_bits(sm->regmap, SM5440_ADCCNTL1, SM5440_ADC_ENABLE, 0);
	mutex_unlock(&sm->io_lock);
	if (ret || adc_ret)
		dev_err(sm->dev, "passive teardown cannot verify OFF/ADC-off: %d/%d\n", ret, adc_ret);
	return ret ? ret : adc_ret;
}

static void sm5440_stop(void *data)
{
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	struct sm5440_direct *sm = data;

#endif
	sm5440_quiesce(data);
#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	if (sm5440_condition_restore(sm, &sm->condition_sample))
		dev_err(sm->dev, "ADC condition teardown cannot verify restoration\n");
	else if (sm5440_context_restore_settings(sm, &sm->context.controls))
		dev_err(sm->dev, "fixed context teardown cannot restore settings\n");
#endif
}

static int sm5440_suspend(struct device *dev)
{
	struct sm5440_direct *sm = dev_get_drvdata(dev);

#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	int ret = sm5440_quiesce(sm);
	int restore = sm5440_condition_restore(sm, &sm->condition_sample);
	int settings = restore ? restore :
		sm5440_context_restore_settings(sm, &sm->context.controls);

	if (ret || settings)
		return ret ? ret : settings;
	/* The diagnostic cannot release switching from its500ms samples. */
	return sm->context.lease_retained ? -EBUSY : 0;
#else
	return sm5440_quiesce(sm);
#endif
}

static int sm5440_resume(struct device *dev)
{
	struct sm5440_direct *sm = dev_get_drvdata(dev);
	int ret;

#ifdef CONFIG_SM5440_ADC_TIMING_TEST
	/* A timing diagnostic is not rearmed after suspend or failure. */
	if (sm->timing.attempted)
		return -EOPNOTSUPP;
#endif

#ifdef CONFIG_SM5440_ADC_CONDITION_TEST
	/* One experiment per bind, never rearm a second one on resume. */
	if (sm->condition_attempted)
		return -EOPNOTSUPP;
	if (sm->context_attempted)
		return -EOPNOTSUPP;
#endif
	mutex_lock(&sm->io_lock);
	ret = sm5440_off(sm);
	mutex_unlock(&sm->io_lock);
	if (ret || READ_ONCE(sm->fault))
		return ret ? ret : -EIO;
	WRITE_ONCE(sm->stopped, false);
	schedule_delayed_work(&sm->work, 0);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(sm5440_pm, sm5440_suspend, sm5440_resume);

static int sm5440_probe(struct i2c_client *client)
{
	struct sm5440_direct *sm;
	struct power_supply_config config = {};
	unsigned int id, mode;
	int ret;

	sm = devm_kzalloc(&client->dev, sizeof(*sm), GFP_KERNEL);
	if (!sm)
		return -ENOMEM;
	sm->dev = &client->dev;
	sm->regmap = devm_regmap_init_i2c(client, &sm5440_regmap);
	if (IS_ERR(sm->regmap))
		return PTR_ERR(sm->regmap);
	mutex_init(&sm->io_lock);
	atomic_set(&sm->request_users, 0);
	atomic_set(&sm->request_busy, 0);
	init_waitqueue_head(&sm->request_wait);
	init_waitqueue_head(&sm->users_wait);
	INIT_DELAYED_WORK(&sm->work, sm5440_poll);
	i2c_set_clientdata(client, sm);
	ret = regmap_read(sm->regmap, SM5440_DEVICEID, &id);
	if (ret || (id & 0xf) != 1)
		return dev_err_probe(sm->dev, ret ? ret : -ENODEV, "invalid SM5440 identity\n");
	ret = regmap_read(sm->regmap, SM5440_CNTL5, &mode);
	if (ret || (mode & SM5440_MODE_MASK))
		return dev_err_probe(sm->dev, ret ? ret : -EBUSY, "passive probe requires pump OFF\n");
	config.drv_data = sm;
	sm->psy = devm_power_supply_register(sm->dev, &sm5440_desc, &config);
	if (IS_ERR(sm->psy))
		return PTR_ERR(sm->psy);
	/* Register stop after supplies so work drains before their memory is freed. */
	ret = devm_add_action_or_reset(sm->dev, sm5440_stop, sm);
	if (ret)
		return ret;
	sm5440_debugfs_init(sm);
	/* Added last: unpublish/drain all readers before debugfs/stop/free. */
	ret = devm_add_action_or_reset(sm->dev, sm5440_unpublish, sm);
	if (ret)
		return ret;
#ifndef CONFIG_SM5440_ADC_CONDITION_TEST
	ret = sm5440_publish(sm);
	if (ret)
		return dev_err_probe(sm->dev, ret, "SM5440 companion already bound\n");
#endif
	schedule_delayed_work(&sm->work, 0);
	dev_info(sm->dev, "passive SM5440 revision %u; pump activation unavailable\n", id >> 4);
	return 0;
}

static void sm5440_shutdown(struct i2c_client *client)
{
	sm5440_stop(i2c_get_clientdata(client));
}

static const struct of_device_id sm5440_match[] = {
	{ .compatible = "siliconmitus,sm5440" },
	{ }
};
MODULE_DEVICE_TABLE(of, sm5440_match);

static struct i2c_driver sm5440_driver = {
	.driver = {
		.name = "sm5440-passive",
		.of_match_table = sm5440_match,
		.pm = pm_sleep_ptr(&sm5440_pm),
	},
	.probe = sm5440_probe,
	.shutdown = sm5440_shutdown,
};
module_i2c_driver(sm5440_driver);
MODULE_DESCRIPTION("SM-X710 passive SM5440 ID/ADC/fault monitor; pump OFF only");
MODULE_LICENSE("GPL");
