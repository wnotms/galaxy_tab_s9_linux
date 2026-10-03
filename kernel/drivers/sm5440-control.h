/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_CONTROL_H
#define _SM5440_CONTROL_H

#include <linux/types.h>

struct regmap;

/* OFF-only register preparation. No physical/thermal/source/ON grant.
 * Caller uses an uncached map, serializes I/O and drains ADC work;
 * lifetime/lease is its responsibility.
 * The isolated fixed9V diagnostic is the only current caller. No export or
 * userspace activation interface is provided.
 */
enum sm5440_control_state {
	SM5440_CONTROL_IDLE,
	SM5440_CONTROL_PREPARED,
	SM5440_CONTROL_DONE,
	SM5440_CONTROL_FAULT,
};

#define SM5440_CONTROL_SETTINGS 3
#define SM5440_CONTROL_WITNESSES 10

struct sm5440_control {
	enum sm5440_control_state state;
	u8 before[SM5440_CONTROL_SETTINGS];
	u8 witness[SM5440_CONTROL_WITNESSES];
	u8 status_before[4], status_after[4];
	u8 attempted;
	bool pending, off_verified, witness_valid;
	int operation_error, restore_error;
};

int sm5440_control_prepare(struct regmap *map, unsigned int input_ma,
			   struct sm5440_control *control);
int sm5440_control_restore(struct regmap *map, struct sm5440_control *control);

#endif
