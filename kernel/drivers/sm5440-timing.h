/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_TIMING_H
#define _SM5440_TIMING_H

#include <linux/types.h>

struct regmap;

/* OFF-only experiment. These diagnostic budgets are not an active ADC/OCP
 * certificate and do not change SM5440_FRESH_REQUEST_MS or the converter.
 */
#define SM5440_TIMING_SAMPLES 8U
#define SM5440_TIMING_WINDOW_MS 2000U
#define SM5440_TIMING_READY_MS 500U
#define SM5440_TIMING_REARM_MS 50U
#define SM5440_TIMING_POLLS 450U

struct sm5440_timing_sample {
	u64 cleared_ms, ready_begin_ms, ready_end_ms, adc_begin_ms, adc_end_ms;
	u8 interrupt[4], status[4], status_after[4], adc[11];
	u8 mode, control, channels;
	u32 faults;
};

struct sm5440_timing {
	struct sm5440_timing_sample sample[SM5440_TIMING_SAMPLES];
	u64 started_ms, disabled_ms, enabled_ms, completed_ms, last_ms;
	u64 cleared_ms, ready_deadline_ms;
	u8 control_before, channels_before, control_after, channels_after;
	u8 initial_interrupt[4], initial_status[4];
	unsigned int count, polls;
	int error, cleanup_error;
	bool attempted, saved, changed, enabled, finished, restored;
};

/* Sleepable regmap operations; caller owns its I/O serialization. No internal
 * sleep, scheduling, source policy, pump/current/ENHIZ write or exported API.
 * step returns 0 pending, 1 all samples, or a negative terminal error. Always
 * finish once after begin, including cancellation and uncertain I2C writes.
 */
int sm5440_timing_begin(struct regmap *map, struct sm5440_timing *t);
int sm5440_timing_step(struct regmap *map, struct sm5440_timing *t);
int sm5440_timing_finish(struct regmap *map, struct sm5440_timing *t, int error);

#endif
