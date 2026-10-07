// SPDX-License-Identifier: GPL-2.0-only
/*
 * Silicon Mitus SM5440 2:1 direct charger for the Samsung SM-X710.
 *
 * This is a deliberately small mainline-first driver.  Linux TCPM owns USB-PD
 * policy; this driver only requests a conservative PPS operating point, hands
 * the battery path over from SM5714, and programs the board's charge pump using
 * the register sequence published in Samsung's GPL source.  Every failure
 * turns the pump off and restores the fixed-PD switching charger.
 *
 * Derived from nacht20-de/gts9wifi-fedora-linux ab123e7d (GPL-2.0-only).
 * X710 adaptation: source/lease ownership, conservative limits and checked
 * fallback. Original source/hash/diff: reference/charging/sm5440-fedora-port.
 * Direct charging is disabled unless explicitly selected at boot.
 */

#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/module.h>
#include <linux/moduleparam.h>
#include <linux/power_supply.h>
#include <linux/suspend.h>
#include <linux/workqueue.h>
#include <linux/ktime.h>

#include "sm5714-stage2.h"
#include "sm5440-hw.h"

/*
 * Interrupt latches.  They are read-to-clear, and they are the only thing that
 * says *why* the chip cut the pump off -- otherwise a stop is just "CHG_ON went
 * away".  Bit names follow Silicon Mitus' own driver header.
 */
#define SM5440_REG_INT1			0x00
#define SM5440_REG_INT3			0x02
#define  SM5440_INT1_VOUTOVP		BIT(4)
#define  SM5440_INT1_VBATOVP		BIT(3)
#define  SM5440_INT3_VBUSOVP		BIT(7)
#define  SM5440_INT3_VBUSUVLO		BIT(6)
#define  SM5440_INT3_THEMSHDN		BIT(3)
#define  SM5440_INT3_STUP_FAIL		BIT(2)
#define  SM5440_INT3_REVBLK		BIT(1)
#define  SM5440_INT3_CFLY_SHORT		BIT(0)
#define SM5440_REG_STATUS1		0x08
#define SM5440_REG_STATUS3		0x0a
#define  SM5440_STATUS3_VBUSPOK		BIT(5)
#define SM5440_REG_CNTL1		0x0c
#define  SM5440_CNTL1_SW_RESET		BIT(0)
#define  SM5440_CNTL1_WDT_EN		BIT(7)
#define  SM5440_CNTL1_WDT_30S		(4 << 4)
#define SM5440_REG_CNTL2		0x0d
#define SM5440_REG_CNTL3		0x0e
#define SM5440_REG_CNTL4		0x0f
#define SM5440_REG_CNTL5		0x10
#define  SM5440_CNTL5_OP_MODE_MASK	GENMASK(3, 2)
#define  SM5440_CNTL5_CHG_ON		BIT(2)
#define SM5440_REG_CNTL6		0x11
#define SM5440_REG_CNTL7		0x12
#define SM5440_REG_VBUSCNTL		0x13
#define SM5440_REG_VBATCNTL		0x14
#define SM5440_REG_VOUTCNTL		0x15
#define SM5440_REG_IBUSCNTL		0x16
#define SM5440_REG_PRTNCNTL		0x19
#define SM5440_REG_THEMCNTL1		0x1a
#define SM5440_REG_ADCCNTL1		0x1c
#define  SM5440_ADCCNTL1_AVG_32		BIT(3)
#define  SM5440_ADCCNTL1_CONTINUOUS	BIT(1)
#define  SM5440_ADCCNTL1_ENABLE	BIT(0)
#define SM5440_REG_ADCCNTL2		0x1d
#define SM5440_REG_ADC_VBUS1		0x1e
#define SM5440_REG_ADC_IBUS1		0x22
#define SM5440_REG_ADC_DIETEMP		0x26
#define SM5440_REG_ADC_VBAT1		0x27
#define SM5440_REG_DEVICEID		0x2b

#define SM5440_POLL_MS			1000
#define SM5440_RETRY_MS			2000
#define SM5440_MAX_RETRY_MS		30000
#define SM5440_QUIET_RETRY_MS		300000
#define SM5440_MAX_FAILS		5

/*
 * TCPM answers -EAGAIN while its state machine is not in SNK_READY, or while the
 * source has not signalled SinkTxOK yet.  That is a "try again" condition, not
 * a failure, so the PD properties are retried briefly before giving up.
 */
#define SM5440_PD_RETRY_MS		200
#define SM5440_PD_RETRIES		5

#define SM5440_INITIAL_IBUS_MA		1800
#define SM5440_VBATREG_MV		4400

/* First mainline bring-up cap; the Fedora 3A/5A controls are not imported. */
#define SM5440_MAX_PPS_MA 1800
/* Test342 raw IBUS exceeded the software cap with an equal hardware setting.
 * Two 50mA steps of provisional bring-up margin; not an accuracy guarantee.
 * Keep the PPS request and the precise raw-current stop ceiling at 1800mA.
 */
#define SM5440_PROGRAM_IBUS_MA 1700
#define SM5440_PPS_V_STEP_MV 20
#define SM5440_REFRESH_TICKS 4
#define SM5440_ONCE_MS 30000
#define SM5440_ONCE_POLL_MS 100
#define SM5440_ONCE_GAP_MS 500
#define SM5440_ONCE_REFRESH_MS 4000
static bool direct_charge;
module_param(direct_charge, bool, 0400);
MODULE_PARM_DESC(direct_charge, "Explicit registered 1.8A direct-charge bring-up (default off)");
static bool direct_charge_once;
module_param(direct_charge_once, bool, 0400);
MODULE_PARM_DESC(direct_charge_once, "Registered one-shot <=30s 1.8A pump test, no restart (default off)");
static bool fixed_return_check;
module_param(fixed_return_check, bool, 0400);
MODULE_PARM_DESC(fixed_return_check, "Registered one-shot fixed9V OFF return proof (default off, no PPS)");
static bool pps_return_check;
module_param(pps_return_check, bool, 0400);
MODULE_PARM_DESC(pps_return_check, "Registered one-shot PPS/fixed return with pump OFF (default off)");
#define SM5440_FIXED_CHECK_WAIT_MS	300000

/*
 * Board tuning from the X710 device tree (sm5440,freq = 850, freq_siop = 450
 * 650, r_ttl = 320000): the vendor driver drops the pump's switching frequency
 * at low charge current and keeps the drop across the cable and connector in
 * the PPS operating point.  Samsung caps this board's PD path at 9 V.
 */
#define SM5440_FREQUENCY_KHZ		850
#define SM5440_FREQUENCY_SIOP2_KHZ	650
#define SM5440_FREQUENCY_SIOP1_KHZ	450
#define SM5440_SIOP_LEV1_MA		1100
#define SM5440_SIOP_LEV2_MA		1700
#define SM5440_R_TTL_MILLIOHM		320
#define SM5440_EXTRA_HEADROOM_MV	200
/*
 * The vendor's own ceiling: its dc_vbus_ovp_th is 11 V and the direct-charge
 * loop never asks for more than dc_vbus_ovp_th - 500.  The operating point needs
 * that room -- at the board's 3 A the cable and connector drop alone is
 * 3 A x 320 mOhm = 960 mV on top of twice the cell voltage -- so clamping lower
 * would starve the pump exactly where the current matters.
 */
#define SM5440_MAX_PPS_MV		10500

/* Linux TCPM owns negotiation; the existing battery lease owns Q4 handoff.
 * No Fedora fast_charge UI or unprotected global battery pointer is used.
 */
struct sm5440_direct {
	struct device *dev;
	struct i2c_client *client;
	struct power_supply *battery;
	struct delayed_work work;
	int target_mv;
	int target_ma;
	unsigned int pps_ticks;
	unsigned int fails;
	bool active;
	bool suspending, stopping, fault_latched, adc_running;
	u64 lease;
	struct sm5714_pd_snapshot source;
	u64 pack_instance;
	int last_cleanup_error;
	u64 fixed_check_deadline;
	bool fixed_check_done;
	bool direct_once_done;
	u64 direct_deadline_ms, direct_sample_ms, direct_refresh_ms;
	unsigned int direct_positive_samples;
	struct notifier_block pm_nb;
};

static int sm5440_once_settings(struct sm5440_direct *sm);
static int sm5440_once_measure(struct sm5440_direct *sm, bool running);

static int sm5440_update_bits(struct sm5440_direct *sm, u8 reg, u8 mask,
			      u8 val)
{
	int old;

	old = i2c_smbus_read_byte_data(sm->client, reg);
	if (old < 0)
		return old;

	return i2c_smbus_write_byte_data(sm->client, reg,
					 (old & ~mask) | (val & mask));
}

static int sm5440_read_adc_pair(struct sm5440_direct *sm, u8 reg)
{
	int high, low;

	high = i2c_smbus_read_byte_data(sm->client, reg);
	if (high < 0)
		return high;
	low = i2c_smbus_read_byte_data(sm->client, reg + 1);
	if (low < 0)
		return low;

	return (high << 5) | (low >> 3);
}

static int sm5440_adc_vbus_mv(struct sm5440_direct *sm)
{
	int raw = sm5440_read_adc_pair(sm, SM5440_REG_ADC_VBUS1);

	return raw < 0 ? raw : 4096 + raw;
}

static int sm5440_adc_ibus_ma(struct sm5440_direct *sm)
{
	int raw = sm5440_read_adc_pair(sm, SM5440_REG_ADC_IBUS1);

	return raw < 0 ? raw : (raw * 625) / 1000;
}

static int sm5440_adc_vbat_mv(struct sm5440_direct *sm)
{
	int raw = sm5440_read_adc_pair(sm, SM5440_REG_ADC_VBAT1);

	return raw < 0 ? raw : 2048 + (raw * 500) / 1000;
}

static int sm5440_adc_die_temp(struct sm5440_direct *sm)
{
	int raw = i2c_smbus_read_byte_data(sm->client,
					   SM5440_REG_ADC_DIETEMP);

	return raw < 0 ? raw : 225 + raw * 5;
}



static bool sm5440_direct_enabled(struct sm5440_direct *sm)
{
	return (READ_ONCE(direct_charge) ||
		(READ_ONCE(direct_charge_once) && !sm->direct_once_done)) &&
	       !READ_ONCE(fixed_return_check) &&
	       !READ_ONCE(pps_return_check) &&
        !READ_ONCE(sm->stopping) &&
        !READ_ONCE(sm->suspending) && !sm->fault_latched;
}

static bool sm5440_modes_valid(void)
{
	return (direct_charge + direct_charge_once + fixed_return_check +
		pps_return_check) <= 1;
}

/* Public snapshots admit fixed contracts only. Once PPS owns the handoff,
 * both sides of the pack coherence check must use the same leased PPS API.
 * It also rejects detach/replacement and a revoked lease before pump enable.
 */
static int sm5440_read_source(struct sm5440_direct *sm,
                             struct sm5714_pd_snapshot *source)
{
	if (sm->source.pps_contract)
		return sm5714_pd_read_owned_snapshot(sm->source.instance,
				sm->source.source_generation, sm->lease, source);

	return sm5714_pd_read_snapshot(source);
}

static int sm5440_read_pack(struct sm5440_direct *sm,
                            struct sm5714_pack_snapshot *pack)
{
	struct sm5714_pd_snapshot source, after;
	int ret;

	ret = sm5440_read_source(sm, &source);
	if (ret)
		return ret;
	if (!source.online || !source.charge_requested ||
					source.instance != sm->source.instance ||
					source.source_generation != sm->source.source_generation)
		return -ESTALE;
	ret = sm5714_battery_read_pack(sm->lease, pack);
	if (ret)
		return ret;
	if (!pack->battery_present || !pack->attached || !pack->thermal_normal ||
					pack->health != POWER_SUPPLY_HEALTH_GOOD ||
					pack->instance != sm->pack_instance ||
					pack->typec_mv != source.budget_mv || pack->typec_ma != source.budget_ma ||
					pack->capacity < 5 || pack->capacity >= 80 ||
					pack->voltage_uv < 3500000 || pack->voltage_uv >= 4400000 ||
					pack->pack_decic < 150 || pack->pack_decic >= 420)
		return -ERANGE;
	ret = sm5440_read_source(sm, &after);
	if (ret)
		return ret;
	if (source.instance != after.instance ||
					source.source_generation != after.source_generation ||
					source.budget_generation != after.budget_generation)
		return -ESTALE;
	return 0;
}

static int sm5440_pps_retry(struct sm5440_direct *sm, int mv, int ma)
{
	struct sm5714_pd_snapshot receipt;
	int i, ret = -EAGAIN;

	for (i = 0; i < SM5440_PD_RETRIES && ret == -EAGAIN; i++) {
		if (READ_ONCE(sm->suspending) || READ_ONCE(sm->stopping))
			return -ESHUTDOWN;
		if (i)
			msleep(SM5440_PD_RETRY_MS);
		ret = sm5714_pd_request_pps(sm->source.instance,
        sm->source.source_generation, sm->lease, mv, ma, &receipt);
		if (!ret) {
			sm->source = receipt;
			return 0;
		}
	}
	return ret;
}

/*
 * The pump halves the bus, so the operating point has to carry twice the cell
 * voltage plus the drop across the cable and connector (r_ttl on this board)
 * plus a small margin, exactly as the vendor loop computes it.
 */
static int sm5440_pps_target_mv(int ma, int vbat_uv)
{
	int headroom = DIV_ROUND_UP(ma * SM5440_R_TTL_MILLIOHM, 1000) +
		       SM5440_EXTRA_HEADROOM_MV;
	int mv = DIV_ROUND_UP((vbat_uv / 1000) * 2 + headroom,
			      SM5440_PPS_V_STEP_MV) * SM5440_PPS_V_STEP_MV;

	return clamp(mv, 8200, SM5440_MAX_PPS_MV);
}

/* Samsung X710 sm5440_charger.c get/set_ibuslim: IBUSCNTL uses 50mA steps.
 * Unlike vendor/Fedora's positive margin, clamp below the bring-up stop cap.
 * A PPS current request is an allowance, not measured input current.
 */
static int sm5440_set_ibus_limit(struct sm5440_direct *sm, int ma)
{
	if (ma < 1000 || ma > SM5440_MAX_PPS_MA)
		return -ERANGE;
	return i2c_smbus_write_byte_data(sm->client, SM5440_REG_IBUSCNTL,
				       min(ma, SM5440_PROGRAM_IBUS_MA) / 50);
}

/* Use TCPM's existing bounded APDO validation and source-bound lease. */
static int sm5440_negotiate_pps(struct sm5440_direct *sm, int vbat_uv,
                                int *target_ma, int *target_mv)
{
	int ret;

 *target_ma = SM5440_MAX_PPS_MA;
 *target_mv = sm5440_pps_target_mv(*target_ma, vbat_uv);
	ret = sm5440_pps_retry(sm, *target_mv, *target_ma);
	if (!ret)
		dev_info(sm->dev, "PPS contract requested: %d mV/%d mA\n",
           *target_mv, *target_ma);
	return ret;
}

/*
 * Keep the operating point alive.
 *
 * Every power_supply property write is its own Power Negotiation and each one
 * re-applies the source's output voltage, so the refresh sends as few of them as
 * it can: the voltage only when the pack has moved the operating point by a step
 * (the only way it changes), the current every time.  The pump is parked across
 * whichever negotiation happens -- see sm5440_renegotiate_pps().
 */
static int sm5440_refresh_pps(struct sm5440_direct *sm)
{
	struct sm5714_pack_snapshot pack;
	int target_mv, ret;

	ret = sm5440_read_pack(sm, &pack);
	if (ret)
		return ret;
	target_mv = sm5440_pps_target_mv(sm->target_ma, pack.voltage_uv);
	ret = sm5440_pps_retry(sm, target_mv, sm->target_ma);
	if (!ret)
		sm->target_mv = target_mv;
	return ret;
}

static int sm5440_set_freq(struct sm5440_direct *sm, int khz)
{
	return i2c_smbus_write_byte_data(sm->client, SM5440_REG_CNTL7,
					 (khz - 250) / 50);
}

static int sm5440_select_freq(struct sm5440_direct *sm, int ma)
{
	if (ma <= SM5440_SIOP_LEV1_MA)
		return sm5440_set_freq(sm, SM5440_FREQUENCY_SIOP1_KHZ);
	if (ma <= SM5440_SIOP_LEV2_MA)
		return sm5440_set_freq(sm, SM5440_FREQUENCY_SIOP2_KHZ);

	return sm5440_set_freq(sm, SM5440_FREQUENCY_KHZ);
}

static int sm5440_pump_off(struct sm5440_direct *sm)
{
	int mode, ret;

	ret = sm5440_update_bits(sm, SM5440_REG_CNTL5,
                         SM5440_CNTL5_OP_MODE_MASK, 0);
	if (ret)
		return ret;
	mode = i2c_smbus_read_byte_data(sm->client, SM5440_REG_CNTL5);
	if (mode < 0)
		return mode;
	return mode & SM5440_CNTL5_OP_MODE_MASK ? -EBUSY : 0;
}

static int sm5440_pump_on(struct sm5440_direct *sm)
{
	struct sm5714_pack_snapshot pack;
	int status3 = 0;
	int i;
	int ret;

	if (!sm5440_direct_enabled(sm))
		return -ESHUTDOWN;
	/* Refresh may have waited in TCPM with the pump parked. Never re-enable
	 * after the one-shot observation deadline, even if negotiation succeeded.
	 */
	if (READ_ONCE(direct_charge_once) && sm->direct_deadline_ms &&
	    ktime_to_ms(ktime_get_boottime()) >= sm->direct_deadline_ms)
		return -ETIME;
	ret = sm5440_read_pack(sm, &pack);
	if (ret)
		return ret;
	ret = sm5440_update_bits(sm, SM5440_REG_CNTL5,
				 SM5440_CNTL5_OP_MODE_MASK,
				 SM5440_CNTL5_CHG_ON);
	if (ret)
		return ret;

	/*
	 * VBUSPOK is set as soon as the pump starts pulling the bus down, which is
	 * well before the 100 ms this used to sleep unconditionally.  Poll for it
	 * instead, keeping the old worst case as the loop bound.
	 */
	for (i = 0; i < 5; i++) {
		msleep(20);
		status3 = i2c_smbus_read_byte_data(sm->client,
						   SM5440_REG_STATUS3);
		if (status3 < 0)
			return status3;
		if (status3 & SM5440_STATUS3_VBUSPOK)
			return 0;
	}

	return -ENOLINK;
}

/*
 * A PPS power_supply write completes before the adapter has necessarily
 * reached the requested voltage, and the chip's reverse-blocking comparator
 * latches REVBLK if the pump is switching across that step.  Let the SM5440's
 * own ADC prove the physical bus is ready before touching CHG_ON.
 */
static int sm5440_wait_vbus_settled(struct sm5440_direct *sm, int target_mv)
{
	int vbus_mv = 0;
	int i;

	/*
	 * The pump is parked while this runs, so every millisecond here is charge
	 * current the pack does not get.  The chip's bus ADC is already averaging
	 * (see ADCCNTL1 in hw_init) and the source has normally re-applied its
	 * output by now, so give it one conversion and then look, rather than
	 * sleeping a fixed 100 ms per attempt and waiting up to three seconds.
	 */
	for (i = 0; i < 30; i++) {
		msleep(i ? 50 : 20);
		vbus_mv = sm5440_adc_vbus_mv(sm);
		if (vbus_mv < 0)
			return vbus_mv;
		if (READ_ONCE(sm->suspending) || READ_ONCE(sm->stopping))
			return -ESHUTDOWN;
		if (vbus_mv > SM5440_MAX_PPS_MV + 300)
			return -ERANGE;
		if (vbus_mv >= target_mv - 500 && vbus_mv <= target_mv + 500)
			return 0;
	}

	dev_warn(sm->dev, "PPS bus did not settle: target=%dmV measured=%dmV\n",
		 target_mv, vbus_mv);
	return -ETIMEDOUT;
}

/*
 * Keep the programmable contract alive without killing the pump.
 *
 * A PPS source re-applies its output voltage on every Request, and that step is
 * enough to drive the 2:1 pump's output above its input for an instant.  The
 * chip then latches REVBLK and clears CHG_ON by itself, so the keep-alive used
 * to end direct charging every couple of seconds and hand the battery back to
 * the 9 V switching charger until the retry.  Park the pump across the
 * re-negotiation and re-arm it once the bus has settled again -- the same rule
 * sm5440_start() applies to the first contract.
 */
static int sm5440_renegotiate_pps(struct sm5440_direct *sm)
{
	int ret;

	ret = sm5440_pump_off(sm);
	if (ret)
		return ret;
	if (READ_ONCE(direct_charge_once))
		dev_info(sm->dev, "one-shot refresh parked: pump_OFF=1\n");

	ret = sm5440_refresh_pps(sm);
	if (ret)
		return ret;

	ret = sm5440_wait_vbus_settled(sm, sm->target_mv);
	if (ret)
		return ret;
	if (READ_ONCE(direct_charge_once)) {
		ret = sm5440_once_settings(sm);
		if (!ret)
			ret = sm5440_once_measure(sm, false);
		if (ret)
			return ret;
	}

	ret = sm5440_pump_on(sm);
	if (!ret && READ_ONCE(direct_charge_once))
		dev_info(sm->dev, "one-shot refresh resumed: target=%dmV/%dmA deadline=%llums\n",
			sm->target_mv, sm->target_ma, sm->direct_deadline_ms);
	return ret;
}

/* Preserve every latch before refresh can re-arm a hardware-stopped pump. */
static int sm5440_monitor_faults(struct sm5440_direct *sm)
{
	u8 events[4], status[4];
	unsigned int faults;
	int i, value, mode;

	for (i = 0; i < 4; i++) {
		value = i2c_smbus_read_byte_data(sm->client, SM5440_REG_INT1 + i);
		if (value < 0)
			return value;
		events[i] = value;
		value = i2c_smbus_read_byte_data(sm->client, SM5440_REG_STATUS1 + i);
		if (value < 0)
			return value;
		status[i] = value;
	}
	mode = i2c_smbus_read_byte_data(sm->client, SM5440_REG_CNTL5);
	if (mode < 0)
		return mode;
	faults = sm5440_decode_faults(events, false, 0) |
          sm5440_decode_faults(status, true,
                 (mode & SM5440_CNTL5_OP_MODE_MASK) >> 2);
	if (events[2] & SM5440_INT3_VBUSUVLO)
		faults |= SM5440_FAULT_VBUS_UVLO;
	if (faults) {
		dev_warn(sm->dev, "retained fault=%#x INT=%02x/%02x/%02x/%02x STATUS=%02x/%02x/%02x/%02x\n",
           faults, events[0], events[1], events[2], events[3],
           status[0], status[1], status[2], status[3]);
		return -EIO;
	}
	return 0;
}

static void sm5440_log_faults(struct sm5440_direct *sm)
{
	static const struct {
		u8 bit;
		bool int3;
		const char *name;
	} faults[] = {
		{ SM5440_INT1_VOUTOVP, false, "VOUT_OVP" },
		{ SM5440_INT1_VBATOVP, false, "VBAT_OVP" },
		{ SM5440_INT3_VBUSOVP, true, "VBUS_OVP" },
		{ SM5440_INT3_VBUSUVLO, true, "VBUS_UVLO" },
		{ SM5440_INT3_THEMSHDN, true, "THERMAL_SHUTDOWN" },
		{ SM5440_INT3_STUP_FAIL, true, "STARTUP_FAIL" },
		{ SM5440_INT3_REVBLK, true, "REVERSE_BLOCKING" },
		{ SM5440_INT3_CFLY_SHORT, true, "FLYING_CAP_SHORT" },
		{ }
	};
	int int1, int3;
	int i;

	/* Read-to-clear: harvest these before the next start wipes them. */
	int1 = i2c_smbus_read_byte_data(sm->client, SM5440_REG_INT1);
	int3 = i2c_smbus_read_byte_data(sm->client, SM5440_REG_INT3);

	dev_warn(sm->dev, "pump off: INT1=%#x INT3=%#x\n", int1, int3);
	for (i = 0; faults[i].name; i++) {
		int reg = faults[i].int3 ? int3 : int1;

		if (reg > 0 && (reg & faults[i].bit))
			dev_warn(sm->dev, "  latched fault: %s\n",
				 faults[i].name);
	}
}

static int sm5440_restore_switching(struct sm5440_direct *sm)
{
	struct sm5714_pd_snapshot fixed;
	struct sm5714_fixed_proof proof = {};
	int i, ret, err, vbus = 0, ibus = 0;
	int vbus_min = 0, vbus_max = 0;
	unsigned int stable_samples = 0;
	u64 stable_started_ms = 0, now;

 /* A failed OFF proof must never release the switching path. */
	ret = sm5440_pump_off(sm);
	sm->active = false;
	sm->pps_ticks = 0;
	if (ret)
		goto failed;
	if (sm->lease) {
		ret = sm5714_pd_restore_fixed(sm->source.instance,
        sm->source.source_generation, sm->lease, &fixed);
		if (ret)
			goto failed;
  /* Fedora continuous ADC, bounded physical settle; no fake READY. */
		ret = sm5440_update_bits(sm, SM5440_REG_ADCCNTL1,
        SM5440_ADCCNTL1_AVG_32 | SM5440_ADCCNTL1_CONTINUOUS |
        SM5440_ADCCNTL1_ENABLE,
        SM5440_ADCCNTL1_AVG_32 | SM5440_ADCCNTL1_CONTINUOUS |
        SM5440_ADCCNTL1_ENABLE);
		if (ret)
			goto failed;
		sm->adc_running = true;
		ret = -ETIMEDOUT;
		for (i = 0; i < 30; i++) {
			msleep(i ? 50 : 20);
			vbus = sm5440_adc_vbus_mv(sm);
			ibus = sm5440_read_adc_pair(sm, SM5440_REG_ADC_IBUS1);
			if (vbus < 0 || ibus < 0) {
				ret = vbus < 0 ? vbus : ibus;
				break;
			}
			if (!sm5714_fixed_vbus_valid(fixed.budget_mv, vbus * 1000U) || ibus) {
				stable_samples = 0;
				continue;
			}
			now = ktime_to_ms(ktime_get_boottime());
			/* Separate nominal voltage tolerance from settling. Require
			 * three zero-current observations over >=100ms whose entire
			 * range stays within 100mV. This is a bring-up stability gate,
			 * not an assertion of independent ADC conversions.
			 */
			if (!stable_samples) {
				vbus_min = vbus_max = vbus;
				stable_started_ms = now;
			} else {
				if (vbus < vbus_min)
					vbus_min = vbus;
				if (vbus > vbus_max)
					vbus_max = vbus;
				if (vbus_max - vbus_min > 100) {
					vbus_min = vbus_max = vbus;
					stable_started_ms = now;
					stable_samples = 0;
				}
			}
			if (++stable_samples >= 3 && now - stable_started_ms >= 100) {
				proof.observed_ms = now;
				proof.vbus_uv = vbus * 1000U;
				proof.ibus_ua = 0;
				proof.pump_off = true;
				ret = sm5440_pump_off(sm);
				break;
			}
		}
		if (ret)
			goto failed;
	}
	ret = sm5440_update_bits(sm, SM5440_REG_ADCCNTL1,
                         SM5440_ADCCNTL1_ENABLE, 0);
	err = sm5440_update_bits(sm, SM5440_REG_CNTL1, SM5440_CNTL1_WDT_EN, 0);
	if (!ret)
		ret = err;
	if (ret)
		goto failed;
	sm->adc_running = false;
	if (sm->lease) {
		ret = sm5714_pd_release_fixed(sm->source.instance,
        sm->source.source_generation, sm->lease, &proof);
		if (ret)
			goto failed;
		dev_info(sm->dev,
			 "fixed return verified: source=%llu lease=%llu vbus=%uuV samples=%u range=%d..%dmV settled=%llums raw_ibus=0 pump_off=1\n",
			 sm->source.source_generation, sm->lease, proof.vbus_uv,
			 stable_samples, vbus_min, vbus_max,
			 proof.observed_ms - stable_started_ms);
		sm->lease = 0;
	}
	sm->last_cleanup_error = 0;
	return 0;
failed:
	sm->fault_latched = true;
	sm->last_cleanup_error = ret;
 /* One last bounded OFF attempt; preserve the original error and lease. */
	err = sm5440_pump_off(sm);
	/* Keep the hardware watchdog armed when pump OFF remains unproven. */
	if (!err)
		sm5440_update_bits(sm, SM5440_REG_CNTL1, SM5440_CNTL1_WDT_EN, 0);
	dev_err(sm->dev, "fixed fallback failed: %d; switching inhibited\n", ret);
	return ret;
}

static void sm5440_put_power_supply(void *data)
{
	power_supply_put(data);
}

static int sm5440_hw_init(struct sm5440_direct *sm)
{
	int reg;
	int ret;
	int i;

	ret = i2c_smbus_write_byte_data(sm->client, SM5440_REG_CNTL1,
					 SM5440_CNTL1_SW_RESET);
	if (ret)
		return ret;
	for (i = 0; i < 255; i++) {
		usleep_range(1000, 2000);
		reg = i2c_smbus_read_byte_data(sm->client, SM5440_REG_CNTL1);
		if (reg < 0)
			return reg;
		if (!(reg & SM5440_CNTL1_SW_RESET))
			break;
	}
	if (i == 255)
		return -ETIMEDOUT;

#define SM5440_WRITE(_reg, _val) do {					\
	ret = i2c_smbus_write_byte_data(sm->client, (_reg), (_val));	\
	if (ret)							\
		return ret;						\
} while (0)

	SM5440_WRITE(SM5440_REG_CNTL1, SM5440_CNTL1_WDT_30S);
	SM5440_WRITE(SM5440_REG_CNTL2, 0xf2);
	SM5440_WRITE(SM5440_REG_CNTL3, 0xb8);
	SM5440_WRITE(SM5440_REG_CNTL4, 0xff);
	SM5440_WRITE(SM5440_REG_CNTL6, 0x09);
	/* CNTL7 (switching frequency) is programmed per charge current in
	 * sm5440_start(), the way the vendor driver does it. */
	SM5440_WRITE(SM5440_REG_VBUSCNTL, 0x07);
	SM5440_WRITE(SM5440_REG_VBATCNTL,
		     ((SM5440_VBATREG_MV - 3800) * 10) / 125);
	SM5440_WRITE(SM5440_REG_VOUTCNTL, 0x3f);
	SM5440_WRITE(SM5440_REG_IBUSCNTL, SM5440_INITIAL_IBUS_MA / 50);
	SM5440_WRITE(SM5440_REG_PRTNCNTL, 0xfe);
	SM5440_WRITE(SM5440_REG_THEMCNTL1, 0x0c);
	SM5440_WRITE(SM5440_REG_ADCCNTL1,
		     SM5440_ADCCNTL1_AVG_32 |
		     SM5440_ADCCNTL1_CONTINUOUS |
		     SM5440_ADCCNTL1_ENABLE);
	SM5440_WRITE(SM5440_REG_ADCCNTL2, 0xdf);
#undef SM5440_WRITE

	/* Reading the four interrupt latches clears stale bootloader events. */
	for (i = 0; i < 4; i++) {
		ret = i2c_smbus_read_byte_data(sm->client, i);
		if (ret < 0)
			return ret;
	}

	sm->adc_running = true;
	return 0;
}

/* Same-model Samsung init_reg_param()/Fedora hw_init(), read back before ON.
 * CNTL2=0xf2 does NOT provide ordinary HW OCP: vendor need_to_sw_ocp=1.
 * Keep the recipe unchanged; the bounded worker checks actual raw current.
 * These checks are programming witnesses, not physical protection validation.
 */
static int sm5440_once_settings(struct sm5440_direct *sm)
{
	static const struct {
		u8 reg, value;
	} settings[] = {
		{ SM5440_REG_CNTL2, 0xf2 },
		{ SM5440_REG_CNTL3, 0xb8 },
		{ SM5440_REG_CNTL4, 0xff },
		{ SM5440_REG_CNTL6, 0x09 },
		{ SM5440_REG_CNTL7, (SM5440_FREQUENCY_KHZ - 250) / 50 },
		{ SM5440_REG_VBUSCNTL, 0x07 },
		{ SM5440_REG_VBATCNTL, ((SM5440_VBATREG_MV - 3800) * 10) / 125 },
		{ SM5440_REG_VOUTCNTL, 0x3f },
		{ SM5440_REG_IBUSCNTL, SM5440_PROGRAM_IBUS_MA / 50 },
		{ SM5440_REG_PRTNCNTL, 0xfe },
		{ SM5440_REG_THEMCNTL1, 0x0c },
		{ SM5440_REG_ADCCNTL1, SM5440_ADCCNTL1_AVG_32 |
		  SM5440_ADCCNTL1_CONTINUOUS | SM5440_ADCCNTL1_ENABLE },
		{ SM5440_REG_ADCCNTL2, 0xdf },
	};
	int i, value;

	for (i = 0; i < ARRAY_SIZE(settings); i++) {
		value = i2c_smbus_read_byte_data(sm->client, settings[i].reg);
		if (value < 0)
			return value;
		if (value != settings[i].value)
			return -EIO;
	}
	return 0;
}

/* First bring-up: retain625uA/500uV ADC precision through the safety check.
 * The200mV pack/ADC coherence tolerance is a BRINGUP_LIMIT, not calibration.
 * No independent pump IBAT ADC exists; use the real signed SM5714 gauge.
 */
static int sm5440_once_measure(struct sm5440_direct *sm, bool running)
{
	struct sm5714_pack_snapshot pack;
	u8 status[4];
	int ret, i, mode, vbus, ibus_raw, vbat_raw, die, value;
	unsigned int ibus_ua, vbat_uv;

	ret = sm5440_read_pack(sm, &pack);
	if (ret)
		return ret;
	if (pack.capacity < 20 || pack.current_ua > 3600000 ||
	    pack.voltage_uv >= 4400000 || pack.pack_decic < 200) {
		dev_err(sm->dev, "one-shot pack range rejected: soc=%d vbat=%duV ibat=%duA temp=%d\n",
			pack.capacity, pack.voltage_uv, pack.current_ua, pack.pack_decic);
		return -ERANGE;
	}
	mode = i2c_smbus_read_byte_data(sm->client, SM5440_REG_CNTL5);
	vbus = sm5440_adc_vbus_mv(sm);
	ibus_raw = sm5440_read_adc_pair(sm, SM5440_REG_ADC_IBUS1);
	vbat_raw = sm5440_read_adc_pair(sm, SM5440_REG_ADC_VBAT1);
	die = sm5440_adc_die_temp(sm);
	if (mode < 0 || vbus < 0 || ibus_raw < 0 || vbat_raw < 0 || die < 0)
		return -EIO;
	ibus_ua = ibus_raw * 625U;
	vbat_uv = 2048000U + vbat_raw * 500U;
	for (i = 0; i < ARRAY_SIZE(status); i++) {
		value = i2c_smbus_read_byte_data(sm->client, SM5440_REG_STATUS1 + i);
		if (value < 0)
			return value;
		status[i] = value;
	}
	if (((mode & SM5440_CNTL5_OP_MODE_MASK) >> 2) != (running ? 1 : 0) ||
	    sm5440_decode_faults(status, running,
		(mode & SM5440_CNTL5_OP_MODE_MASK) >> 2) ||
	    (status[2] & SM5440_INT3_VBUSUVLO) ||
	    vbus < sm->target_mv - 500 || vbus > sm->target_mv + 500 ||
	    vbus > SM5440_MAX_PPS_MV + 300 ||
	    ibus_ua > SM5440_MAX_PPS_MA * 1000U || (!running && ibus_raw) ||
	    vbat_uv < 3500000U || vbat_uv >= 4400000U ||
	    abs((int)vbat_uv - pack.voltage_uv) > 200000 || die >= 850) {
		dev_err(sm->dev, "one-shot range rejected: running=%u mode=0x%x vbus=%dmV target=%dmV ibus=%uuA cap=%uuA vbat=%uuV pack=%duV/%duA temp=%d die=%d status=%02x/%02x/%02x/%02x\n",
			running, mode, vbus, sm->target_mv, ibus_ua,
			SM5440_MAX_PPS_MA * 1000U, vbat_uv, pack.voltage_uv,
			pack.current_ua, pack.pack_decic, die,
			status[0], status[1], status[2], status[3]);
		return -ERANGE;
	}
	if (running && ibus_ua && pack.current_ua > 0)
		sm->direct_positive_samples++;
	dev_dbg(sm->dev, "one-shot sample: on=%u vbus=%dmV ibus=%uuA vbat=%uuV pack=%duV/%duA temp=%d die=%d\n",
		running, vbus, ibus_ua, vbat_uv, pack.voltage_uv,
		pack.current_ua, pack.pack_decic, die);
	return 0;
}

static int sm5440_start(struct sm5440_direct *sm)
{
	struct sm5714_pack_snapshot pack;
	int battery_uv, target_mv, target_ma;
	int ret;

	if (!sm5440_direct_enabled(sm) || sm->lease)
		return -EPERM;
	ret = sm5440_read_pack(sm, &pack);
	if (ret)
		return ret;
	if (pack.pack_decic >= 380 || pack.voltage_uv >= 4300000)
		return -ERANGE;
	battery_uv = pack.voltage_uv;

	/*
	 * Open the SM5714 switching path while VBUS is still at its safe fixed
	 * 9 V contract.  Only then may the direct charger leave that contract
	 * for a programmable one.
	 */
	ret = sm5714_battery_switching_acquire(&sm->lease);
	if (ret) {
		if (sm->lease)
			sm5440_restore_switching(sm);
		return ret;
	}

	ret = sm5440_hw_init(sm);
	if (ret)
		goto restore;

	ret = sm5440_negotiate_pps(sm, battery_uv, &target_ma, &target_mv);
	if (ret)
		goto restore;

	ret = sm5440_select_freq(sm, target_ma);
	if (ret)
		goto restore;

	ret = sm5440_set_ibus_limit(sm, target_ma);
	if (ret)
		goto restore;

	ret = sm5440_wait_vbus_settled(sm, target_mv);
	if (ret)
		goto restore;
	if (READ_ONCE(direct_charge_once)) {
		sm->target_mv = target_mv;
		sm->target_ma = target_ma;
		ret = sm5440_once_settings(sm);
		if (!ret)
			ret = sm5440_once_measure(sm, false);
		if (ret)
			goto restore;
	}

	ret = sm5440_update_bits(sm, SM5440_REG_CNTL1,
				 SM5440_CNTL1_WDT_EN,
				 SM5440_CNTL1_WDT_EN);
	if (ret)
		goto restore;

	ret = sm5440_pump_on(sm);
	if (ret)
		goto restore;
	if (READ_ONCE(direct_charge_once)) {
		/* Includes the bounded VBUSPOK start wait in the30-second budget. */
		sm->direct_deadline_ms = ktime_to_ms(ktime_get_boottime()) +
			SM5440_ONCE_MS - 100;
		ret = sm5440_once_measure(sm, true);
		if (ret)
			goto restore;
	}

	sm->active = true;
	sm->target_mv = target_mv;
	sm->target_ma = target_ma;
	sm->pps_ticks = 0;
	dev_info(sm->dev,
		 "direct charge started: PPS %d mV/%d mA, ibus limit %d mA\n",
		 target_mv, target_ma,
		 min(target_ma, SM5440_PROGRAM_IBUS_MA));
	return 0;

restore:
	sm5440_restore_switching(sm);
	return ret;
}

static bool sm5440_eligible(struct sm5440_direct *sm)
{
	struct sm5714_pd_snapshot source;
	struct sm5714_pack_snapshot pack;
	int ret;

	if (!sm5440_direct_enabled(sm) || sm->lease)
		return false;
	ret = sm5714_pd_read_snapshot(&source);
	if (ret || source.pps_contract || !source.online || !source.charge_requested ||
					source.budget_mv != 9000 || source.budget_ma < 1000 ||
					source.budget_ma > SM5714_FIXED_9V_MA)
		return false;
	ret = sm5714_battery_read_pack(0, &pack);
	if (ret)
		return false;
	sm->source = source;
	sm->pack_instance = pack.instance;
	ret = sm5440_read_pack(sm, &pack);
	return !ret && pack.voltage_uv < 4300000 && pack.pack_decic < 380;
}

/* Single worker owner, drained by the existing PM/remove callbacks. Waiting
 * on a PC fixed5V source is read-only and bounded. This mode can only exercise
 * the existing fixed return proof: no PPS Request, reset/init or pump enable.
 */
static int sm5440_fixed_check_ready(struct sm5440_direct *sm)
{
	struct sm5714_pd_snapshot source;
	struct sm5714_pack_snapshot pack;
	int ret;

	if (READ_ONCE(direct_charge) || READ_ONCE(sm->suspending) ||
	    READ_ONCE(sm->stopping) || sm->fault_latched || sm->lease)
		return -EPERM;
	ret = sm5714_pd_read_snapshot(&source);
	/* The public fixed-source observer reports ENODATA while detached.
	 * This readiness gate runs before any lease/PPS/pump entry; absence is
	 * bounded waiting, not a retry after a failed charging transaction.
	 * Pack ENODATA and real bus errors below remain terminal errors.
	 */
	if (ret == -ENODATA)
		return -EAGAIN;
	if (ret)
		return ret;
	if (source.pps_contract || !source.online || !source.charge_requested)
		return -EAGAIN;
	if (source.budget_mv == 5000)
		return -EAGAIN;
	if (source.budget_mv != 9000 || source.budget_ma < 1000 ||
	    source.budget_ma > SM5714_FIXED_9V_MA)
		return -ERANGE;
	ret = sm5714_battery_read_pack(0, &pack);
	if (ret)
		return ret;
	sm->source = source;
	sm->pack_instance = pack.instance;
	ret = sm5440_read_pack(sm, &pack);
	if (!ret && (pack.voltage_uv >= 4300000 || pack.pack_decic >= 380))
		ret = -ERANGE;
	return ret;
}

static int sm5440_fixed_return_once(struct sm5440_direct *sm)
{
	struct sm5714_pack_snapshot pack;
	int ret, cleanup, adc_channels;

	ret = sm5440_pump_off(sm);
	if (ret)
		return ret;
	/* Fedora's existing channel setup is 0xdf. Do not silently sample
	 * disabled channels or change this configuration for the experiment.
	 */
	adc_channels = i2c_smbus_read_byte_data(sm->client, SM5440_REG_ADCCNTL2);
	if (adc_channels < 0)
		return adc_channels;
	if (adc_channels != 0xdf)
		return -ENODATA;
	if (READ_ONCE(sm->suspending) || READ_ONCE(sm->stopping))
		return -ESHUTDOWN;
	ret = sm5714_battery_switching_acquire(&sm->lease);
	if (!ret)
		ret = sm5440_read_pack(sm, &pack);
	/* Even a partial acquire failure must attempt the existing safe return;
	 * preserve its original error. The worker never retries this experiment.
	 */
	cleanup = sm->lease ? sm5440_restore_switching(sm) : 0;
	return ret ? ret : cleanup;
}

/* The diagnostic never reaches hw_init/start/pump_on. Reuse the verified
 * Fedora ADC setup and the native TCPM lease. No pump current, protections,
 * reset, frequency or channel mask is programmed by this transaction.
 */
static int sm5440_pps_check_pack(struct sm5440_direct *sm)
{
	struct sm5714_pack_snapshot pack;
	int ret = sm5440_read_pack(sm, &pack);

	if (!ret && (pack.capacity < 20 || pack.voltage_uv >= 4300000 ||
		     pack.pack_decic < 200 || pack.pack_decic >= 380))
		ret = -ERANGE;
	return ret;
}

static int sm5440_pps_return_once(struct sm5440_direct *sm)
{
	struct sm5714_pack_snapshot pack;
	struct sm5714_pd_snapshot receipt, after;
	u64 started = 0, now;
	int ret, cleanup, channels, i;
	int vbus = -1, ibus = -1, mode = -1;
	int low = 0, high = 0, samples = 0;
	const char *step = "OFF/channels";

	ret = sm5440_pump_off(sm);
	if (ret)
		goto restore;
	channels = i2c_smbus_read_byte_data(sm->client, SM5440_REG_ADCCNTL2);
	if (channels != 0xdf) {
		ret = channels < 0 ? channels : -ENODATA;
		goto restore;
	}
	step = "lease/pack";
	ret = sm5714_battery_switching_acquire(&sm->lease);
	if (ret)
		goto restore;
	ret = sm5440_pps_check_pack(sm);
	if (ret)
		goto restore;
	ret = sm5440_read_pack(sm, &pack);
	if (ret)
		goto restore;
	sm->target_mv = sm5440_pps_target_mv(SM5440_MAX_PPS_MA,
					   pack.voltage_uv);
	sm->target_ma = SM5440_MAX_PPS_MA;
	step = "ADC";
	/* Existing same-model continuous/32-average sequence, channels unchanged. */
	ret = sm5440_update_bits(sm, SM5440_REG_ADCCNTL1,
		SM5440_ADCCNTL1_AVG_32 | SM5440_ADCCNTL1_CONTINUOUS |
		SM5440_ADCCNTL1_ENABLE,
		SM5440_ADCCNTL1_AVG_32 | SM5440_ADCCNTL1_CONTINUOUS |
		SM5440_ADCCNTL1_ENABLE);
	if (ret)
		goto restore;
	sm->adc_running = true;
	step = "PPS request";
	if (READ_ONCE(sm->suspending) || READ_ONCE(sm->stopping)) {
		ret = -ESHUTDOWN;
		goto restore;
	}
	/* Exactly one owned API call. No diagnostic retry/PPS keepalive/pump ON. */
	ret = sm5714_pd_request_pps(sm->source.instance,
		sm->source.source_generation, sm->lease,
		sm->target_mv, sm->target_ma, &receipt);
	if (ret)
		goto restore;
	sm->source = receipt;
	dev_info(sm->dev,
		 "PPS OFF negotiated: source=%llu lease=%llu target=%dmV/%dmA pump_ON=0\n",
		 sm->source.source_generation, sm->lease,
		 sm->target_mv, sm->target_ma);
	step = "PPS physical sample";
	for (i = 0; i < 30; i++) {
		msleep(i ? 50 : 20);
		if (READ_ONCE(sm->suspending) || READ_ONCE(sm->stopping)) {
			ret = -ESHUTDOWN;
			goto restore;
		}
		ret = sm5440_pps_check_pack(sm);
		if (ret)
			goto restore;
		ret = sm5440_read_source(sm, &receipt);
		if (ret)
			goto restore;
		if (!receipt.pps_contract || receipt.online != 2 ||
		    receipt.budget_mv != sm->target_mv ||
		    receipt.budget_ma != sm->target_ma) {
			ret = -ESTALE;
			goto restore;
		}
		mode = i2c_smbus_read_byte_data(sm->client, SM5440_REG_CNTL5);
		vbus = sm5440_adc_vbus_mv(sm);
		ibus = sm5440_read_adc_pair(sm, SM5440_REG_ADC_IBUS1);
		if (mode < 0 || vbus < 0 || ibus < 0) {
			ret = mode < 0 ? mode : (vbus < 0 ? vbus : ibus);
			goto restore;
		}
		ret = sm5440_read_source(sm, &after);
		if (ret)
			goto restore;
		if (receipt.budget_generation != after.budget_generation) {
			ret = -ESTALE;
			goto restore;
		}
		if ((mode & SM5440_CNTL5_OP_MODE_MASK) || ibus ||
		    vbus > SM5440_MAX_PPS_MV + 300) {
			ret = -ERANGE;
			goto restore;
		}
		/* Retain Fedora's existing PPS ±500mV envelope. This is not an
		 * independent ADC calibration; require stability separately.
		 */
		if (vbus < sm->target_mv - 500 || vbus > sm->target_mv + 500) {
			samples = 0;
			continue;
		}
		now = ktime_to_ms(ktime_get_boottime());
		if (!samples) {
			low = high = vbus;
			started = now;
			samples = 0;
		} else {
			low = min(low, vbus);
			high = max(high, vbus);
			if (high - low > 100) {
				low = high = vbus;
				started = now;
				samples = 0;
			}
		}
		if (++samples >= 3 && now - started >= 100) {
			dev_info(sm->dev,
				 "PPS OFF sampled: target=%dmV/%dmA observed=%dmV range=%d..%dmV samples=%d settled=%llums raw_ibus=0 pump_ON=0\n",
				 sm->target_mv, sm->target_ma, vbus, low, high,
				 samples, now - started);
			ret = 0;
			goto restore;
		}
	}
	ret = -ETIMEDOUT;
restore:
	/* Restore even on partial acquisition/request/sampling failure. Preserve
	 * the primary error independently of terminal physical-return failure.
	 */
	cleanup = sm->lease ? sm5440_restore_switching(sm) : 0;
	if (ret || cleanup)
		dev_err(sm->dev,
			"PPS OFF return failed: step=%s primary=%d cleanup=%d lease=%llu target=%dmV/%dmA observed=%dmV raw_ibus=%d mode=%d\n",
			step, ret, cleanup, sm->lease, sm->target_mv,
			sm->target_ma, vbus, ibus, mode);
	else
		dev_info(sm->dev,
			"PPS OFF return complete: target=%dmV/%dmA lease=0 fixed_return=1 pump_ON=0\n",
			sm->target_mv, sm->target_ma);
	return ret ? ret : cleanup;
}

/*
 * A pump that cannot hold is worse than no pump: it hands the pack back to the
 * switching charger and re-negotiates PPS over and over.  Back off exponentially
 * and then stay quiet for a while instead of cycling.
 */
static unsigned long sm5440_backoff(struct sm5440_direct *sm)
{
	if (sm->fails < SM5440_MAX_FAILS)
		sm->fails++;

	if (sm->fails >= SM5440_MAX_FAILS) {
		dev_warn(sm->dev,
			 "direct charging is not holding; retrying in %d s\n",
			 SM5440_QUIET_RETRY_MS / 1000);
		return msecs_to_jiffies(SM5440_QUIET_RETRY_MS);
	}

	return msecs_to_jiffies(min(SM5440_RETRY_MS << sm->fails,
				    SM5440_MAX_RETRY_MS));
}

/* One worker owns entry, monitoring, refresh and terminal cleanup. No retry
 * or automatic resume/re-attach grant in this test mode.100ms is a scheduling
 * target, not a hard-realtime cutoff guarantee; excessive delivery gap stops.
 * TCPM waits occur only with the pump OFF, never under a charger mutex.
 */
static void sm5440_direct_once_work(struct sm5440_direct *sm)
{
	u64 now = ktime_to_ms(ktime_get_boottime());
	int ret = 0, cleanup;

	if (sm->direct_once_done)
		return;
	if (READ_ONCE(sm->suspending) || READ_ONCE(sm->stopping) || sm->fault_latched) {
		ret = -ESHUTDOWN;
		goto finish;
	}
	if (!sm->active) {
		ret = now >= sm->fixed_check_deadline ? -ETIMEDOUT :
			sm5440_fixed_check_ready(sm);
		if (ret == -EAGAIN || ret == -ENODEV)
			goto schedule;
		if (!ret)
			ret = sm5440_pps_check_pack(sm);
		if (!ret) {
			/* Ordered witness before any switching lease or PPS operation. */
			dev_info(sm->dev, "one-shot entry begins: fixed9=1\n");
			ret = sm5440_start(sm);
		}
		if (ret)
			goto finish;
		now = ktime_to_ms(ktime_get_boottime());
		sm->direct_sample_ms = now;
		sm->direct_refresh_ms = now + SM5440_ONCE_REFRESH_MS;
		dev_info(sm->dev, "one-shot pump started: target=%dmV/%dmA deadline=%llums max_ms=%u no_restart=1\n",
			sm->target_mv, sm->target_ma, sm->direct_deadline_ms,
			SM5440_ONCE_MS);
		goto schedule;
	}
	if (now <= sm->direct_sample_ms ||
	    now - sm->direct_sample_ms > SM5440_ONCE_GAP_MS) {
		ret = -ETIME;
		goto finish;
	}
	/* Harvest read-to-clear latches AND measure before any refresh. A late
	 * refresh must never re-arm a pump that hardware already stopped.
	 */
	ret = sm5440_monitor_faults(sm);
	if (!ret)
		ret = sm5440_once_measure(sm, true);
	if (ret)
		goto finish;
	if (now >= sm->direct_deadline_ms) {
		ret = sm->direct_positive_samples ? 0 : -ENODATA;
		goto finish;
	}
	if (now >= sm->direct_refresh_ms) {
		ret = sm5440_renegotiate_pps(sm);
		if (ret)
			goto finish;
		now = ktime_to_ms(ktime_get_boottime());
		sm->direct_refresh_ms = now + SM5440_ONCE_REFRESH_MS;
		ret = sm5440_once_measure(sm, true);
		if (ret)
			goto finish;
	}
	ret = sm5440_update_bits(sm, SM5440_REG_CNTL1,
		SM5440_CNTL1_WDT_EN, SM5440_CNTL1_WDT_EN);
	if (ret)
		goto finish;
	sm->direct_sample_ms = ktime_to_ms(ktime_get_boottime());
schedule:
	if (!READ_ONCE(sm->suspending) && !READ_ONCE(sm->stopping))
		schedule_delayed_work(&sm->work,
			msecs_to_jiffies(sm->active ? SM5440_ONCE_POLL_MS : SM5440_POLL_MS));
	return;
finish:
	sm->direct_once_done = true;
	/* start() already attempted cleanup on failure. Preserve that refusal;
	 * do not retry a failed fixed return just to obtain a clean terminal log.
	 */
	cleanup = sm->last_cleanup_error;
	if (!cleanup && (sm->active || sm->lease || sm->adc_running))
		cleanup = sm5440_restore_switching(sm);
	if (ret || cleanup) {
		sm->fault_latched = true;
		dev_err(sm->dev, "one-shot pump stopped: primary=%d cleanup=%d lease=%llu no_restart=1\n",
			ret, cleanup, sm->lease);
	} else {
		dev_info(sm->dev, "one-shot pump complete: lease=0 fixed_return=1 positive_samples=%u no_restart=1\n",
			sm->direct_positive_samples);
	}
}

static void sm5440_work(struct work_struct *work)
{
	struct sm5440_direct *sm =
		container_of(to_delayed_work(work), struct sm5440_direct, work);
	unsigned long delay = msecs_to_jiffies(SM5440_POLL_MS);
	struct sm5714_pack_snapshot pack;
	int capacity, die_temp, ibus, op_mode, pack_temp, status3;
	int vbat, vbus;
	int ret;

	if (READ_ONCE(direct_charge_once)) {
		sm5440_direct_once_work(sm);
		return;
	}

	if (READ_ONCE(pps_return_check)) {
		if (sm->fixed_check_done)
			return;
		if (ktime_to_ms(ktime_get_boottime()) >= sm->fixed_check_deadline)
			ret = -ETIMEDOUT;
		else
			ret = sm5440_fixed_check_ready(sm);
		if (!ret)
			ret = sm5440_pps_check_pack(sm);
		if (ret == -EAGAIN || ret == -ENODEV)
			goto out;
		sm->fixed_check_done = true;
		if (!ret)
			ret = sm5440_pps_return_once(sm);
		if (ret) {
			sm->fault_latched = true;
			dev_err(sm->dev, "PPS OFF check stopped: %d; lease=%llu\n",
				ret, sm->lease);
		}
		return;
	}

	if (READ_ONCE(fixed_return_check)) {
		if (sm->fixed_check_done)
			return;
		if (ktime_to_ms(ktime_get_boottime()) >= sm->fixed_check_deadline)
			ret = -ETIMEDOUT;
		else
			ret = sm5440_fixed_check_ready(sm);
		if (ret == -EAGAIN || ret == -ENODEV)
			goto out;
		sm->fixed_check_done = true;
		if (!ret)
			ret = sm5440_fixed_return_once(sm);
		if (ret) {
			sm->fault_latched = true;
			dev_err(sm->dev, "fixed return check failed: %d; lease=%llu\n",
				ret, sm->lease);
		} else {
			dev_info(sm->dev, "fixed return check complete: lease=0 PPS=0 pump_ON=0\n");
		}
		return;
	}

	if (!sm->active) {
		/*
		 * Opt-in: the SM5714 switching charger owns the pack on the fixed
		 * 9 V contract until fast charging is switched on.
		 */
		if (!sm5440_direct_enabled(sm)) {
			delay = msecs_to_jiffies(SM5440_RETRY_MS);
			goto out;
		}
		if (!sm5440_eligible(sm)) {
			delay = msecs_to_jiffies(SM5440_RETRY_MS);
			goto out;
		}
		ret = sm5440_start(sm);
		if (ret) {
			dev_warn(sm->dev, "direct-charge start failed: %d\n", ret);
			delay = sm5440_backoff(sm);
			goto out;
		}
		/* A successful start alone does not erase repeated first-poll faults. */
		goto out;
	}

	/* The switch can go off while the pump runs: hand the pack back. */
	if (!sm5440_direct_enabled(sm)) {
		sm5440_log_faults(sm);
		sm5440_restore_switching(sm);
		dev_info(sm->dev,
			 "fast charging off: back to the fixed contract\n");
		delay = msecs_to_jiffies(SM5440_RETRY_MS);
		goto out;
	}

	ret = sm5440_read_pack(sm, &pack);
	if (!ret)
		ret = sm5440_monitor_faults(sm);
	if (ret) {
		sm5440_restore_switching(sm);
		delay = sm5440_backoff(sm);
		goto out;
	}

	/*
	 * PPS sources leave the programmable contract unless the sink refreshes
	 * its Request periodically. Samsung's downstream loop does this every
	 * 2.5 seconds; without it the EP-T4510 fell back after about five
	 * seconds and the resulting VBUS step tripped REVBLK.  Four seconds keeps
	 * a margin under that fallback while halving how often the pump has to be
	 * parked for the negotiation -- parked time is charge current the pack
	 * never gets, and the parked window itself is kept as short as the chip's
	 * bus ADC allows (see sm5440_wait_vbus_settled / sm5440_pump_on).
	 */
	if (++sm->pps_ticks >= SM5440_REFRESH_TICKS) {
		sm->pps_ticks = 0;
		ret = sm5440_renegotiate_pps(sm);
		if (ret) {
			sm5440_log_faults(sm);
			dev_warn(sm->dev, "failed to refresh PPS: %d\n", ret);
			sm5440_restore_switching(sm);
			delay = sm5440_backoff(sm);
			goto out;
		}
	}

	ret = sm5440_read_pack(sm, &pack);
	if (ret) {
		sm5440_restore_switching(sm);
		delay = sm5440_backoff(sm);
		goto out;
	}
	capacity = pack.capacity;
	pack_temp = pack.pack_decic;
	op_mode = i2c_smbus_read_byte_data(sm->client, SM5440_REG_CNTL5);
	status3 = i2c_smbus_read_byte_data(sm->client, SM5440_REG_STATUS3);
	vbus = sm5440_adc_vbus_mv(sm);
	ibus = sm5440_adc_ibus_ma(sm);
	vbat = sm5440_adc_vbat_mv(sm);
	die_temp = sm5440_adc_die_temp(sm);

	if (capacity < 0 || pack_temp < 0 || op_mode < 0 || status3 < 0 ||
	    vbus < 0 || ibus < 0 || vbat < 0 || die_temp < 0 ||
	    capacity >= 80 || pack_temp < 150 || pack_temp >= 420 ||
	    !(op_mode & SM5440_CNTL5_CHG_ON) ||
	    !(status3 & SM5440_STATUS3_VBUSPOK) ||
	    vbus < sm->target_mv - 500 || vbus > sm->target_mv + 500 ||
	    vbus > 10800 || vbat < 3500 || vbat >= 4400 ||
	    ibus > SM5440_MAX_PPS_MA || die_temp >= 850) {
		dev_warn(sm->dev,
			 "stopping direct charge: cap=%d temp=%d mode=%#x "
			 "st3=%#x vbus=%d ibus=%d vbat=%d die=%d\n",
			 capacity, pack_temp, op_mode, status3,
			 vbus, ibus, vbat, die_temp);
		sm5440_log_faults(sm);
		sm5440_restore_switching(sm);
		delay = sm5440_backoff(sm);
		goto out;
	}

	/* Rewriting CNTL1 services the hardware watchdog. */
	ret = sm5440_update_bits(sm, SM5440_REG_CNTL1,
				 SM5440_CNTL1_WDT_EN,
				 SM5440_CNTL1_WDT_EN);
	if (ret) {
		sm5440_restore_switching(sm);
		delay = sm5440_backoff(sm);
		goto out;
	}

	/* A complete, healthy poll: forget earlier failures. */
	sm->fails = 0;

	dev_info_ratelimited(sm->dev,
			     "direct: pack=%d.%dC vbus=%dmV ibus=%dmA "
			     "vbat=%dmV die=%d.%dC\n",
			     pack_temp / 10, abs(pack_temp % 10),
			     vbus, ibus, vbat,
			     die_temp / 10, abs(die_temp % 10));
out:
	/* The PM notifier owns rescheduling while the system is suspending. */
	if (!READ_ONCE(sm->suspending) && !READ_ONCE(sm->stopping))
		schedule_delayed_work(&sm->work, delay);
}

static void sm5440_cancel_work(void *data)
{
	struct sm5440_direct *sm = data;

	WRITE_ONCE(sm->stopping, true);
	cancel_delayed_work_sync(&sm->work);
	if (sm->active || sm->lease || sm->adc_running)
		sm5440_restore_switching(sm);
}

static void sm5440_unregister_pm(void *data)
{
	struct sm5440_direct *sm = data;

	unregister_pm_notifier(&sm->pm_nb);
}

/*
 * The i2c adapter this charger sits on is suspended with the system, so the poll
 * must neither run nor be scheduled once the tablet is going down: a poll during
 * suspend trips the i2c core's "Transfer while suspended" warning, and a pump
 * left running would lose its PPS contract anyway because nothing refreshes it
 * while the bus is gone.  Park the pump, hand the pack back to the switching
 * charger, and start polling again after resume.
 */
static int sm5440_pm_notify(struct notifier_block *nb, unsigned long action,
			    void *data)
{
	struct sm5440_direct *sm = container_of(nb, struct sm5440_direct, pm_nb);
	int ret;

	switch (action) {
	case PM_SUSPEND_PREPARE:
	case PM_HIBERNATION_PREPARE:
	case PM_RESTORE_PREPARE:
		WRITE_ONCE(sm->suspending, true);
		cancel_delayed_work_sync(&sm->work);
		if (READ_ONCE(direct_charge_once))
			sm->direct_once_done = true;
		if (sm->active || sm->lease || sm->adc_running) {
			ret = sm5440_restore_switching(sm);
			if (ret)
				return notifier_from_errno(ret);
			dev_info(sm->dev,
				 "system suspending: back to the fixed contract\n");
		}
		break;
	case PM_POST_SUSPEND:
	case PM_POST_HIBERNATION:
	case PM_POST_RESTORE:
		WRITE_ONCE(sm->suspending, false);
		if (!READ_ONCE(sm->stopping))
			schedule_delayed_work(&sm->work,
					      msecs_to_jiffies(SM5440_POLL_MS));
		break;
	}

	return NOTIFY_DONE;
}

static int sm5440_probe(struct i2c_client *client)
{
	struct sm5440_direct *sm;
	int id;
	int ret;

	if (!sm5440_modes_valid())
		return -EINVAL;
	if (!i2c_check_functionality(client->adapter,
				     I2C_FUNC_SMBUS_BYTE_DATA))
		return -EOPNOTSUPP;

	sm = devm_kzalloc(&client->dev, sizeof(*sm), GFP_KERNEL);
	if (!sm)
		return -ENOMEM;
	sm->dev = &client->dev;
	sm->client = client;
	sm->fixed_check_deadline = ktime_to_ms(ktime_get_boottime()) +
				   SM5440_FIXED_CHECK_WAIT_MS;
	i2c_set_clientdata(client, sm);

	id = i2c_smbus_read_byte_data(client, SM5440_REG_DEVICEID);
	if (id < 0)
		return dev_err_probe(sm->dev, id, "cannot read device ID\n");
	if ((id & 0x0f) != 1)
		return dev_err_probe(sm->dev, -ENODEV,
				     "unexpected device ID %#x\n", id);

	/* Passive probe: no reset, ADC initialization, handoff or PPS request. */
	ret = sm5440_pump_off(sm);
	if (ret)
		return dev_err_probe(sm->dev, ret, "cannot verify pump OFF\n");

	sm->battery = power_supply_get_by_name("sm5714-battery");
	if (!sm->battery)
		return dev_err_probe(sm->dev, -EPROBE_DEFER,
				     "battery power supply is not ready\n");
	ret = devm_add_action_or_reset(sm->dev, sm5440_put_power_supply,
				       sm->battery);
	if (ret)
		return ret;

	INIT_DELAYED_WORK(&sm->work, sm5440_work);
	ret = devm_add_action_or_reset(sm->dev, sm5440_cancel_work, sm);
	if (ret)
		return ret;

	sm->pm_nb.notifier_call = sm5440_pm_notify;
	ret = register_pm_notifier(&sm->pm_nb);
	if (ret)
		return dev_err_probe(sm->dev, ret,
				     "cannot register the PM notifier\n");
	ret = devm_add_action_or_reset(sm->dev, sm5440_unregister_pm, sm);
	if (ret)
		return ret;

	schedule_delayed_work(&sm->work, msecs_to_jiffies(10000));

	dev_info(sm->dev,
		 "SM5440 direct charger device ID %#x, fast charging %s (cap %u mA)\n",
		 id, sm5440_direct_enabled(sm) ? "on" : "off",
		 SM5440_MAX_PPS_MA);
	return 0;
}

static void sm5440_shutdown(struct i2c_client *client)
{
	sm5440_cancel_work(i2c_get_clientdata(client));
}

static const struct of_device_id sm5440_of_match[] = {
	{ .compatible = "siliconmitus,sm5440" },
	{ }
};
MODULE_DEVICE_TABLE(of, sm5440_of_match);

static struct i2c_driver sm5440_driver = {
	.driver = {
		.name = "sm5440-fedora",
		.of_match_table = sm5440_of_match,
	},
	.probe = sm5440_probe,
	.shutdown = sm5440_shutdown,
};
module_i2c_driver(sm5440_driver);

MODULE_DESCRIPTION("Silicon Mitus SM5440 direct charger for Samsung SM-X710");
MODULE_LICENSE("GPL");
