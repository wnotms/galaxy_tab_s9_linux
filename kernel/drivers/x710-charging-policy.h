/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _X710_CHARGING_POLICY_H
#define _X710_CHARGING_POLICY_H
#ifdef __KERNEL__
#include <linux/types.h>
#endif

/* Logical refusal deadlines, not measured hardware OCP response guarantees. */
#define X710_FACTS_MAX_AGE_MS	500U
#define X710_ADC_MAX_AGE_MS	100U
#define X710_MONITOR_DEADLINE_MS	100U

/* Offline transaction core. No live adapter or userspace activation interface
 * exists. Future adapter must be single-worker/epoch-serialized, must drain on
 * PM/unbind, and must implement bounded hardware operations without nesting
 * TCPM/charger locks. Source/parameter provenance is in the X710 audit docs.
 */
enum x710_charge_state {
	X710_SWITCHING,
	X710_DIRECT_PREPARE,
	X710_PPS_NEGOTIATING,
	X710_DIRECT_STARTING,
	X710_DIRECT_ACTIVE,
	X710_DIRECT_STOPPING,
	X710_FIXED_RESTORE,
	X710_CHARGE_OFF,
	X710_CHARGE_FAULT,
};

enum x710_thermal_zone {
	X710_COLD, X710_COOL3, X710_COOL2, X710_COOL1,
	X710_NORMAL, X710_WARM, X710_OVERHEAT,
};

struct x710_charge_facts {
	u64 epoch;
	/* Oldest acquisition in this bundle; never the time of a cache lookup. */
	u64 observed_ms;
	int capacity;
	int pack_decic;
	int die_decic;
	unsigned int vbat_mv;
	unsigned int fixed_mv;
	unsigned int apdo_min_mv;
	unsigned int apdo_max_mv;
	unsigned int apdo_ma;
	bool attached;
	bool battery_present;
	bool healthy;
	bool pack_valid;
	bool voltage_valid;
	bool soc_valid;
	bool die_valid;
	bool adc_valid;
	bool fixed_healthy;
	bool apdo;
	bool thermal_normal;
	bool suspended;
	bool fault;
	/* Cannot be inferred from vendor disabled HW OCP / IBUSLIM bits. */
	bool software_ocp_verified;
};

struct x710_physical_sample {
	u64 observed_ms;
	unsigned int vbus_mv;
	unsigned int vbat_mv;
	/* Preserve the ADC's625uA LSB through the actual current limit check. */
	unsigned int ibus_ua;
	unsigned int faults;
	bool valid;
	bool online;
	bool pump_on;
};

struct x710_charge_transaction {
	enum x710_charge_state state;
	u64 epoch;
	u64 last_clock_ms;
	u64 last_monitor_ms;
	u64 last_facts_ms;
	unsigned int target_mv;
	unsigned int target_ma;
	unsigned int fixed_mv;
	int last_error;
	/* Default false, no live setter/consumer supplied by this port. */
	bool armed;
	bool switching_inhibited;
};

/* Exactly one hardware/framework adapter, not a vendor framework. */
struct x710_charge_ops {
	u64 (*now_ms)(void *ctx);
	bool (*current_epoch)(void *ctx, u64 epoch);
	int (*read_facts)(void *ctx, struct x710_charge_facts *facts);
	int (*switching_gate)(void *ctx, bool inhibit);
	int (*pump_off)(void *ctx);
	int (*pps_request)(void *ctx, unsigned int mv, unsigned int ma);
	int (*measure)(void *ctx, struct x710_physical_sample *sample);
	int (*pump_prepare)(void *ctx, unsigned int ma);
	int (*pump_on)(void *ctx);
	int (*fixed_restore)(void *ctx);
};

bool x710_charge_eligible(const struct x710_charge_facts *facts);
enum x710_thermal_zone x710_vendor_zone(int decic, enum x710_thermal_zone previous);
int x710_pps_target(unsigned int vbat_mv, unsigned int offer_min_mv,
		    unsigned int offer_max_mv, unsigned int offer_ma,
		    unsigned int *target_mv, unsigned int *target_ma);
unsigned int x710_retry_seconds(unsigned int failures);
int x710_charge_start(struct x710_charge_transaction *tx,
		      const struct x710_charge_facts *facts,
		      const struct x710_charge_ops *ops, void *ctx);
int x710_charge_refresh(struct x710_charge_transaction *tx,
			const struct x710_charge_ops *ops, void *ctx);
int x710_charge_monitor(struct x710_charge_transaction *tx,
			const struct x710_charge_ops *ops, void *ctx);
int x710_charge_stop(struct x710_charge_transaction *tx,
		     const struct x710_charge_ops *ops, void *ctx);
#endif
