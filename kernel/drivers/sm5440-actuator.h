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
	u64 pause_started_ms, paused_budget_generation, pause_sequence;
	unsigned int active_mv, active_ma;
	u8 cntl6_before;
	bool enabled, switching_inhibited;
	bool attempted, cleanup_attempted, enhiz_owned, mode_possible, off_verified;
	bool paused, resume_attempted;
	int operation_error, cleanup_error;
};

int sm5440_actuator_start(struct regmap *map, struct sm5440_actuator *actuator,
			  const struct x710_charge_facts *facts,
			  const struct x710_physical_sample *physical,
			  const struct sm5714_pd_snapshot *source,
			  unsigned int target_mv, unsigned int target_ma);
int sm5440_actuator_stop(struct regmap *map, struct sm5440_actuator *actuator);
/* OFF-only park for a serialized owner; no ADC may be outstanding. Keeps
 * original settings/WDT/ENHIZ ownership, not terminal cleanup or a PD grant.
 */
int sm5440_actuator_pause(struct regmap *map, struct sm5440_actuator *actuator);
/* New native PPS completion and fresh real OFF VBUS/zeroIBUS required; source
 * budget generation must advance, same attach/source. Current can only fall.
 */
int sm5440_actuator_resume(struct regmap *map, struct sm5440_actuator *actuator,
			   const struct x710_charge_facts *facts,
			   const struct x710_physical_sample *physical,
			   const struct sm5714_pd_snapshot *source,
			   unsigned int target_mv, unsigned int target_ma);

#endif
