/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Compatibility layer for the imported Samsung stm32_pogo_v3 sources.
 *
 * The vendor files are imported verbatim except for their includes and this
 * header, which supplies what Samsung's frameworks provided and nothing else.
 * The function stubs live in samsung_pogo_stubs.c so that their signatures match
 * the vendor's own prototypes exactly.
 *
 * Dropped on purpose, as agreed for this experiment: sec_class sysfs, factory
 * and FOTA interfaces, Samsung's logging class and the sec_input framework.
 */
#ifndef __SAMSUNG_POGO_COMPAT_H__
#define __SAMSUNG_POGO_COMPAT_H__

#include <linux/device.h>
#include <linux/notifier.h>
#include <linux/types.h>

/* Samsung's sec_input logging: (verbose, dev, fmt, ...) with its own tag. */
#define SECLOG "sec_input"

#define input_info(verbose, dev, fmt, ...) \
	dev_info((dev), fmt, ##__VA_ARGS__)
#define input_err(verbose, dev, fmt, ...) \
	dev_err((dev), fmt, ##__VA_ARGS__)
#define input_dbg(verbose, dev, fmt, ...) \
	dev_dbg((dev), fmt, ##__VA_ARGS__)

/* Samsung's return convention, from sec_input.h. */
#ifndef SEC_SUCCESS
#define SEC_SUCCESS	0
#endif
#ifndef SEC_ERROR
#define SEC_ERROR	(-1)
#endif

/*
 * Samsung's wake-lock timeout for touch/key wakeups (sec_input.h).  Only the
 * timeout value is used; the wakeup source itself is registered by the driver.
 */
#ifndef SEC_TS_WAKE_LOCK_TIME
#define SEC_TS_WAKE_LOCK_TIME	2000
#endif

/* Samsung's millisecond delay helper, from sec_common_fn. */
#define sec_delay(ms)	msleep(ms)

/* sec_class device lifetime: nothing is created here, so nothing is destroyed. */
#define sec_device_destroy(dev)		do { } while (0)

/* msm-bus bandwidth votes are accounting only; nothing is voted here. */
struct msm_bus_scale_pdata {
	int unused;
};

#endif /* __SAMSUNG_POGO_COMPAT_H__ */
