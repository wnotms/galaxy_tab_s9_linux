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

#define SM5714_SOURCE_PDO_MAX 7U

/* Standard TCPM fixed-budget observation, not physical VBUS or a charge grant.
 * No controller/supply pointer escapes. On error the complete output is zero.
 */
struct sm5714_pd_snapshot {
	u64 instance, source_generation, budget_generation;
	u64 started_ms, completed_ms;
	u32 source_pdos[SM5714_SOURCE_PDO_MAX];
	unsigned int nr_source_pdos;
	unsigned int budget_mv, budget_ma;
	int online, usb_type, voltage_uv, current_ua;
	bool charge_requested;
};
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *out);

#endif
