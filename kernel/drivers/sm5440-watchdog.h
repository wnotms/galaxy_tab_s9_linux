/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_WATCHDOG_H
#define _SM5440_WATCHDOG_H

#include <linux/types.h>

struct regmap;

/* Native-session hardware helper, no standalone export/charging grant. Caller owns
 * uncached I/O serialization, source epoch, pump shutdown and PM drain.
 */
enum sm5440_watchdog_state {
	SM5440_WATCHDOG_IDLE,
	SM5440_WATCHDOG_ARMED,
	SM5440_WATCHDOG_DONE,
	SM5440_WATCHDOG_FAULT,
};

#define SM5440_WATCHDOG_SERVICE_MS 1000U /* software refusal, not cutoff proof */

struct sm5440_watchdog {
	enum sm5440_watchdog_state state;
	u64 epoch, serviced_ms;
	u8 before, expected;
	bool owned, off_verified;
	int operation_error, restore_error;
};

int sm5440_watchdog_arm_off(struct regmap *map, struct sm5440_watchdog *wdt,
			    u64 epoch, u64 now_ms);
int sm5440_watchdog_service(struct regmap *map, struct sm5440_watchdog *wdt,
			    u64 epoch, u64 now_ms);
int sm5440_watchdog_restore_off(struct regmap *map, struct sm5440_watchdog *wdt);

#endif
