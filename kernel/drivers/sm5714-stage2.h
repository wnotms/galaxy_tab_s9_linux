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

/* USB PD r3.2 v1.2 Table 4.6 vSrcNew: fixed source voltage +/-5%.
 * Use this steady-state window as the board's physical return gate; do not
 * include the additional vSrcValid transient allowance. ADC at the sink is
 * not a calibrated source-receptacle compliance measurement. Only approved
 * fixed contracts are accepted, so the uV products cannot overflow.
 */
static inline bool sm5714_fixed_vbus_valid(unsigned int mv, u32 vbus_uv)
{
	if (mv != 5000 && mv != 9000)
		return false;

	return vbus_uv >= mv * 950U && vbus_uv <= mv * 1050U;
}

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

/* Fresh native gauge/pack-thermistor observation, not a pump grant. A zero
 * lease is pre-entry observation; an owned observation needs the exact lease.
 * State/PM/rebind changes refuse the whole bundle. Errors zero output. The
 * consumer must also bracket acquisition with native TCPC epoch observations.
 */
struct sm5714_pack_snapshot {
	u64 instance, state_generation, switching_lease;
	u64 started_ms, completed_ms;
	unsigned int typec_mv, typec_ma;
	int capacity, voltage_uv, current_ua, pack_decic, health;
	bool battery_present, attached, thermal_normal;
	bool typec_owned, typec_charge, pps_contract;
};
int sm5714_battery_read_pack(u64 lease, struct sm5714_pack_snapshot *out);

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

/* Read-only active PPS observation, exact source/lease and native timestamps.
 * No Request/refresh, current programming, pump operation or charge grant.
 * Caller owns serialization against battery lease release; errors zero output.
 */
int sm5714_pd_read_owned_snapshot(u64 instance, u64 source_generation, u64 lease,
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
