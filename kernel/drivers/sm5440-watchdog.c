// SPDX-License-Identifier: GPL-2.0-only
/* X710 vendor CNTL1 timer/enable; Fedora same-model refresh cross-check.
 * Linked only by the isolated native-control profile. Ordinary passive/fixed
 * charging does not call this helper.
 * See docs/SM5440_WATCHDOG_TRANSACTION.md; no HW OCP or charging grant.
 */
#include <linux/errno.h>
#include <linux/regmap.h>

#include "sm5440-hw.h"
#include "sm5440-watchdog.h"

#define SM5440_WDT_CNTL1	0x0c
#define SM5440_WDT_ENABLE	BIT(7) /* vendor sm5440_enable_wdt() */
#define SM5440_WDT_TIMER	GENMASK(6, 4)
#define SM5440_WDT_30S	(4U << 4) /* vendor WDT_TIMER_S_30 */
#define SM5440_WDT_RESET	BIT(0) /* vendor sm5440_sw_reset(), never write1 */
#define SM5440_WDT_FIELDS	(SM5440_WDT_ENABLE | SM5440_WDT_TIMER)

static int sm5440_watchdog_fail(struct sm5440_watchdog *wdt, int error)
{
	if (!wdt->operation_error)
		wdt->operation_error = error;
	wdt->state = SM5440_WATCHDOG_FAULT;
	return error;
}

static int sm5440_watchdog_mode(struct regmap *map, struct sm5440_watchdog *wdt,
			       bool running)
{
	unsigned int mode;
	u8 status[4];
	int ret;

	wdt->off_verified = false;
	ret = regmap_read(map, SM5440_CNTL5, &mode);
	if (ret)
		return ret;
	if ((mode & SM5440_MODE_MASK) != (running ? BIT(2) : 0))
		return -EBUSY;
	wdt->off_verified = !running;
	ret = regmap_bulk_read(map, SM5440_STATUS1, status, sizeof(status));
	if (ret)
		return ret;
	if (sm5440_decode_faults(status, running, 1) || (status[2] & BIT(6)))
		return -EIO;
	return status[2] & BIT(5) ? 0 : -ENOLINK;
}

/* Must issue a write even if unchanged: equal-value update_bits can skip it.
 * Always clear software-reset in the proposed byte; callers first reject a
 * readback with reset active rather than acknowledge/reset unknown silicon.
 */
static int sm5440_watchdog_write(struct regmap *map, u8 value)
{
	unsigned int after;
	int ret;

	if (value & SM5440_WDT_RESET)
		return -EBUSY;
	ret = regmap_write(map, SM5440_WDT_CNTL1, value);
	if (!ret)
		ret = regmap_read(map, SM5440_WDT_CNTL1, &after);
	if (!ret && after != value)
		ret = -EIO;
	return ret;
}

int sm5440_watchdog_restore_off(struct regmap *map, struct sm5440_watchdog *wdt)
{
	unsigned int mode, cntl1;
	u8 target;
	int ret;

	if (!map || !wdt)
		return -EINVAL;
	if (!wdt->owned)
		return wdt->restore_error;
	/* Cleanup must also work detached/faulted; OFF, not healthy VBUS, gates it. */
	wdt->off_verified = false;
	ret = regmap_read(map, SM5440_CNTL5, &mode);
	if (!ret && mode & SM5440_MODE_MASK)
		ret = -EBUSY;
	if (ret)
		goto out;
	wdt->off_verified = true;
	ret = regmap_read(map, SM5440_WDT_CNTL1, &cntl1);
	if (!ret && cntl1 & SM5440_WDT_RESET)
		ret = -EBUSY;
	if (ret)
		goto out;
	target = (cntl1 & ~SM5440_WDT_FIELDS) | (wdt->before & SM5440_WDT_FIELDS);
	ret = sm5440_watchdog_write(map, target);
	/* Preserve drift, disable WDT, but never report an exact restoration. */
	if (!ret && target != wdt->before)
		ret = -EIO;
	if (!ret) {
		wdt->owned = false;
		wdt->state = wdt->operation_error ? SM5440_WATCHDOG_FAULT : SM5440_WATCHDOG_DONE;
	}
out:
	wdt->restore_error = ret;
	if (ret)
		wdt->state = SM5440_WATCHDOG_FAULT;
	return ret;
}

int sm5440_watchdog_arm_off(struct regmap *map, struct sm5440_watchdog *wdt,
			    u64 epoch, u64 now_ms)
{
	unsigned int value;
	int ret;

	if (!map || !wdt || !epoch || !now_ms)
		return -EINVAL;
	if (wdt->state != SM5440_WATCHDOG_IDLE || wdt->owned)
		return -EALREADY;
	ret = regmap_read(map, SM5440_DEVICEID, &value);
	if (!ret && (value & 0xf) != 1)
		ret = -ENODEV;
	if (!ret)
		ret = sm5440_watchdog_mode(map, wdt, false);
	if (!ret)
		ret = regmap_read(map, SM5440_WDT_CNTL1, &value);
	if (!ret && value & (SM5440_WDT_ENABLE | SM5440_WDT_RESET))
		ret = -EBUSY;
	if (ret)
		return sm5440_watchdog_fail(wdt, ret);
	wdt->before = value;
	wdt->expected = (value & ~SM5440_WDT_FIELDS) | SM5440_WDT_30S | SM5440_WDT_ENABLE;
	wdt->epoch = epoch;
	/* A failed bus write may already have enabled silicon. Keep ownership. */
	wdt->owned = true;
	ret = sm5440_watchdog_write(map, wdt->expected);
	if (!ret)
		ret = sm5440_watchdog_mode(map, wdt, false);
	if (ret) {
		sm5440_watchdog_fail(wdt, ret);
		sm5440_watchdog_restore_off(map, wdt);
		return ret;
	}
	wdt->serviced_ms = now_ms;
	wdt->state = SM5440_WATCHDOG_ARMED;
	return 0;
}

int sm5440_watchdog_service(struct regmap *map, struct sm5440_watchdog *wdt,
			    u64 epoch, u64 now_ms)
{
	unsigned int value;
	int ret;

	if (!map || !wdt)
		return -EINVAL;
	if (wdt->state != SM5440_WATCHDOG_ARMED || !wdt->owned)
		return -EPERM;
	if (!epoch || epoch != wdt->epoch)
		return sm5440_watchdog_fail(wdt, -ECANCELED);
	if (!now_ms || now_ms < wdt->serviced_ms ||
	    now_ms - wdt->serviced_ms > SM5440_WATCHDOG_SERVICE_MS)
		return sm5440_watchdog_fail(wdt, -ETIMEDOUT);
	ret = sm5440_watchdog_mode(map, wdt, true);
	if (!ret)
		ret = regmap_read(map, SM5440_WDT_CNTL1, &value);
	if (!ret && value != wdt->expected)
		ret = -EIO;
	if (!ret)
		ret = sm5440_watchdog_write(map, wdt->expected);
	if (!ret)
		ret = sm5440_watchdog_mode(map, wdt, true);
	if (ret)
		return sm5440_watchdog_fail(wdt, ret);
	wdt->serviced_ms = now_ms;
	return 0;
}
