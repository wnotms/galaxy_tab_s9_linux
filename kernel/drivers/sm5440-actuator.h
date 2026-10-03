/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_ACTUATOR_H
#define _SM5440_ACTUATOR_H

#include "sm5440-control.h"
#include "sm5440-watchdog.h"
#include "sm5714-stage2.h"
#include "x710-charging-policy.h"

/* Unintegrated, default disabled. Caller owns serialized uncached I/O and
 * generation publication/drain; these registers do not grant PD or OCP.
 */
struct sm5440_actuator {
	struct sm5440_control controls;
	struct sm5440_watchdog watchdog;
	const u64 *generation;
	u64 epoch, last_clock_ms, instance, source_generation, budget_generation, lease;
	u8 cntl6_before;
	bool enabled, switching_inhibited;
	bool attempted, cleanup_attempted, enhiz_owned, mode_possible, off_verified;
	int operation_error, cleanup_error;
};

int sm5440_actuator_start(struct regmap *map, struct sm5440_actuator *actuator,
			  const struct x710_charge_facts *facts,
			  const struct x710_physical_sample *physical,
			  const struct sm5714_pd_snapshot *source,
			  unsigned int target_mv, unsigned int target_ma);
int sm5440_actuator_stop(struct regmap *map, struct sm5440_actuator *actuator);

#endif
