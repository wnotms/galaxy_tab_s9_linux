// SPDX-License-Identifier: GPL-2.0-only
/* Checked ADC/current/fault -> actual OFF, not qualified analog protection.
 * Linked by the inactive native session; see SM5440_ACTIVE_SUPERVISOR.md.
 * No PD policy, native activation grant or ON operation.
 */
#include <linux/compiler.h>
#include <linux/errno.h>
#include <linux/ktime.h>
#include <linux/power_supply.h>
#include <linux/regmap.h>

#include "sm5440-supervisor.h"
#include "sm5440-hw.h"
#include "sm5714-pd-policy.h"

static int sm5440_supervisor_shutdown(struct regmap *map, struct sm5440_supervisor *s,
				      int error)
{
	struct sm5440_actuator *a = s->actuator;

	if (s->stopped)
		return s->operation_error;
	s->stopped = true;
	s->enabled = false;
	if (!s->operation_error)
		s->operation_error = error;
	/* OFF has priority over ADC cleanup. Neither helper retries uncertain I/O. */
	if (a->mode_possible || a->controls.pending || a->watchdog.owned || a->enhiz_owned)
		s->actuator_error = sm5440_actuator_stop(map, a);
	if (s->adc.state == SM5440_CONVERSION_REARM || s->adc.state == SM5440_CONVERSION_WAIT ||
	    s->adc.state == SM5440_CONVERSION_MEASURED ||
	    (s->adc.state == SM5440_CONVERSION_FAULT && s->adc.owned && !s->adc.cleanup_attempted))
		sm5440_conversion_cancel(map, &s->adc);
	s->converter_error = s->adc.cleanup_error;
	s->sampling = false;
	s->hardware_quiesced = a->off_verified && !a->mode_possible && !a->controls.pending &&
		!a->watchdog.owned && !a->enhiz_owned && !s->actuator_error &&
		!s->adc.owned && !s->converter_error &&
		(!s->adc.requested_ms || s->adc.adc_off_verified);
	return s->operation_error;
}

static int sm5440_supervisor_guard(struct sm5440_supervisor *s,
				   const struct x710_charge_facts *f,
				   const struct sm5714_pd_snapshot *p)
{
	struct sm5440_actuator *a = s->actuator;
	u64 now = ktime_to_ms(ktime_get_boottime());
	unsigned int i;
	bool offer = false;

	if (!s->enabled || !a->enabled || !a->attempted || a->cleanup_attempted ||
	    !a->mode_possible || a->off_verified || a->operation_error || a->cleanup_error ||
	    !a->lease || !a->switching_inhibited || !a->generation || !a->epoch ||
	    READ_ONCE(*a->generation) != a->epoch || f->epoch != a->epoch)
		return -ECANCELED;
	if (!now || now < s->last_clock_ms)
		return -ETIME;
	s->last_clock_ms = now;
	if (!s->last_good_ms || now < s->last_good_ms ||
	    now - s->last_good_ms > X710_MONITOR_DEADLINE_MS)
		return -ETIMEDOUT;
	if (!f->observed_ms || f->observed_ms > now ||
	    now - f->observed_ms > X710_FACTS_MAX_AGE_MS - X710_MONITOR_DEADLINE_MS ||
	    !p->started_ms || p->started_ms > p->completed_ms || p->completed_ms > now ||
	    now - p->started_ms > X710_FACTS_MAX_AGE_MS - X710_MONITOR_DEADLINE_MS)
		return -ESTALE;
	if (!x710_charge_eligible(f) || f->die_decic >= 420 ||
	    s->target_mv < 8200 || s->target_mv > 10500 || s->target_mv % 20 ||
	    s->target_ma < 1000 || s->target_ma > 1800 || s->target_ma % 50 ||
	    s->target_mv < f->apdo_min_mv || s->target_mv > f->apdo_max_mv ||
	    s->target_ma > f->apdo_ma)
		return -EPERM;
	if (!a->instance || !a->source_generation || !a->budget_generation ||
	    p->instance != a->instance || p->source_generation != a->source_generation ||
	    p->budget_generation != a->budget_generation || p->online != 2 ||
	    !p->pps_contract || !p->charge_requested ||
	    (p->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS &&
	     p->usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS) ||
	    p->voltage_uv != (int)(s->target_mv * 1000) ||
	    p->current_ua != (int)(s->target_ma * 1000) ||
	    p->budget_mv != s->target_mv || p->budget_ma != s->target_ma ||
	    !p->nr_source_pdos || p->nr_source_pdos > SM5714_SOURCE_PDO_MAX)
		return -EPERM;
	for (i = 0; i < p->nr_source_pdos; i++)
		if (sm5714_validate_pps_request(p->source_pdos[i],
			RDO_PROG(i + 1, s->target_mv, s->target_ma, 0)))
			offer = true;
	if (!offer || a->controls.state != SM5440_CONTROL_PREPARED ||
	    !a->controls.pending || a->controls.operation_error || a->controls.restore_error ||
	    a->watchdog.state != SM5440_WATCHDOG_ARMED || !a->watchdog.owned ||
	    a->watchdog.epoch != a->epoch || a->watchdog.operation_error ||
	    !a->watchdog.serviced_ms || a->watchdog.serviced_ms > now ||
	    now - a->watchdog.serviced_ms > SM5440_WATCHDOG_SERVICE_MS)
		return -EPERM;
	return 0;
}

static int sm5440_supervisor_settings(struct regmap *map, struct sm5440_supervisor *s)
{
	static const u8 regs[] = { 0x16, 0x14, 0x12 };
	static const u8 masks[] = { 0x7f, 0x3f, 0x1f };
	static const u8 witnesses[] = { 0x0c, 0x0d, 0x0e, 0x0f, 0x11,
				      0x13, 0x15, 0x19, 0x1a, 0x1b };
	struct sm5440_actuator *a = s->actuator;
	unsigned int value, khz;
	u8 target[3];
	int i, ret;

	if (!a->controls.witness_valid || a->controls.attempted != 7 ||
	    a->watchdog.before != a->controls.witness[0])
		return -EPERM;
	khz = s->target_ma <= 1100 ? 450 : s->target_ma <= 1700 ? 650 : 850;
	target[0] = sm5440_ibus_code(s->target_ma);
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
		/* Active ENHIZ is cleared, unlike the saved attached/OFF witness. */
		u8 expected = i == 0 ? a->watchdog.expected : i == 4 ?
			a->cntl6_before & ~SM5440_ENHIZ : a->controls.witness[i];

		ret = regmap_read(map, witnesses[i], &value);
		if (!ret && value != expected)
			ret = -EIO;
		if (ret)
			return ret;
	}
	return 0;
}

int sm5440_supervisor_begin(struct regmap *map, struct sm5440_supervisor *s,
			    const struct x710_charge_facts *f,
			    const struct sm5714_pd_snapshot *p)
{
	int ret;

	if (!map || !s || !s->actuator)
		return -EINVAL;
	if (!f || !p)
		return sm5440_supervisor_shutdown(map, s, -EINVAL);
	if (s->stopped)
		return s->operation_error;
	if (s->sampling)
		return -EALREADY;
	if (!s->started) {
		s->started = true;
		s->last_good_ms = s->actuator->last_clock_ms; /* post-ON guard timestamp */
	}
	ret = sm5440_supervisor_guard(s, f, p);
	if (!ret && s->samples == ~0ULL)
		ret = -EOVERFLOW;
	if (ret)
		return sm5440_supervisor_shutdown(map, s, ret);
	s->adc = (struct sm5440_conversion) {
		.enabled = true, .running = true, .defer_cleanup = true,
		.epoch = s->actuator->epoch,
		.generation = s->actuator->generation,
	};
	s->sampling = true;
	ret = sm5440_conversion_begin(map, &s->adc);
	return ret == -EINPROGRESS ? ret : sm5440_supervisor_shutdown(map, s, ret);
}

int sm5440_supervisor_advance(struct regmap *map, struct sm5440_supervisor *s,
			      const struct x710_charge_facts *f,
			      const struct sm5714_pd_snapshot *p)
{
	u64 now;
	int ret;

	if (!map || !s || !s->actuator)
		return -EINVAL;
	if (!f || !p)
		return sm5440_supervisor_shutdown(map, s, -EINVAL);
	if (s->stopped)
		return s->operation_error;
	if (!s->sampling)
		return -EALREADY;
	ret = sm5440_supervisor_guard(s, f, p);
	if (!ret)
		ret = sm5440_conversion_advance(map, &s->adc);
	if (ret == -EINPROGRESS && s->adc.state != SM5440_CONVERSION_MEASURED)
		return ret;
	if (ret && ret != -EINPROGRESS)
		return sm5440_supervisor_shutdown(map, s, ret);
	if (s->adc.state != SM5440_CONVERSION_MEASURED || !s->adc.data_acquired ||
	    s->adc.faults || s->adc.vbat_uv < 3500000 || s->adc.vbat_uv >= 4300000 ||
	    s->adc.vbus_uv < (s->target_mv - 100) * 1000 ||
	    s->adc.vbus_uv > (s->target_mv + 100) * 1000 ||
	    s->adc.vbus_uv > 10500000 || s->adc.ibus_ua > s->target_ma * 1000 ||
	    s->adc.die_decic >= 420)
		return sm5440_supervisor_shutdown(map, s, -ERANGE);
	ret = sm5440_supervisor_guard(s, f, p);
	if (!ret)
		ret = sm5440_conversion_finish(map, &s->adc);
	if (!ret)
		ret = sm5440_supervisor_settings(map, s);
	if (!ret)
		ret = sm5440_supervisor_guard(s, f, p);
	if (!ret) {
		now = ktime_to_ms(ktime_get_boottime());
		ret = sm5440_watchdog_service(map, &s->actuator->watchdog, s->actuator->epoch, now);
	}
	if (!ret)
		ret = sm5440_supervisor_guard(s, f, p);
	if (ret)
		return sm5440_supervisor_shutdown(map, s, ret);
	s->last_good_ms = s->last_clock_ms;
	s->samples++;
	s->sampling = false;
	return 0;
}

int sm5440_supervisor_cancel(struct regmap *map, struct sm5440_supervisor *s)
{
	if (!map || !s || !s->actuator)
		return -EINVAL;
	return sm5440_supervisor_shutdown(map, s, -ECANCELED);
}
