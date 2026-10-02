/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5714_STAGE2_H
#define _SM5714_STAGE2_H

#include <linux/types.h>

/* Accepted fixed ceilings and initial PPS bring-up bounds, not pump grants. */
#define SM5714_FIXED_5V_MA	1800U
#define SM5714_FIXED_9V_MA	1500U
#define SM5714_PPS_MIN_MV	8200U
#define SM5714_PPS_MAX_MV	10500U
#define SM5714_PPS_MAX_MA	1800U
/* Linux PD_P_SNK_STDBY_MW; switching remains OFF during fixed return. */
#define SM5714_STANDBY_MAX_MW	2500U

enum sm5714_contract_kind {
	SM5714_CONTRACT_FIXED,
	SM5714_CONTRACT_PPS,
	SM5714_CONTRACT_STANDBY,
};

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
/* Try-only authorization release; no IIO/I2C or producer wait. The unchanged
 * battery worker performs ordinary thermal/charging programming afterwards.
 */
int sm5714_battery_switching_release_async(u64 lease);
int sm5714_battery_switching_check(u64 lease);
/* Owned callbacks can only maintain checked switching OFF, never enable it. */
int sm5714_battery_set_owned_contract(u64 lease, unsigned int mv, unsigned int ma,
				    enum sm5714_contract_kind kind);

#define SM5714_SOURCE_PDO_MAX	7U

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
	bool charge_requested, pps_contract;
};
int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *out);

/* Caller-proven pump OFF, acquired switching lease, no concurrent release.
 * ONLINE=1 only; no activation/voltage/current write, lease release or physical
 * proof. An ordinary budget change revokes the lease while inhibition stays set;
 * success is a logical fixed snapshot, not authorization to release that lease.
 * No live consumer is installed by this interface.
 */
int sm5714_pd_restore_fixed(u64 instance, u64 source_generation, u64 lease,
			   struct sm5714_pd_snapshot *out);

/* Kernel-only, caller-proven pump OFF, externally acquired switching lease.
 * No live consumer installed. Initial entry requires healthy fixed9V.
 */
int sm5714_pd_request_pps(u64 instance, u64 source_generation, u64 lease,
			 unsigned int mv, unsigned int ma,
			 struct sm5714_pd_snapshot *out);

/* Actual fresh physical evidence supplied by a serialized pump-OFF consumer,
 * never reconstructed from a logical TCPM budget or stale diagnostic cache.
 */
struct sm5714_fixed_proof {
	u64 observed_ms;
	u32 vbus_uv, ibus_ua;
	bool pump_off;
};

/* Atomically binds lease release to the exact current fixed source/instance.
 * No protocol setter, retry or fabricated proof. Physical evidence<=100ms.
 */
int sm5714_pd_release_fixed(u64 instance, u64 source_generation, u64 lease,
			    const struct sm5714_fixed_proof *proof);

#endif
