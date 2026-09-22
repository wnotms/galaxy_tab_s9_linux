/* SPDX-License-Identifier: GPL-2.0 */
/*
 * Compatibility layer for the imported Samsung stm32_pogo_v3 sources.
 *
 * The vendor files are imported verbatim except for this header and the include
 * lines that pull Samsung's frameworks.  Everything the bring-up path actually
 * needs is provided here with no behaviour of its own:
 *
 *   - Samsung's logging wrappers, whose first argument is a verbosity flag
 *   - the pogo notifier registration (only used to tell other drivers that the
 *     cover appeared; nothing in the bring-up depends on it)
 *   - kbd_max77816_* (a keyboard backlight controller; the vendor log itself
 *     prints "not support device" on this board)
 *   - MUIC and msm-bus votes, which the vendor driver uses for power and
 *     bandwidth accounting, not for the MCU handshake
 *
 * sec_device_create()/sysfs are deliberately absent: the port keeps the
 * bring-up and drops the Android interfaces, as agreed for this experiment.
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

/* pogo notifier: registered by the vendor driver, consumed by other drivers. */
static inline int pogo_notifier_register(struct notifier_block *nb)
{
	return 0;
}

static inline int pogo_notifier_unregister(struct notifier_block *nb)
{
	return 0;
}

static inline int pogo_notifier_notify(void *data, unsigned long event, void *v,
				       void *extra)
{
	return 0;
}

/* Keyboard backlight controller: not present on this cover. */
static inline int kbd_max77816_init(void *stm32)
{
	return 0;
}

static inline void kbd_max77816_control_init(void *stm32)
{
	input_info(true, &((struct stm32_dev *)stm32)->client->dev,
		   "kbd_max77816_control : not support device\n");
}

static inline int kbd_max77816_control(void *stm32, int on)
{
	return 0;
}

/* MUIC: the vendor driver only mirrors cover events into it. */
static inline int muic_notifier_register(struct notifier_block *nb)
{
	return 0;
}

/* msm-bus bandwidth votes are accounting only. */
struct msm_bus_scale_pdata;
static inline void *msm_bus_scale_register_client(struct msm_bus_scale_pdata *p)
{
	return NULL;
}

static inline int msm_bus_scale_client_update_request(void *client, unsigned int idx)
{
	return 0;
}

static inline void msm_bus_scale_unregister_client(void *client)
{
}

#endif /* __SAMSUNG_POGO_COMPAT_H__ */
