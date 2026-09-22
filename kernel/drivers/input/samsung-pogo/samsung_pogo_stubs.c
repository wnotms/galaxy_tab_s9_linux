// SPDX-License-Identifier: GPL-2.0
/*
 * Stubs for the Samsung and Qualcomm services the imported driver calls.
 *
 * Every one of them is outside the bring-up path: the notifier only tells other
 * drivers the cover appeared, kbd_max77816_* drives a keyboard backlight this
 * cover does not have (the vendor log prints "not support device" on this
 * board), and the msm-bus votes are bandwidth accounting.
 */
#include "stm32_pogo_v3.h"

int pogo_notifier_register(struct notifier_block *nb, notifier_fn_t notifier,
			   enum pogo_notifier_device_t listener)
{
	return 0;
}
EXPORT_SYMBOL_GPL(pogo_notifier_register);

int pogo_notifier_unregister(struct notifier_block *nb)
{
	return 0;
}
EXPORT_SYMBOL_GPL(pogo_notifier_unregister);

int pogo_notifier_notify(struct stm32_dev *stm32, enum pogo_notifier_id_t notify_id,
			 char *data, int len)
{
	return 0;
}
EXPORT_SYMBOL_GPL(pogo_notifier_notify);

int kbd_max77816_init(void)
{
	return 0;
}
EXPORT_SYMBOL_GPL(kbd_max77816_init);

int kbd_max77816_control_init(struct stm32_dev *data)
{
	input_info(true, &data->client->dev, "kbd_max77816_control : not support device\n");
	return 0;
}
EXPORT_SYMBOL_GPL(kbd_max77816_control_init);

int kbd_max77816_control(struct stm32_dev *data, int voltage_val)
{
	return 0;
}
EXPORT_SYMBOL_GPL(kbd_max77816_control);

void *msm_bus_scale_register_client(struct msm_bus_scale_pdata *pdata)
{
	return NULL;
}
EXPORT_SYMBOL_GPL(msm_bus_scale_register_client);

int msm_bus_scale_client_update_request(void *client, unsigned int index)
{
	return 0;
}
EXPORT_SYMBOL_GPL(msm_bus_scale_client_update_request);

void msm_bus_scale_unregister_client(void *client)
{
}
EXPORT_SYMBOL_GPL(msm_bus_scale_unregister_client);

/*
 * The vendor files left out of this port: the two child input devices, the
 * notifier module and the voting module.  The bring-up path calls into them
 * only after - or beside - the MCU handshake, so they are stubs here and the
 * A/B still answers its question.  Their signatures are copied from the
 * vendor's own header.
 */
int boot_module_id;

void stm32_send_conn_noti(struct stm32_dev *stm32)
{
}

void pogo_set_conn_state(int state)
{
}

void stm32_register_notify(struct stm32_dev *stm32)
{
}

void stm32_unregister_notify(struct stm32_dev *stm32)
{
}

int stm32_init_voting(struct stm32_dev *stm32)
{
	return 0;
}

void stm32_destroy_voting(struct stm32_dev *stm32)
{
}

void stm32_voting_remove(struct stm32_dev *stm32)
{
}

void stm32_voting_suspend(struct stm32_dev *stm32)
{
}

int stm32_pogo_kpd_init(void)
{
	return 0;
}

void stm32_pogo_kpd_exit(void)
{
}

int stm32_pogo_touchpad_init(void)
{
	return 0;
}

void stm32_pogo_touchpad_exit(void)
{
}
