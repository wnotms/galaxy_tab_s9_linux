/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_SUPERVISOR_H
#define _SM5440_SUPERVISOR_H

#include "sm5440-actuator.h"
#include "sm5440-conversion.h"

/* Offline only, no worker/Kbuild/activation. Caller serializes I/O, source
 * snapshots and cancellation generation; no charger/TCPM lock across waits.
 */
struct sm5440_supervisor {
	struct sm5440_actuator *actuator;
	struct sm5440_conversion adc;
	u64 last_clock_ms, last_good_ms, samples;
	unsigned int target_mv, target_ma;
	bool enabled, started, stopped, sampling, hardware_quiesced;
	int operation_error, actuator_error, converter_error;
};

/* Calls return -EINPROGRESS while acquiring, 0 only after measured health and
 * actual WDT service. Negative errors do checked terminal shutdown, no retry.
 */
int sm5440_supervisor_begin(struct regmap *map, struct sm5440_supervisor *monitor,
			    const struct x710_charge_facts *facts,
			    const struct sm5714_pd_snapshot *source);
int sm5440_supervisor_advance(struct regmap *map, struct sm5440_supervisor *monitor,
			      const struct x710_charge_facts *facts,
			      const struct sm5714_pd_snapshot *source);
int sm5440_supervisor_cancel(struct regmap *map, struct sm5440_supervisor *monitor);

#endif
