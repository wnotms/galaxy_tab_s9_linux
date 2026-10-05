/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_CONVERSION_H
#define _SM5440_CONVERSION_H

#include "x710-charging-policy.h"

struct regmap;

enum sm5440_conversion_state {
	SM5440_CONVERSION_IDLE,
	SM5440_CONVERSION_REARM,
	SM5440_CONVERSION_WAIT,
	SM5440_CONVERSION_DONE,
	SM5440_CONVERSION_FAULT,
	SM5440_CONVERSION_MEASURED,
};

/* One object per native request; the bound driver serializes uncached I/O
 * and cancellation generation, including exclusive read-to-clear IRQ access.
 */
struct sm5440_conversion {
	enum sm5440_conversion_state state;
	const u64 *generation;
	u64 epoch, requested_ms, disabled_ms, acquired_ms, completed_ms, last_clock_ms;
	u8 before_control, before_channels, expected_control;
	u8 events[4], status[4], adc[11];
	u32 faults, vbus_uv, vbat_uv, ibus_ua;
	int die_decic;
	unsigned int polls;
	bool enabled, running, owned, cleanup_attempted, adc_off_verified, ready;
	/* Managed supervisor consumes raw current before cleanup and handles OFF
	 * first on errors. Default false preserves standalone cleanup semantics.
	 */
	bool defer_cleanup, data_acquired;
	int operation_error, cleanup_error;
	struct x710_physical_sample sample;
};

/* -EINPROGRESS means schedule advance, not a valid measurement. */
int sm5440_conversion_begin(struct regmap *map, struct sm5440_conversion *adc);
int sm5440_conversion_advance(struct regmap *map, struct sm5440_conversion *adc);
int sm5440_conversion_finish(struct regmap *map, struct sm5440_conversion *adc);
int sm5440_conversion_cancel(struct regmap *map, struct sm5440_conversion *adc);

#endif
