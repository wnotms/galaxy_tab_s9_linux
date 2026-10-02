/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5714_STAGE2_H
#define _SM5714_STAGE2_H

#include <linux/types.h>

/* Serialized companion API; no raw charger pointer escapes its lifetime. */
int sm5714_battery_typec_claim(void);
int sm5714_battery_get_bc12_limit(void);
int sm5714_battery_set_pd_contract(unsigned int mv, unsigned int ma);
int sm5714_battery_set_typec_charge(bool charge);
void sm5714_battery_typec_fault(void);

/* Default inactive. A nonzero lease on error is diagnostic, not authorization.
 * Release is kernel-only and requires caller-proven pump OFF / fresh fixed VBUS.
 * Revocation (standby/budget/fault/PM/unbind) keeps switching inhibited.
 */
int sm5714_battery_switching_acquire(u64 *lease);
int sm5714_battery_switching_release(u64 lease);

#endif
