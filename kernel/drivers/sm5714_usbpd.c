// SPDX-License-Identifier: GPL-2.0-only
/*
 * SM-X710 SM5714 TCPC transport, Sink + Device; fixed5/9V by default.
 *
 * Register provenance: Samsung X710 GPL sm5714_typec.c/.h, and same-model
 * nacht20-de/gts9wifi-fedora-linux ab123e7d, kernel/files/sm5714_usbpd.c.
 * See docs/SM5714_STAGE2_PD_PLAN.md and Test255 SOURCE_AUDIT for each sequence.
 * Stock Linux TCPM owns policy. No private policy, boost, role-swap quirk,
 * alternate-mode or direct-charger implementation. Kernel-owned PPS protocol
 * operation requires checked switching-OFF ownership; no live caller installed.
 */
#include <linux/atomic.h>
#include <linux/build_bug.h>
#include <linux/debugfs.h>
#include <linux/delay.h>
#include <linux/ktime.h>
#include <linux/limits.h>
#include <linux/power_supply.h>
#include <linux/seq_file.h>
#include <linux/wait.h>
#include <linux/i2c.h>
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/property.h>
#include <linux/regmap.h>
#include <linux/usb/pd.h>
#include <linux/usb/tcpm.h>
#include <linux/workqueue.h>

#include "sm5714-stage2.h"
#include "sm5714-pd-policy.h"

static_assert(SM5714_STANDBY_MAX_MW == PD_P_SNK_STDBY_MW);

/* Samsung sm5714_typec.h register map and interrupt bit definitions. */
#define SM5714_REG_INT1		0x01
#define SM5714_REG_MASK1		0x06
#define SM5714_REG_STATUS1	0x0b
#define SM5714_VBUS_POK		BIT(0)
#define SM5714_ATTACH		BIT(3)
#define SM5714_DETACH		BIT(4)
#define SM5714_SRC_ADV		BIT(4)
#define SM5714_VBUS_0V		BIT(5)
#define SM5714_RX_DONE		BIT(0)
#define SM5714_TX_DONE		BIT(1)
#define SM5714_TX_ERR		BIT(2)
#define SM5714_HRST_RX		BIT(5)
#define SM5714_HRST_DONE		BIT(6)
#define SM5714_TX_DISCARD		BIT(7)
#define SM5714_REG_CORR_CNTL4	0x23
#define SM5714_REG_CORR_CNTL5	0x24
#define SM5714_REG_CC_STATUS	0x28
#define SM5714_CC_ATTACH_MASK	GENMASK(2, 0)
#define SM5714_CC_SOURCE		1 /* partner is Source, local port is Sink */
#define SM5714_CC_RP_MASK		GENMASK(4, 3)
#define SM5714_CC_FLIPPED		BIT(5)
#define SM5714_REG_CC_CNTL1	0x29
#define SM5714_REG_CC_CNTL3	0x2b
#define SM5714_REG_CC_CNTL5	0x2d
#define SM5714_REG_PD_CNTL1	0x38
#define SM5714_REG_PD_CNTL2	0x39
#define SM5714_REG_PD_CNTL4	0x3b
#define SM5714_REG_RX_SRC		0x41
#define SM5714_REG_RX_HEADER	0x42
#define SM5714_REG_RX_PAYLOAD	0x44
#define SM5714_REG_RX_BUF		0x5e
#define SM5714_REG_RX_BUF_ST	0x5f
#define SM5714_REG_TX_HEADER	0x60
#define SM5714_REG_TX_PAYLOAD	0x62
#define SM5714_REG_TX_REQ		0x7e
#define SM5714_REG_PD_STATE3	0xd8

struct sm5714_usbpd {
	struct device *dev;
	struct regmap *regmap;
	struct mutex lock;
	struct mutex control_lock;
	struct tcpc_dev tcpc;
	struct tcpm_port *port;
	struct fwnode_handle *connector;
	struct delayed_work cc_resync_work;
	u32 source_pdos[PD_MAX_PAYLOAD];
	unsigned int nr_source_pdos;
	u64 source_generation;
	u64 port_instance, budget_generation;
	unsigned int budget_mv, budget_ma, budget_pending;
	bool charge_requested, observation_exhausted, budget_pps;
	u64 pps_lease, pps_source_generation;
	unsigned int pps_mv, pps_ma, pps_previous_mv, pps_previous_ma;
	unsigned int operating_snk_mw, request_mv, request_ma;
	bool pps_restoring, last_request_pps, pps_operation_active;
	struct power_supply *tcp_supply;
	atomic_t snapshot_users;
	wait_queue_head_t snapshot_wait;
	struct dentry *snapshot_debug;
	int irq;
	bool fault;
	bool removing;
};

static const struct regmap_config sm5714_regmap_config = {
	.reg_bits = 8,
	.val_bits = 8,
	.max_register = 0xff,
	.cache_type = REGCACHE_NONE,
};

static struct sm5714_usbpd *tcpc_to_sm5714(struct tcpc_dev *tcpc)
{
	return container_of(tcpc, struct sm5714_usbpd, tcpc);
}

static void sm5714_pps_revoke_locked(struct sm5714_usbpd *sm)
{
	lockdep_assert_held(&sm->lock);
	sm->pps_lease = 0;
	sm->pps_source_generation = 0;
	sm->pps_mv = sm->pps_ma = 0;
	sm->pps_previous_mv = sm->pps_previous_ma = 0;
	sm->pps_restoring = sm->last_request_pps = sm->pps_operation_active = false;
	sm->request_mv = sm->request_ma = 0;
}

/* Transport lock protects both the cache and its lifetime. No old offer may
 * authorize a Request after reset, fault, detach, or a new source publication.
 */
static void sm5714_forget_source(struct sm5714_usbpd *sm)
{
	lockdep_assert_held(&sm->lock);
	sm5714_pps_revoke_locked(sm);
	memset(sm->source_pdos, 0, sizeof(sm->source_pdos));
	sm->nr_source_pdos = 0;
	if (sm->source_generation == U64_MAX)
		sm->observation_exhausted = true;
	else
		sm->source_generation++;
}

/* Registry->tryTCPC for short copies only. No registry/TCPC lock across
 * standard power_supply properties, which may run TCPM code. Teardown drains
 * pinned operations before releasing its supply reference or port resources.
 */
static DEFINE_MUTEX(sm5714_port_registry_lock);
static struct sm5714_usbpd *sm5714_port_provider;
static u64 sm5714_port_issuer;

static void sm5714_budget_tick_locked(struct sm5714_usbpd *sm)
{
	lockdep_assert_held(&sm->lock);
	if (sm->budget_generation == U64_MAX)
		sm->observation_exhausted = true;
	else
		sm->budget_generation++;
}

static void sm5714_budget_begin(struct sm5714_usbpd *sm)
{
	mutex_lock(&sm->lock);
	sm->budget_pending++;
	sm5714_budget_tick_locked(sm);
	mutex_unlock(&sm->lock);
}

static void sm5714_budget_end(struct sm5714_usbpd *sm, int ret,
			      bool update_current, unsigned int mv, unsigned int ma,
			      bool charge, bool pps)
{
	mutex_lock(&sm->lock);
	if (!ret) {
		if (update_current) {
			sm->budget_mv = mv;
			sm->budget_ma = ma;
			sm->budget_pps = pps;
		} else {
			sm->charge_requested = charge;
		}
	}
	sm->budget_pending--;
	sm5714_budget_tick_locked(sm);
	mutex_unlock(&sm->lock);
}

static int sm5714_port_publish(struct sm5714_usbpd *sm)
{
	int ret = 0;

	mutex_lock(&sm5714_port_registry_lock);
	if (!sm->tcp_supply)
		ret = -ENODEV;
	else if (sm5714_port_provider)
		ret = -EBUSY;
	else if (sm5714_port_issuer == U64_MAX)
		ret = -EOVERFLOW;
	else {
		sm->port_instance = ++sm5714_port_issuer;
		sm5714_port_provider = sm;
	}
	mutex_unlock(&sm5714_port_registry_lock);
	return ret;
}

static void sm5714_port_unpublish(struct sm5714_usbpd *sm)
{
	mutex_lock(&sm5714_port_registry_lock);
	WRITE_ONCE(sm->removing, true);
	if (sm5714_port_provider == sm)
		sm5714_port_provider = NULL;
	mutex_unlock(&sm5714_port_registry_lock);
	wait_event(sm->snapshot_wait, !atomic_read(&sm->snapshot_users));
	/* Last put wakes while holding registry; wait for its final unlock. */
	mutex_lock(&sm5714_port_registry_lock);
	mutex_unlock(&sm5714_port_registry_lock);
}

static int sm5714_snapshot_locked(struct sm5714_usbpd *sm,
				  struct sm5714_pd_snapshot *sample)
{
	lockdep_assert_held(&sm->lock);
	if (READ_ONCE(sm->removing))
		return -ESHUTDOWN;
	if (sm->fault)
		return -EIO;
	if (sm->observation_exhausted)
		return -EOVERFLOW;
	if (!sm->nr_source_pdos || !sm->source_generation)
		return -ENODATA;
	if (sm->nr_source_pdos > SM5714_SOURCE_PDO_MAX)
		return -EPROTO;
	if (sm->budget_pending)
		return -EAGAIN;
	sample->instance = sm->port_instance;
	sample->source_generation = sm->source_generation;
	sample->budget_generation = sm->budget_generation;
	sample->budget_mv = sm->budget_mv;
	sample->budget_ma = sm->budget_ma;
	sample->charge_requested = sm->charge_requested;
	sample->pps_contract = sm->budget_pps;
	sample->nr_source_pdos = sm->nr_source_pdos;
	memcpy(sample->source_pdos, sm->source_pdos, sizeof(sample->source_pdos));
	return 0;
}

static int sm5714_snapshot_properties(struct power_supply *psy,
				      struct sm5714_pd_snapshot *sample)
{
	static const enum power_supply_property props[] = {
		POWER_SUPPLY_PROP_ONLINE, POWER_SUPPLY_PROP_USB_TYPE,
		POWER_SUPPLY_PROP_VOLTAGE_NOW, POWER_SUPPLY_PROP_CURRENT_NOW,
	};
	int *values[] = { &sample->online, &sample->usb_type,
			  &sample->voltage_uv, &sample->current_ua };
	union power_supply_propval value;
	unsigned int i;
	int ret;

	for (i = 0; i < ARRAY_SIZE(props); i++) {
		ret = power_supply_get_property(psy, props[i], &value);
		if (ret)
			return ret;
		*values[i] = value.intval;
	}
	return 0;
}

/* Reference pinning is shared by observations and protocol-only restoration. */
static int sm5714_port_get(struct sm5714_usbpd **out,
			   struct sm5714_pd_snapshot *sample)
{
	struct sm5714_usbpd *sm;
	int ret;

	mutex_lock(&sm5714_port_registry_lock);
	sm = sm5714_port_provider;
	if (!sm) {
		ret = -ENODEV;
		goto registry_out;
	}
	if (!mutex_trylock(&sm->lock)) {
		ret = -EBUSY;
		goto registry_out;
	}
	ret = sm5714_snapshot_locked(sm, sample);
	if (!ret)
		atomic_inc(&sm->snapshot_users);
	mutex_unlock(&sm->lock);
registry_out:
	mutex_unlock(&sm5714_port_registry_lock);
	if (!ret)
		*out = sm;
	return ret;
}

static void sm5714_port_put(struct sm5714_usbpd *sm)
{
	mutex_lock(&sm5714_port_registry_lock);
	if (atomic_dec_and_test(&sm->snapshot_users))
		wake_up_all(&sm->snapshot_wait);
	mutex_unlock(&sm5714_port_registry_lock);
}

/* TCPM USB_TYPE describes advertised augmented capabilities, not active mode.
 * ONLINE=1 is fixed even on a PPS/AVS-capable source. Never accept ONLINE=2/3
 * as fixed. Linux 7.2-rc3 tcpm_pd_select_pdo()/tcpm_psy_get_online().
 */
static bool sm5714_pd_capable(int type)
{
	return type == POWER_SUPPLY_USB_TYPE_PD ||
		type == POWER_SUPPLY_USB_TYPE_PD_PPS ||
		type == POWER_SUPPLY_USB_TYPE_PD_SPR_AVS ||
		type == POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS;
}

static int sm5714_read_contract_pinned(struct sm5714_usbpd *sm,
				       struct sm5714_pd_snapshot *out, bool pps)
{
	struct sm5714_pd_snapshot before = {}, after = {}, repeat = {};
	int ret;

	mutex_lock(&sm->lock);
	ret = sm5714_snapshot_locked(sm, &before);
	mutex_unlock(&sm->lock);
	if (ret)
		return ret;
	before.started_ms = ktime_to_ms(ktime_get_boottime());
	ret = sm5714_snapshot_properties(sm->tcp_supply, &before);
	if (!ret)
		ret = sm5714_snapshot_properties(sm->tcp_supply, &repeat);
	before.completed_ms = ktime_to_ms(ktime_get_boottime());
	mutex_lock(&sm->lock);
	if (!ret)
		ret = sm5714_snapshot_locked(sm, &after);
	if (!ret && (before.instance != after.instance ||
		before.source_generation != after.source_generation ||
		before.budget_generation != after.budget_generation ||
		before.online != repeat.online || before.usb_type != repeat.usb_type ||
		before.voltage_uv != repeat.voltage_uv || before.current_ua != repeat.current_ua))
		ret = -EAGAIN;
	/* Only stable mirrored contracts are usable here. No physical measurement.
	 * Mirror matching rejects lockless TCPM publication before its callback.
	 */
	if (!ret && (!before.started_ms || before.completed_ms < before.started_ms ||
		before.online != (pps ? 2 : 1) || !sm5714_pd_capable(before.usb_type) ||
		before.pps_contract != pps ||
		!before.charge_requested ||
		(pps ? (before.budget_mv < SM5714_PPS_MIN_MV ||
			before.budget_mv > SM5714_PPS_MAX_MV || before.budget_mv % 20 ||
			before.budget_ma % 50 ||
			(before.usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS &&
			 before.usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS)) :
			(before.budget_mv != 5000 && before.budget_mv != 9000)) ||
		before.budget_ma < 100 || before.budget_ma > SM5714_PPS_MAX_MA ||
		(!pps && before.budget_mv == 9000 && before.budget_ma > SM5714_FIXED_9V_MA) ||
		before.voltage_uv != before.budget_mv * 1000 ||
		before.current_ua != before.budget_ma * 1000))
		ret = -EAGAIN;
	if (!ret)
		*out = before;
	mutex_unlock(&sm->lock);
	return ret;
}

static int sm5714_read_fixed_pinned(struct sm5714_usbpd *sm,
				    struct sm5714_pd_snapshot *out)
{
	return sm5714_read_contract_pinned(sm, out, false);
}

int sm5714_pd_read_snapshot(struct sm5714_pd_snapshot *out)
{
	struct sm5714_pd_snapshot sample = {};
	struct sm5714_usbpd *sm;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	ret = sm5714_port_get(&sm, &sample);
	if (ret)
		return ret;
	ret = sm5714_read_fixed_pinned(sm, out);
	sm5714_port_put(sm);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_pd_read_snapshot);

static int sm5714_restore_token(struct sm5714_usbpd *sm, u64 instance,
				u64 source_generation)
{
	struct sm5714_pd_snapshot sample = {};
	int ret;

	mutex_lock(&sm->lock);
	ret = sm5714_snapshot_locked(sm, &sample);
	if (!ret && (sample.instance != instance ||
		     sample.source_generation != source_generation))
		ret = -ESTALE;
	mutex_unlock(&sm->lock);
	return ret;
}

static int sm5714_restore_fixed_pinned(struct sm5714_usbpd *sm, u64 instance,
				      u64 source_generation, u64 lease,
				      struct sm5714_pd_snapshot *out)
{
	struct sm5714_pd_snapshot sample = {}, repeat = {}, fixed = {};
	union power_supply_propval value = { .intval = 1 };
	int ret;

	ret = sm5714_restore_token(sm, instance, source_generation);
	if (!ret)
		ret = sm5714_battery_switching_check(lease);
	if (!ret)
		ret = sm5714_snapshot_properties(sm->tcp_supply, &sample);
	if (!ret)
		ret = sm5714_snapshot_properties(sm->tcp_supply, &repeat);
	if (!ret && (sample.online != repeat.online ||
		     sample.usb_type != repeat.usb_type ||
		     sample.voltage_uv != repeat.voltage_uv ||
		     sample.current_ua != repeat.current_ua))
		ret = -EAGAIN;
	/* Do not deactivate an unreviewed AVS state. ONLINE=2 is PPS only;
	 * this operation can only leave it, never enter or tune it.
	 */
	if (!ret && (!sm5714_pd_capable(sample.usb_type) ||
		     (sample.online != 1 && sample.online != 2) ||
		     (sample.online == 2 &&
		      sample.usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS &&
		      sample.usb_type != POWER_SUPPLY_USB_TYPE_PD_PPS_SPR_AVS)))
		ret = -EOPNOTSUPP;
	if (!ret)
		ret = sm5714_restore_token(sm, instance, source_generation);
	if (!ret)
		ret = sm5714_battery_switching_check(lease);
	if (!ret && sample.online == 2) {
		mutex_lock(&sm->lock);
		if (sm->source_generation != source_generation || sm->removing || sm->fault ||
		    (sm->pps_lease && sm->pps_lease != lease)) {
			ret = -ESTALE;
		} else {
			sm->pps_lease = lease;
			sm->pps_source_generation = source_generation;
			sm->pps_mv = sm->pps_ma = 0;
			sm->pps_previous_mv = sm->pps_previous_ma = 0;
			sm->pps_restoring = true;
		}
		mutex_unlock(&sm->lock);
	}
	if (!ret && sample.online == 2)
		ret = power_supply_set_property(sm->tcp_supply,
					       POWER_SUPPLY_PROP_ONLINE, &value);
	if (!ret)
		ret = sm5714_read_fixed_pinned(sm, &fixed);
	if (!ret && (fixed.instance != instance ||
		     fixed.source_generation != source_generation))
		ret = -ESTALE;
	if (!ret)
		*out = fixed;
	mutex_lock(&sm->lock);
	if (sm->port_instance == instance && sm->pps_lease == lease &&
	    sm->pps_source_generation == source_generation)
		sm5714_pps_revoke_locked(sm);
	mutex_unlock(&sm->lock);
	return ret;
}

/* Caller-proven pump OFF; serialize against releasing its switching lease. */
int sm5714_pd_restore_fixed(u64 instance, u64 source_generation, u64 lease,
			   struct sm5714_pd_snapshot *out)
{
	struct sm5714_pd_snapshot sample = {};
	struct sm5714_usbpd *sm;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	if (!instance || !source_generation || !lease)
		return -EINVAL;
	ret = sm5714_port_get(&sm, &sample);
	if (ret)
		return ret;
	if (!mutex_trylock(&sm->control_lock)) {
		ret = -EBUSY;
		goto put;
	}
	ret = sm5714_restore_fixed_pinned(sm, instance, source_generation, lease, out);
	mutex_unlock(&sm->control_lock);
put:
	sm5714_port_put(sm);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_pd_restore_fixed);

int sm5714_pd_release_fixed(u64 instance, u64 source_generation, u64 lease,
			    const struct sm5714_fixed_proof *proof)
{
	struct sm5714_pd_snapshot sample = {}, present = {};
	struct sm5714_usbpd *sm;
	u64 now;
	int ret;

	if (!proof || !instance || !source_generation || !lease || !proof->pump_off ||
	    proof->ibus_ua)
		return -EINVAL;
	ret = sm5714_port_get(&sm, &sample);
	if (ret)
		return ret;
	if (!mutex_trylock(&sm->control_lock)) {
		ret = -EBUSY;
		goto put;
	}
	ret = sm5714_read_fixed_pinned(sm, &sample);
	if (ret)
		goto unlock;
	mutex_lock(&sm->lock);
	ret = sm5714_snapshot_locked(sm, &present);
	if (!ret && (present.instance != instance ||
		     present.source_generation != source_generation ||
		     present.budget_generation != sample.budget_generation ||
		     present.pps_contract))
		ret = -ESTALE;
	now = ktime_to_ms(ktime_get_boottime());
	if (!ret && (!proof->observed_ms || now < proof->observed_ms ||
		     now - proof->observed_ms > 100))
		ret = -ESTALE;
	if (!ret && !sm5714_fixed_vbus_valid(sample.budget_mv, proof->vbus_uv))
		ret = -ERANGE;
	/* TCPC -> try-only companion/charger. Authorize the unchanged ordinary
	 * worker; no producer wait, IIO/I2C/TCPM setter while holding this gate.
	 * Source reset/withdrawal cannot interleave authorization release.
	 */
	if (!ret)
		ret = sm5714_battery_switching_release_async(lease);
	mutex_unlock(&sm->lock);
unlock:
	mutex_unlock(&sm->control_lock);
put:
	sm5714_port_put(sm);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_pd_release_fixed);

/* Pair validation does not select an APDO: TCPM still chooses and builds RDOs. */
static bool sm5714_pps_pair_locked(struct sm5714_usbpd *sm,
				  unsigned int mv, unsigned int ma)
{
	unsigned int i;
	u32 rdo;

	lockdep_assert_held(&sm->lock);
	if (!sm->operating_snk_mw || mv < SM5714_PPS_MIN_MV ||
	    mv > SM5714_PPS_MAX_MV || ma < 100 || ma > SM5714_PPS_MAX_MA ||
	    mv % 20 || ma % 50 || mv * ma / 1000 < sm->operating_snk_mw)
		return false;
	for (i = 0; i < sm->nr_source_pdos; i++) {
		rdo = RDO_PROG(i + 1, mv, ma, RDO_USB_COMM | RDO_NO_SUSPEND);
		if (sm5714_validate_pps_request(sm->source_pdos[i], rdo))
			return true;
	}
	return false;
}

static int sm5714_pps_step(struct sm5714_usbpd *sm, u64 instance, u64 source,
			  u64 lease, unsigned int mv, unsigned int ma,
			  enum power_supply_property prop, int value,
			  bool *mutated, struct sm5714_pd_snapshot *out)
{
	struct sm5714_pd_snapshot sample = {};
	union power_supply_propval val = { .intval = value };
	int ret;

	ret = sm5714_battery_switching_check(lease);
	if (ret)
		return ret;
	mutex_lock(&sm->lock);
	ret = sm5714_snapshot_locked(sm, &sample);
	if (!ret && (sample.instance != instance || sample.source_generation != source ||
		     sm->pps_lease != lease || sm->pps_source_generation != source))
		ret = -ESTALE;
	if (!ret && !sm5714_pps_pair_locked(sm, mv, ma))
		ret = -ERANGE;
	if (!ret) {
		sm->pps_previous_mv = sm->budget_mv;
		sm->pps_previous_ma = sm->budget_ma;
		sm->pps_mv = mv;
		sm->pps_ma = ma;
	}
	mutex_unlock(&sm->lock);
	if (ret)
		return ret;
	*mutated = true;
	ret = power_supply_set_property(sm->tcp_supply, prop, &val);
	if (!ret)
		ret = sm5714_battery_switching_check(lease);
	if (!ret)
		ret = sm5714_read_contract_pinned(sm, &sample, true);
	if (!ret && (sample.instance != instance || sample.source_generation != source ||
		     sample.budget_mv != mv || sample.budget_ma != ma))
		ret = -ESTALE;
	if (!ret)
		*out = sample;
	return ret;
}

/* Protocol-only operation: no live caller, pump control, or permission to ON.
 * Caller must stop pump before EVERY operation, including unchanged refresh.
 */
int sm5714_pd_request_pps(u64 instance, u64 source_generation, u64 lease,
			 unsigned int mv, unsigned int ma,
			 struct sm5714_pd_snapshot *out)
{
	struct sm5714_pd_snapshot sample = {}, result = {}, fixed = {};
	struct sm5714_usbpd *sm;
	unsigned int old_mv, old_ma;
	bool mutated = false, current_first;
	int ret, cleanup;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	if (!instance || !source_generation || !lease)
		return -EINVAL;
	ret = sm5714_port_get(&sm, &sample);
	if (ret)
		return ret;
	if (!mutex_trylock(&sm->control_lock)) {
		ret = -EBUSY;
		goto put;
	}
	ret = sm5714_read_contract_pinned(sm, &result, sample.pps_contract);
	if (!ret)
		ret = sm5714_restore_token(sm, instance, source_generation);
	if (!ret)
		ret = sm5714_battery_switching_check(lease);
	if (ret)
		goto done;
	old_mv = result.budget_mv;
	old_ma = result.budget_ma;
	mutex_lock(&sm->lock);
	if (!sm5714_pps_pair_locked(sm, mv, ma) ||
	    !sm5714_pps_pair_locked(sm, old_mv, old_ma)) {
		ret = -ERANGE;
	} else if ((!result.pps_contract && (old_mv != 9000 || sm->pps_lease)) ||
		   (result.pps_contract && (sm->pps_lease != lease ||
		    sm->pps_source_generation != source_generation))) {
		ret = -ESTALE;
	}
	current_first = sm5714_pps_pair_locked(sm, old_mv, ma);
	if (!ret && !current_first && !sm5714_pps_pair_locked(sm, mv, old_ma))
		ret = -ERANGE;
	if (!ret) {
		sm->pps_lease = lease;
		sm->pps_source_generation = source_generation;
		sm->pps_restoring = false;
		sm->pps_operation_active = true;
	}
	mutex_unlock(&sm->lock);
	if (ret)
		goto done;
	if (!result.pps_contract) {
		ret = sm5714_pps_step(sm, instance, source_generation, lease, old_mv, old_ma,
				      POWER_SUPPLY_PROP_ONLINE, 2, &mutated, &result);
		if (ret)
			goto failed;
	}
	if (current_first) {
		if (ma != old_ma || (mv == old_mv && sample.pps_contract))
			ret = sm5714_pps_step(sm, instance, source_generation, lease, old_mv, ma,
					      POWER_SUPPLY_PROP_CURRENT_NOW, ma * 1000,
					      &mutated, &result);
		if (!ret && mv != old_mv)
			ret = sm5714_pps_step(sm, instance, source_generation, lease, mv, ma,
					      POWER_SUPPLY_PROP_VOLTAGE_NOW, mv * 1000,
					      &mutated, &result);
	} else {
		ret = sm5714_pps_step(sm, instance, source_generation, lease, mv, old_ma,
				      POWER_SUPPLY_PROP_VOLTAGE_NOW, mv * 1000, &mutated, &result);
		if (!ret && ma != old_ma)
			ret = sm5714_pps_step(sm, instance, source_generation, lease, mv, ma,
					      POWER_SUPPLY_PROP_CURRENT_NOW, ma * 1000,
					      &mutated, &result);
	}
	if (ret)
		goto failed;
	*out = result;
	goto done;
failed:
	if (mutated) {
		cleanup = sm5714_restore_fixed_pinned(sm, instance, source_generation,
					     lease, &fixed);
		dev_warn_ratelimited(sm->dev, "PPS operation refused %d; fixed restore %d; switching inhibited\n",
				     ret, cleanup);
	}
	mutex_lock(&sm->lock);
	if (sm->port_instance == instance && sm->pps_lease == lease &&
	    sm->pps_source_generation == source_generation)
		sm5714_pps_revoke_locked(sm);
	mutex_unlock(&sm->lock);
done:
	mutex_lock(&sm->lock);
	if (sm->port_instance == instance && sm->pps_lease == lease &&
	    sm->pps_source_generation == source_generation)
		sm->pps_operation_active = false;
	mutex_unlock(&sm->lock);
	mutex_unlock(&sm->control_lock);
put:
	sm5714_port_put(sm);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_pd_request_pps);

/* Read-only active PPS receipt; no Request, budget callback or lease release.
 * The control gate excludes owned entry/refresh/restore, while the lifetime
 * pin spans every supplier access. Short transport checks bracket the native
 * getter without holding the transport/registry mutex across it.
 */
static int sm5714_owned_observer_token(struct sm5714_usbpd *sm,
				      const struct sm5714_pd_snapshot *receipt,
				      u64 instance, u64 source_generation, u64 lease)
{
	struct sm5714_pd_snapshot present = {};
	int ret;

	mutex_lock(&sm->lock);
	ret = sm5714_snapshot_locked(sm, &present);
	if (!ret && (present.instance != instance ||
		     present.source_generation != source_generation ||
		     present.budget_generation != receipt->budget_generation ||
		     !present.pps_contract || !present.charge_requested ||
		     sm->pps_lease != lease ||
		     sm->pps_source_generation != source_generation ||
		     sm->pps_operation_active || sm->pps_restoring ||
		     sm->pps_mv != present.budget_mv || sm->pps_ma != present.budget_ma))
		ret = -ESTALE;
	if (!ret && !sm5714_pps_pair_locked(sm, present.budget_mv, present.budget_ma))
		ret = -ERANGE;
	mutex_unlock(&sm->lock);
	return ret;
}

int sm5714_pd_read_owned_snapshot(u64 instance, u64 source_generation, u64 lease,
				 struct sm5714_pd_snapshot *out)
{
	struct sm5714_pd_snapshot seed = {}, observed = {};
	struct sm5714_usbpd *sm;
	int ret;

	if (!out)
		return -EINVAL;
	memset(out, 0, sizeof(*out));
	if (!instance || !source_generation || !lease)
		return -EINVAL;
	ret = sm5714_port_get(&sm, &seed);
	if (ret)
		return ret;
	if (!mutex_trylock(&sm->control_lock)) {
		ret = -EBUSY;
		goto put;
	}
	ret = sm5714_owned_observer_token(sm, &seed, instance, source_generation, lease);
	if (!ret)
		ret = sm5714_battery_switching_check(lease);
	if (!ret)
		ret = sm5714_read_contract_pinned(sm, &observed, true);
	if (!ret && observed.budget_generation != seed.budget_generation)
		ret = -ESTALE;
	if (!ret)
		ret = sm5714_battery_switching_check(lease);
	if (!ret)
		ret = sm5714_owned_observer_token(sm, &observed, instance, source_generation, lease);
	if (!ret)
		*out = observed;
	mutex_unlock(&sm->control_lock);
put:
	sm5714_port_put(sm);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_pd_read_owned_snapshot);

static int sm5714_current_port_show(struct seq_file *seq, void *unused)
{
	struct sm5714_pd_snapshot sample;
	unsigned int i;
	int ret = sm5714_pd_read_snapshot(&sample);

	(void)unused;
	seq_printf(seq, "format=sm5714-current-port-v1\nret=%d\ncharging_grant=0\n"
		   "values_are_not_physical_measurements=1\n", ret);
	if (ret)
		return 0;
	seq_printf(seq, "instance=%llu\nsource_generation=%llu\nbudget_generation=%llu\n"
		   "started_ms=%llu\ncompleted_ms=%llu\nonline=%d\nusb_type=%d\n"
		   "voltage_uv=%d\ncurrent_ua=%d\nbudget_mv=%u\nbudget_ma=%u\n"
		   "charge_requested=%u\nnr_source_pdos=%u\n",
		   (unsigned long long)sample.instance,
		   (unsigned long long)sample.source_generation,
		   (unsigned long long)sample.budget_generation,
		   (unsigned long long)sample.started_ms,
		   (unsigned long long)sample.completed_ms, sample.online, sample.usb_type,
		   sample.voltage_uv, sample.current_ua, sample.budget_mv, sample.budget_ma,
		   sample.charge_requested, sample.nr_source_pdos);
	for (i = 0; i < sample.nr_source_pdos; i++)
		seq_printf(seq, "source_pdo_%u=0x%08x\n", i + 1, sample.source_pdos[i]);
	return 0;
}
DEFINE_SHOW_ATTRIBUTE(sm5714_current_port);

static void sm5714_snapshot_debug_remove(void *data)
{
	struct sm5714_usbpd *sm = data;

	debugfs_remove_recursive(sm->snapshot_debug);
}

static void sm5714_snapshot_debug_init(struct sm5714_usbpd *sm)
{
	char name[64];

	snprintf(name, sizeof(name), "sm5714-%s", dev_name(sm->dev));
	sm->snapshot_debug = debugfs_create_dir(name, NULL);
	if (IS_ERR_OR_NULL(sm->snapshot_debug))
		return;
	debugfs_create_file("current-port", 0400, sm->snapshot_debug, NULL,
			    &sm5714_current_port_fops);
	devm_add_action_or_reset(sm->dev, sm5714_snapshot_debug_remove, sm);
}

/* No bus retry/reset loop: first transport failure latches charger off. */
static int sm5714_result(struct sm5714_usbpd *sm, int ret)
{
	bool first;

	if (ret < 0) {
		mutex_lock(&sm->lock);
		first = !sm->fault;
		sm->fault = true;
		sm5714_forget_source(sm);
		mutex_unlock(&sm->lock);
		if (first) {
			sm5714_battery_typec_fault();
			dev_err(sm->dev, "TCPC fault %d; switching charge inhibited\n", ret);
		}
	}
	return ret;
}

static int sm5714_usbpd_init(struct tcpc_dev *tcpc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	/* Fedora same-model masks; read INT1..5 clears edge latches (Samsung). */
	static const u8 masks[5] = { 0xe6, 0xcf, 0xff, 0x08, 0xff };
	unsigned int state;
	u8 pending[5];
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	mutex_lock(&sm->lock);
	sm5714_forget_source(sm);
	/* Fedora/Samsung normal (non water-detection) CORR initialization. */
	ret = regmap_write(sm->regmap, SM5714_REG_CORR_CNTL5, 0x00);
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CORR_CNTL4, 0x00);
	if (!ret)
		ret = regmap_read(sm->regmap, SM5714_REG_PD_STATE3, &state);
	/* Samsung protocol-layer RX flush; Fedora/Samsung retained ResetDone ack. */
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_RX_BUF_ST, 0x10);
	if (!ret && (state & 0x06))
		ret = regmap_write(sm->regmap, SM5714_REG_PD_CNTL4, 0x01);
	/* Samsung set_vconn_source(OFF) and set_snk/set_ufp: preserve other bits. */
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL5, 0x18);
	if (!ret)
		ret = regmap_update_bits(sm->regmap, SM5714_REG_PD_CNTL2,
					 GENMASK(1, 0), 0);
	/* Force Rd, not autonomous DRP; Samsung sm5714_set_attach(UFP). */
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL1, 0x45);
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL3, 0x82);
	if (!ret)
		ret = regmap_bulk_read(sm->regmap, SM5714_REG_INT1,
				       pending, sizeof(pending));
	if (!ret)
		ret = regmap_bulk_write(sm->regmap, SM5714_REG_MASK1,
					masks, sizeof(masks));
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_get_vbus(struct tcpc_dev *tcpc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	unsigned int status;
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	ret = regmap_read(sm->regmap, SM5714_REG_STATUS1, &status);
	return ret ? sm5714_result(sm, ret) : !!(status & SM5714_VBUS_POK);
}

static int sm5714_usbpd_get_current_limit(struct tcpc_dev *tcpc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	/* TCPM calls this for default Rp; retain Stage1 BC1.2 SDP/CDP/DCP. */
	ret = sm5714_battery_get_bc12_limit();
	return ret < 0 ? sm5714_result(sm, ret) : ret;
}

static int sm5714_usbpd_get_cc(struct tcpc_dev *tcpc,
			      enum typec_cc_status *cc1, enum typec_cc_status *cc2)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	enum typec_cc_status active = TYPEC_CC_OPEN;
	unsigned int cc;
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	ret = regmap_read(sm->regmap, SM5714_REG_CC_STATUS, &cc);
	if (ret)
		return sm5714_result(sm, ret);
	/* Samsung CC_STATUS: only a Source partner is accepted by this Sink. */
	if ((cc & SM5714_CC_ATTACH_MASK) == SM5714_CC_SOURCE) {
		switch (cc & SM5714_CC_RP_MASK) {
		case 0x08:
			active = TYPEC_CC_RP_1_5;
			break;
		case 0x10:
		case 0x18:
			active = TYPEC_CC_RP_3_0;
			break;
		default:
			active = TYPEC_CC_RP_DEF;
			break;
		}
	}
	*cc1 = cc & SM5714_CC_FLIPPED ? TYPEC_CC_OPEN : active;
	*cc2 = cc & SM5714_CC_FLIPPED ? active : TYPEC_CC_OPEN;
	return 0;
}

static int sm5714_usbpd_set_cc(struct tcpc_dev *tcpc, enum typec_cc_status cc)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	if (cc != TYPEC_CC_OPEN && cc != TYPEC_CC_RD)
		return -EOPNOTSUPP;
	mutex_lock(&sm->lock);
	/* Samsung force-detach=0x88, force UFP=0x45/0x82; no Rp writes. */
	if (cc == TYPEC_CC_OPEN) {
		sm5714_forget_source(sm);
		ret = regmap_write(sm->regmap, SM5714_REG_CC_CNTL3, 0x88);
	} else {
		ret = regmap_update_bits(sm->regmap, SM5714_REG_CC_CNTL1,
					 0xff, 0x45);
		if (!ret)
			ret = regmap_update_bits(sm->regmap, SM5714_REG_CC_CNTL3,
						 0xff, 0x82);
	}
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_polarity(struct tcpc_dev *tcpc,
				    enum typec_cc_polarity polarity)
{
	/* Fedora: CC_STATUS selects hardware PD lane; no external mux required. */
	return READ_ONCE(tcpc_to_sm5714(tcpc)->fault) ? -EIO : 0;
}

static int sm5714_usbpd_set_vconn(struct tcpc_dev *tcpc, bool on)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);

	if (on)
		return -EOPNOTSUPP;
	if (READ_ONCE(sm->fault))
		return -EIO;
	/* Samsung OFF=0x18; no source VCONN or cable discovery is implemented. */
	return sm5714_result(sm, regmap_write(sm->regmap,
					    SM5714_REG_CC_CNTL5, 0x18));
}

static int sm5714_usbpd_set_vbus(struct tcpc_dev *tcpc, bool on, bool charge)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (on)
		return -EOPNOTSUPP;
	if (READ_ONCE(sm->removing))
		return charge ? -ESHUTDOWN : 0;
	if (READ_ONCE(sm->fault) && charge)
		return -EIO;
	/* Required by TCPM: apply Sink charge gate, never generate VBUS. */
	if (!charge) {
		mutex_lock(&sm->lock);
		sm5714_pps_revoke_locked(sm);
		mutex_unlock(&sm->lock);
	}
	sm5714_budget_begin(sm);
	ret = sm5714_battery_set_typec_charge(charge);
	sm5714_budget_end(sm, ret, false, 0, 0, charge, false);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_current_limit(struct tcpc_dev *tcpc, u32 ma, u32 mv)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	enum sm5714_contract_kind kind;
	u64 lease, source;
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	mutex_lock(&sm->lock);
	lease = sm->pps_lease;
	source = sm->source_generation;
	kind = sm->last_request_pps ? SM5714_CONTRACT_PPS : SM5714_CONTRACT_FIXED;
	if (sm->pps_restoring && mv && ma > 0 &&
	    ma <= SM5714_STANDBY_MAX_MW * 1000 / mv && mv == sm->budget_mv)
		kind = SM5714_CONTRACT_STANDBY;
	ret = 0;
	if (lease && kind != SM5714_CONTRACT_STANDBY &&
	    (sm->request_mv != mv || sm->request_ma != ma))
		ret = -ERANGE;
	if (!mv && !ma) {
		sm5714_pps_revoke_locked(sm);
		lease = 0;
		ret = 0;
	}
	mutex_unlock(&sm->lock);
	if (ret)
		return sm5714_result(sm, ret);
	sm5714_budget_begin(sm);
	if (lease)
		ret = sm5714_battery_set_owned_contract(lease, mv, ma, kind);
	else
		ret = sm5714_battery_set_pd_contract(mv, ma);
	if (!ret && lease) {
		mutex_lock(&sm->lock);
		if (sm->pps_lease != lease || sm->source_generation != source ||
		    sm->pps_source_generation != source)
			ret = -ESTALE;
		mutex_unlock(&sm->lock);
	}
	sm5714_budget_end(sm, ret, true, mv, ma, false, kind != SM5714_CONTRACT_FIXED);
	if (!ret)
		dev_info(sm->dev, "TCPM Sink budget: %u mV %u mA (not measured VBUS)\n", mv, ma);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_pd_rx(struct tcpc_dev *tcpc, bool on)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	int ret;

	if (READ_ONCE(sm->fault))
		return -EIO;
	/* Samsung set_pd_control(): ordinary SOP receive=0x08, off=0x00. */
	mutex_lock(&sm->lock);
	if (!on)
		sm5714_forget_source(sm);
	ret = regmap_write(sm->regmap, SM5714_REG_PD_CNTL1, on ? 0x08 : 0x00);
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

static int sm5714_usbpd_set_roles(struct tcpc_dev *tcpc, bool attached,
				 enum typec_role role, enum typec_data_role data)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);

	if (role != TYPEC_SINK || data != TYPEC_DEVICE)
		return -EOPNOTSUPP;
	if (READ_ONCE(sm->fault))
		return -EIO;
	/* Samsung set_snk/set_ufp: role bits1:0; DWC3 stays peripheral. */
	return sm5714_result(sm, regmap_update_bits(sm->regmap,
						 SM5714_REG_PD_CNTL2, GENMASK(1, 0), 0));
}

/* Guard the actual Request frame without choosing a PDO or changing policy. */
static bool sm5714_request_allowed(struct sm5714_usbpd *sm, u32 rdo)
{
	unsigned int mv = ((rdo >> 9) & 0x7ff) * 20;
	unsigned int ma = (rdo & 0x7f) * 50;

	if (sm5714_validate_request(sm->source_pdos, sm->nr_source_pdos, rdo, false))
		return true;
	return sm->pps_lease && sm->pps_operation_active && !sm->pps_restoring &&
		sm->pps_source_generation == sm->source_generation &&
		((mv == sm->pps_mv && ma == sm->pps_ma) ||
		 (mv == sm->pps_previous_mv && ma == sm->pps_previous_ma)) &&
		sm5714_validate_request(sm->source_pdos, sm->nr_source_pdos, rdo, true);
}

static int sm5714_usbpd_transmit(struct tcpc_dev *tcpc,
			       enum tcpm_transmit_type type, const struct pd_message *msg,
			       unsigned int negotiated_rev)
{
	struct sm5714_usbpd *sm = tcpc_to_sm5714(tcpc);
	unsigned int count;
	u64 lease, source;
	bool pps_request = false;
	int ret = 0;

	if (READ_ONCE(sm->fault))
		return -EIO;
	if (type != TCPC_TX_SOP && type != TCPC_TX_HARD_RESET)
		return -EOPNOTSUPP;
	mutex_lock(&sm->lock);
	if (type == TCPC_TX_HARD_RESET) {
		/* Samsung hard_reset(): PD_CNTL4 bit2; IRQ HCRST_DONE completes TX. */
		sm5714_forget_source(sm);
		ret = regmap_update_bits(sm->regmap, SM5714_REG_PD_CNTL4, BIT(2), BIT(2));
		goto out;
	}
	if (!msg) {
		ret = -EINVAL;
		goto out;
	}
	count = pd_header_cnt_le(msg->header);
	/* This driver has no extended-message transport or EPR implementation.
	 * Type2/count0 is Get_Source_Cap control, not a malformed Request.
	 */
	if (le16_to_cpu(msg->header) & PD_HEADER_EXT_HDR) {
		ret = -EOPNOTSUPP;
		goto out;
	}
	if (!count && pd_header_type_le(msg->header) == PD_CTRL_SOFT_RESET)
		sm5714_forget_source(sm);
	if (pd_header_type_le(msg->header) == PD_DATA_REQUEST && count &&
	    (count != 1 || !sm5714_request_allowed(sm, le32_to_cpu(msg->payload[0])))) {
		ret = -ERANGE;
		goto out;
	}
	if (pd_header_type_le(msg->header) == PD_DATA_REQUEST && count) {
		u32 rdo = le32_to_cpu(msg->payload[0]);

		pps_request = pdo_type(sm->source_pdos[rdo_index(rdo) - 1]) != PDO_TYPE_FIXED;
		if (pps_request) {
			lease = sm->pps_lease;
			source = sm->source_generation;
			mutex_unlock(&sm->lock);
			ret = sm5714_battery_switching_check(lease);
			mutex_lock(&sm->lock);
			if (!ret && (sm->source_generation != source || sm->pps_lease != lease ||
				     !sm5714_request_allowed(sm, rdo) || sm->fault || sm->removing))
				ret = -ESTALE;
			if (ret)
				goto out;
		}
	}
	/* Samsung write_msg_header/obj/send_msg: little-endian header/payload. */
	ret = regmap_bulk_write(sm->regmap, SM5714_REG_TX_HEADER,
				&msg->header, sizeof(msg->header));
	if (!ret && count)
		ret = regmap_bulk_write(sm->regmap, SM5714_REG_TX_PAYLOAD,
					msg->payload, count * sizeof(msg->payload[0]));
	if (!ret)
		ret = regmap_write(sm->regmap, SM5714_REG_TX_REQ, 0x07); /* SOP only */
	if (!ret && pd_header_type_le(msg->header) == PD_DATA_REQUEST && count) {
		u32 rdo = le32_to_cpu(msg->payload[0]);

		sm->last_request_pps = pps_request;
		sm->request_mv = pps_request ? ((rdo >> 9) & 0x7ff) * 20 :
			pdo_fixed_voltage(sm->source_pdos[rdo_index(rdo) - 1]);
		sm->request_ma = pps_request ? (rdo & 0x7f) * 50 : rdo_op_current(rdo);
	}
out:
	mutex_unlock(&sm->lock);
	return sm5714_result(sm, ret);
}

/* Called under transport lock. Deliver only a completely read SOP frame. */
static int sm5714_usbpd_receive(struct sm5714_usbpd *sm)
{
	struct pd_message msg = {};
	unsigned int count, origin, i;
	int ret, ack;

	ret = regmap_bulk_read(sm->regmap, SM5714_REG_RX_HEADER,
			       &msg.header, sizeof(msg.header));
	if (ret)
		goto acknowledge;
	count = pd_header_cnt_le(msg.header);
	if (count) {
		ret = regmap_bulk_read(sm->regmap, SM5714_REG_RX_PAYLOAD,
				       msg.payload, count * sizeof(msg.payload[0]));
		if (ret)
			goto acknowledge;
	}
	ret = regmap_read(sm->regmap, SM5714_REG_RX_SRC, &origin);
	if (ret)
		goto acknowledge;
	/* Samsung RX_SRC low nibble0=SOP; no cable/alternate-mode transport. */
	if (!(origin & 0x0f)) {
		if (!count && pd_header_type_le(msg.header) == PD_CTRL_SOFT_RESET)
			sm5714_forget_source(sm);
		if (count && !(le16_to_cpu(msg.header) & PD_HEADER_EXT_HDR) &&
		    pd_header_type_le(msg.header) == PD_DATA_SOURCE_CAP) {
			sm5714_forget_source(sm);
			sm->nr_source_pdos = count;
			for (i = 0; i < count; i++)
				sm->source_pdos[i] = le32_to_cpu(msg.payload[i]);
		}
		tcpm_pd_receive(sm->port, &msg, TCPC_TX_SOP);
	}
acknowledge:
	/* Samsung receive_message(): RX_BUF=0x80 marks message consumed. */
	ack = regmap_write(sm->regmap, SM5714_REG_RX_BUF, 0x80);
	return ret ? ret : ack;
}

static irqreturn_t sm5714_usbpd_irq(int irq, void *data)
{
	struct sm5714_usbpd *sm = data;
	u8 intr[5];
	int ret;

	if (READ_ONCE(sm->removing))
		return IRQ_HANDLED;
	mutex_lock(&sm->lock);
	ret = regmap_bulk_read(sm->regmap, SM5714_REG_INT1, intr, sizeof(intr));
	if (!ret && (intr[0] & (SM5714_ATTACH | SM5714_DETACH) ||
		     intr[3] & (SM5714_HRST_RX | SM5714_HRST_DONE)))
		sm5714_forget_source(sm);
	if (!ret && (intr[3] & SM5714_RX_DONE)) {
		/* Detach/reset may share an IRQ with a buffered old frame. Drain it
		 * without publishing capabilities or delivering it to the new epoch.
		 */
		if (intr[0] & SM5714_DETACH ||
		    intr[3] & (SM5714_HRST_RX | SM5714_HRST_DONE))
			ret = regmap_write(sm->regmap, SM5714_REG_RX_BUF, 0x80);
		else
			ret = sm5714_usbpd_receive(sm);
	}
	if (!ret) {
		/* Hard-reset completion is also a TX completion, not a timeout. */
		if (intr[3] & SM5714_TX_ERR)
			tcpm_pd_transmit_complete(sm->port, TCPC_TX_FAILED);
		else if (intr[3] & SM5714_TX_DISCARD)
			tcpm_pd_transmit_complete(sm->port, TCPC_TX_DISCARDED);
		else if (intr[3] & (SM5714_TX_DONE | SM5714_HRST_DONE))
			tcpm_pd_transmit_complete(sm->port, TCPC_TX_SUCCESS);
		if (intr[3] & SM5714_HRST_RX)
			tcpm_pd_hard_reset(sm->port);
	}
	mutex_unlock(&sm->lock);
	if (ret) {
		/* Level-low IRQ plus failed clear must not form an interrupt storm. */
		disable_irq_nosync(irq);
		sm5714_result(sm, ret);
		return IRQ_HANDLED;
	}
	if (intr[0] & (SM5714_ATTACH | SM5714_DETACH) || intr[1] & SM5714_SRC_ADV)
		tcpm_cc_change(sm->port);
	if (intr[0] & SM5714_VBUS_POK || intr[1] & SM5714_VBUS_0V)
		tcpm_vbus_change(sm->port);
	return IRQ_HANDLED;
}

static void sm5714_usbpd_resync(struct work_struct *work)
{
	struct sm5714_usbpd *sm = container_of(to_delayed_work(work),
						     struct sm5714_usbpd, cc_resync_work);

	/* Fedora one-shot1.5s resync covers a pre-registration attach edge. */
	if (!READ_ONCE(sm->fault) && !READ_ONCE(sm->removing)) {
		tcpm_cc_change(sm->port);
		tcpm_vbus_change(sm->port);
	}
}

static int sm5714_usbpd_probe(struct i2c_client *client)
{
	struct device *dev = &client->dev;
	struct sm5714_usbpd *sm;
	const u8 masked[5] = { 0xff, 0xff, 0xff, 0xff, 0xff };
	int ret;

	if (client->irq <= 0)
		return -EINVAL;
	sm = devm_kzalloc(dev, sizeof(*sm), GFP_KERNEL);
	if (!sm)
		return -ENOMEM;
	sm->dev = dev;
	sm->irq = client->irq;
	sm->regmap = devm_regmap_init_i2c(client, &sm5714_regmap_config);
	if (IS_ERR(sm->regmap))
		return PTR_ERR(sm->regmap);
	mutex_init(&sm->lock);
	mutex_init(&sm->control_lock);
	atomic_set(&sm->snapshot_users, 0);
	init_waitqueue_head(&sm->snapshot_wait);
	INIT_DELAYED_WORK(&sm->cc_resync_work, sm5714_usbpd_resync);
	i2c_set_clientdata(client, sm);
	sm->connector = device_get_named_child_node(dev, "connector");
	if (!sm->connector)
		return -EINVAL;
	ret = sm5714_battery_typec_claim();
	if (ret)
		goto put_connector;
	ret = regmap_bulk_write(sm->regmap, SM5714_REG_MASK1, masked, sizeof(masked));
	if (ret)
		goto fault;
	/* Request before unmask, but enable only after a live TCPM port exists. */
	ret = devm_request_threaded_irq(dev, client->irq, NULL, sm5714_usbpd_irq,
				       IRQF_ONESHOT | IRQF_TRIGGER_LOW | IRQF_NO_AUTOEN,
				       dev_name(dev), sm);
	if (ret)
		goto fault;
	{
		u32 operating_uw = 0;

		fwnode_property_read_u32(sm->connector, "op-sink-microwatt", &operating_uw);
		sm->operating_snk_mw = operating_uw / 1000;
	}

	sm->tcpc.fwnode = sm->connector;
	sm->tcpc.init = sm5714_usbpd_init;
	sm->tcpc.get_vbus = sm5714_usbpd_get_vbus;
	sm->tcpc.get_current_limit = sm5714_usbpd_get_current_limit;
	sm->tcpc.get_cc = sm5714_usbpd_get_cc;
	sm->tcpc.set_cc = sm5714_usbpd_set_cc;
	sm->tcpc.set_polarity = sm5714_usbpd_set_polarity;
	sm->tcpc.set_vconn = sm5714_usbpd_set_vconn;
	sm->tcpc.set_vbus = sm5714_usbpd_set_vbus;
	sm->tcpc.set_current_limit = sm5714_usbpd_set_current_limit;
	sm->tcpc.set_pd_rx = sm5714_usbpd_set_pd_rx;
	sm->tcpc.set_roles = sm5714_usbpd_set_roles;
	sm->tcpc.pd_transmit = sm5714_usbpd_transmit;
	/* TCPM7.2 ignores init's return: check explicitly before registering. */
	ret = sm5714_usbpd_init(&sm->tcpc);
	if (ret)
		goto fault;
	sm->port = tcpm_register_port(dev, &sm->tcpc);
	if (IS_ERR(sm->port)) {
		ret = PTR_ERR(sm->port);
		goto fault;
	}
	if (READ_ONCE(sm->fault)) {
		ret = -EIO;
		tcpm_unregister_port(sm->port);
		goto fault;
	}
	/* Pinned Linux TCPM registers this standard supply before returning. */
	{
		char *name = kasprintf(GFP_KERNEL, "tcpm-source-psy-%s", dev_name(dev));

		if (!name) {
			ret = -ENOMEM;
		} else {
			sm->tcp_supply = power_supply_get_by_name(name);
			kfree(name);
			ret = sm->tcp_supply ? 0 : -ENODEV;
		}
	}
	if (!ret)
		ret = sm5714_port_publish(sm);
	if (ret) {
		if (sm->tcp_supply)
			power_supply_put(sm->tcp_supply);
		tcpm_unregister_port(sm->port);
		goto fault;
	}
	sm5714_snapshot_debug_init(sm);
	enable_irq(client->irq);
	mod_delayed_work(system_dfl_wq, &sm->cc_resync_work, msecs_to_jiffies(1500));
	dev_info(dev, "SM-X710 fixed5/9V Sink/Device TCPC registered\n");
	return 0;
fault:
	sm5714_result(sm, ret);
put_connector:
	fwnode_handle_put(sm->connector);
	return dev_err_probe(dev, ret, "cannot register fixed-PD Sink\n");
}

static void sm5714_usbpd_remove(struct i2c_client *client)
{
	struct sm5714_usbpd *sm = i2c_get_clientdata(client);

	sm5714_port_unpublish(sm);
	disable_irq(client->irq);
	cancel_delayed_work_sync(&sm->cc_resync_work);
	WRITE_ONCE(sm->fault, true);
	mutex_lock(&sm->lock);
	sm5714_forget_source(sm);
	mutex_unlock(&sm->lock);
	sm5714_battery_typec_fault();
	power_supply_put(sm->tcp_supply);
	tcpm_unregister_port(sm->port);
	fwnode_handle_put(sm->connector);
}

static void sm5714_usbpd_shutdown(struct i2c_client *client)
{
	struct sm5714_usbpd *sm = i2c_get_clientdata(client);

	sm5714_port_unpublish(sm);
	disable_irq(client->irq);
	cancel_delayed_work_sync(&sm->cc_resync_work);
	WRITE_ONCE(sm->fault, true);
	mutex_lock(&sm->lock);
	sm5714_forget_source(sm);
	mutex_unlock(&sm->lock);
	sm5714_battery_typec_fault();
	/* Stop TCPM timers/worker before the I2C controllers shut down. */
	power_supply_put(sm->tcp_supply);
	tcpm_unregister_port(sm->port);
}

static const struct of_device_id sm5714_usbpd_of_match[] = {
	{ .compatible = "siliconmitus,sm5714-usbpd" },
	{ }
};
MODULE_DEVICE_TABLE(of, sm5714_usbpd_of_match);

static struct i2c_driver sm5714_usbpd_driver = {
	.driver = {
		.name = "sm5714-usbpd",
		.of_match_table = sm5714_usbpd_of_match,
	},
	.probe = sm5714_usbpd_probe,
	.remove = sm5714_usbpd_remove,
	.shutdown = sm5714_usbpd_shutdown,
};
module_i2c_driver(sm5714_usbpd_driver);
MODULE_DESCRIPTION("SM-X710 SM5714 fixed-PD Sink TCPC transport");
MODULE_LICENSE("GPL");
