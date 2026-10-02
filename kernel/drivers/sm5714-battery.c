// SPDX-License-Identifier: GPL-2.0-only
/*
 * Silicon Mitus SM5714 charger + fuel gauge, as wired on the Samsung Galaxy
 * Tab S9 Wi-Fi (SM-X710).
 *
 * SM8550 boards normally report the battery through pmic_glink/qcom_battmgr,
 * but that path needs a "charger_pd" protection domain on the ADSP and this
 * device's firmware ships none (only root_pd, sensor_pd, audio_pd and the CDSP
 * root_pd).  Samsung drives the SM5714 from the AP instead, so do the same.
 *
 * The chip answers on three I2C addresses on the same bus: 0x49 for the
 * charger block (8-bit registers), 0x71 for the fuel gauge (16-bit registers,
 * with the interesting values behind an SRAM read window) and 0x25 for the
 * MUIC.  This driver binds the charger address and creates dummy clients for
 * the fuel gauge and MUIC.
 *
 * Stage 1 supports fuel-gauge telemetry and ordinary BC1.2 switching charge.
 * Stage 2 accepts a bounded fixed-PD budget from the companion TCPM transport.
 * This driver does not control the TCPC or OTG boost. Register
 * layout and gauge conversions follow Samsung's downstream SM5714 drivers;
 * charging limits follow the same-model AP-direct port.  The external pack
 * thermistor is mandatory for enabling Q4.
 */

#include <linux/bitops.h>
#include <linux/delay.h>
#include <linux/i2c.h>
#include <linux/iio/consumer.h>
#include <linux/mod_devicetable.h>
#include <linux/module.h>
#include <linux/mutex.h>
#include <linux/limits.h>
#include <linux/pm.h>
#include <linux/power_supply.h>
#include <linux/workqueue.h>

#include "sm5714-stage2.h"

#define SM5714_MUIC_I2C_ADDR		0x25
#define SM5714_FG_I2C_ADDR		0x71

/* Charger block (8-bit registers, at the address this driver binds). */
#define SM5714_CHG_REG_STATUS1		0x0d
#define  SM5714_CHG_STATUS1_VBUS_POK	BIT(0)
#define  SM5714_CHG_STATUS1_VBUS_OVP	BIT(2)
#define SM5714_CHG_REG_STATUS2		0x0e
#define  SM5714_CHG_STATUS2_CHG_ON	BIT(3)
#define  SM5714_CHG_STATUS2_TOPOFF	BIT(5)
#define  SM5714_CHG_STATUS2_WDT_EXPIRED	BIT(7)
#define SM5714_CHG_REG_CNTL1		0x13
#define  SM5714_CHG_CNTL1_ENQ4FET	BIT(3)
#define SM5714_CHG_REG_VBUSCNTL		0x15
#define SM5714_CHG_REG_CHGCNTL2		0x18
#define SM5714_CHG_REG_CHGCNTL4		0x1a
#define  SM5714_CHG_BATREG_MASK		GENMASK(5, 0)
#define SM5714_CHG_REG_DEVICEID		0x50

/* MUIC block (8-bit registers, at SM5714_MUIC_I2C_ADDR). */
#define SM5714_MUIC_REG_DEVICE_ID	0x00
#define SM5714_MUIC_REG_DEVICE_TYPE1	0x07
#define  SM5714_MUIC_TYPE_DCD_OUT_SDP	BIT(0)
#define  SM5714_MUIC_TYPE_SDP		BIT(1)
#define  SM5714_MUIC_TYPE_DCP		BIT(2)
#define  SM5714_MUIC_TYPE_CDP		BIT(3)

/* Fuel gauge block (16-bit registers, at SM5714_FG_I2C_ADDR). */
#define SM5714_FG_REG_DEVICE_ID		0x00
#define SM5714_FG_REG_SRAM_RADDR	0x8c
#define SM5714_FG_REG_SRAM_RDATA	0x8d

/* Fuel gauge SRAM window addresses. */
#define SM5714_FG_SRAM_SOC		0x00
#define SM5714_FG_SRAM_OCV		0x01
#define SM5714_FG_SRAM_VBAT		0x03
#define SM5714_FG_SRAM_CURRENT		0x05
#define SM5714_FG_SRAM_VBAT_AVG		0x08
#define SM5714_FG_SRAM_CURRENT_AVG	0x09

#define SM5714_POLL_INTERVAL_MS		1000
#define SM5714_CAPACITY_POLL_DIVIDER	10

enum sm5714_charge_thermal_state {
	SM5714_THERMAL_NORMAL,
	SM5714_THERMAL_REDUCED,
	SM5714_THERMAL_STOP,
};

struct sm5714_battery {
	struct device *dev;
	struct i2c_client *chg;
	struct i2c_client *fg;
	struct i2c_client *muic;
	struct iio_channel *battery_temp;
	/* Serialises the two-step SRAM read window on the fuel gauge. */
	struct mutex sram_lock;
	/* Serialises charger programming from polling and probe. */
	struct mutex chg_lock;
	struct power_supply *psy_bat;
	struct power_supply *psy_usb;
	struct power_supply_battery_info *info;
	/* Board battery-regulation voltage, 0 when board data is absent. */
	unsigned int float_uv;
	struct delayed_work poll_work;
	int last_status;
	int last_capacity;
	bool last_online;
	int last_usb_type;
	unsigned int poll_count;
	enum sm5714_charge_thermal_state thermal_state;
	/* All policy writes and charge programming serialize on chg_lock. */
	unsigned int typec_mv;
	unsigned int typec_ma;
	bool typec_owned;
	bool typec_claimed;
	bool typec_charge;
	bool typec_fault;
	bool suspended;
	/* Default inactive; only an explicit companion lease inhibits switching. */
	bool switching_inhibited;
	u64 switching_lease;
};

/* Companion callbacks hold this lock through use; unbind clears before free. */
static DEFINE_MUTEX(sm5714_companion_lock);
static struct sm5714_battery *sm5714_companion;
/* Registry lock protects issuer and inhibition inherited across unbind/rebind. */
static u64 sm5714_switching_issuer;
static bool sm5714_switching_blocked;

static int sm5714_get_online_raw(struct sm5714_battery *sm);
static int sm5714_get_status(struct sm5714_battery *sm);
static int sm5714_get_temp(struct sm5714_battery *sm, int *val);

static int sm5714_chg_update_bits(struct sm5714_battery *sm, u8 reg,
				  u8 mask, u8 val)
{
	int old;
	u8 new;

	old = i2c_smbus_read_byte_data(sm->chg, reg);
	if (old < 0)
		return old;

	new = (old & ~mask) | (val & mask);
	if (new == old)
		return 0;

	return i2c_smbus_write_byte_data(sm->chg, reg, new);
}

static int sm5714_disable_charging(struct sm5714_battery *sm)
{
	int ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_CNTL1,
					 SM5714_CHG_CNTL1_ENQ4FET, 0);

	if (ret)
		dev_err_ratelimited(sm->dev, "cannot open Q4 charging path: %d\n", ret);
	return ret;
}

/*
 * Battery-regulation (float) voltage, CHGCNTL4[5:0], in the vendor encoding:
 * 3.70-3.85 V in 50 mV steps, 3.90/4.00 V, then 4.05-4.62 V in 10 mV steps.
 * The chip's OTP default is 4.38 V; the stock board data for this pack asks
 * for 4.44 V (battery,chg_float_voltage = 0x1158), and the vendor charger
 * driver programs that value from its platform data at init.  Leaving the
 * OTP default in place charges the pack ~60 mV short and keeps the fuel
 * gauge from ever reaching its 100 % point.
 */
static u8 sm5714_batreg_offset(unsigned int uv)
{
	unsigned int mv = uv / 1000;

	if (mv <= 3700)
		return 0x00;
	if (mv < 3900)
		return (mv - 3700) / 50;
	if (mv < 4050)
		return ((mv - 3900) / 100) + 4;
	if (mv < 4630)
		return ((mv - 4050) / 10) + 6;

	/* Out of range: keep the chip's 4.2 V default, as the vendor does. */
	return 0x15;
}

static int sm5714_set_float_voltage(struct sm5714_battery *sm)
{
	u8 offset = sm5714_batreg_offset(sm->float_uv);
	int ret;

	ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_CHGCNTL4,
				     SM5714_CHG_BATREG_MASK, offset);
	if (ret)
		return ret;
	ret = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_CHGCNTL4);
	if (ret < 0)
		return ret;
	return (ret & SM5714_CHG_BATREG_MASK) == offset ? 0 : -EIO;
}

/* Keep latched watchdog faults for inspection; do not reset/retry them. */
static int sm5714_charge_fault(struct sm5714_battery *sm)
{
	int st1, st2;

	st1 = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_STATUS1);
	if (st1 < 0)
		return st1;
	st2 = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_STATUS2);
	if (st2 < 0)
		return st2;
	if (st1 & SM5714_CHG_STATUS1_VBUS_OVP)
		return -EOVERFLOW;
	if (st2 & SM5714_CHG_STATUS2_WDT_EXPIRED)
		return -ETIMEDOUT;
	return 0;
}

static int sm5714_get_usb_type(struct sm5714_battery *sm)
{
	int online = sm5714_get_online_raw(sm);
	int type;

	if (online <= 0)
		return online < 0 ? online : POWER_SUPPLY_USB_TYPE_UNKNOWN;
	if (READ_ONCE(sm->typec_mv) == 9000 && READ_ONCE(sm->typec_ma))
		return POWER_SUPPLY_USB_TYPE_PD;

	type = i2c_smbus_read_byte_data(sm->muic,
					SM5714_MUIC_REG_DEVICE_TYPE1);
	if (type < 0)
		return type;

	if (type == SM5714_MUIC_TYPE_CDP)
		return POWER_SUPPLY_USB_TYPE_CDP;
	if (type == SM5714_MUIC_TYPE_SDP ||
	    type == SM5714_MUIC_TYPE_DCD_OUT_SDP ||
	    type == (SM5714_MUIC_TYPE_SDP | SM5714_MUIC_TYPE_DCD_OUT_SDP))
		return POWER_SUPPLY_USB_TYPE_SDP;
	/*
	 * Only plain BC1.2 DCP authorizes the 1.8 A limit in Stage 1.
	 * Proprietary AFC/QC and ambiguous adapters remain at 500 mA until
	 * voltage/current contract telemetry exists in Stage 2.
	 */
	if (type == SM5714_MUIC_TYPE_DCP)
		return POWER_SUPPLY_USB_TYPE_DCP;

	return POWER_SUPPLY_USB_TYPE_UNKNOWN;
}

static u8 sm5714_input_current_reg(unsigned int ma)
{
	return clamp_val((ma - 100) / 25, 0, 0x7f);
}

static u8 sm5714_fast_current_reg(unsigned int ma)
{
	unsigned int ua = ma * 1000;

	if (ua <= 109375)
		return 0x07;

	return clamp_val(7 + (ua - 109375) / 15625, 0x07, 0xe0);
}

static enum sm5714_charge_thermal_state
sm5714_charge_thermal_state(struct sm5714_battery *sm, int temp)
{
	/*
	 * Stock has reduced-current bands at 5/15/18 C and cuts off at 0 C.
	 * Until those bands are modeled, stop below 10 C and allow only
	 * 500 mA between 10 and 18 C; a stopped cold pack resumes at 15 C.
	 */
	if (temp < 100)
		return SM5714_THERMAL_STOP;
	if (sm->thermal_state == SM5714_THERMAL_STOP && temp < 150)
		return SM5714_THERMAL_STOP;
	if (temp < 180)
		return SM5714_THERMAL_REDUCED;
	/*
	 * The stock X710 battery data uses 50.0 C as the wired
	 * warm/overheat boundary. Reduce from its wired warm/normal threshold
	 * of 42.0 C. A hot hard stop recovers to reduced current below 46.0 C;
	 * full current returns only below 42.0 C.
	 */
	if (sm->thermal_state == SM5714_THERMAL_STOP) {
		if (temp >= 460)
			return SM5714_THERMAL_STOP;
		if (temp > 420)
			return SM5714_THERMAL_REDUCED;
	}
	if (sm->thermal_state == SM5714_THERMAL_REDUCED && temp > 420) {
		if (temp >= 500)
			return SM5714_THERMAL_STOP;
		return SM5714_THERMAL_REDUCED;
	}

	if (temp >= 500)
		return SM5714_THERMAL_STOP;
	if (temp >= 420)
		return SM5714_THERMAL_REDUCED;
	return SM5714_THERMAL_NORMAL;
}

/* Invalidation never drops inhibition: another charger's state is unknown. */
static void sm5714_revoke_switching_locked(struct sm5714_battery *sm)
{
	lockdep_assert_held(&sm->chg_lock);
	if (sm->switching_inhibited)
		sm->switching_lease = 0;
}

static int sm5714_configure_charging_locked(struct sm5714_battery *sm)
{
	unsigned int input_ma, fast_ma;
	enum sm5714_charge_thermal_state thermal_state;
	int usb_type;
	int temp;
	int ret;

	lockdep_assert_held(&sm->chg_lock);
	/* Never inherit Android's unknown limits or leave Q4 closed on error. */
	ret = sm5714_disable_charging(sm);
	if (ret)
		goto out_unlock;
	/* Q4 gates the pack, not all VSYS consumption. Lower the input limit too
	 * before any early return on a TCPM transition/fault.100mA is the stock
	 * register's minimum; this does not claim complete VBUS isolation.
	 */
	if (sm->typec_owned) {
		ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
					     GENMASK(6, 0), sm5714_input_current_reg(100));
		if (ret)
			goto out_unlock;
	}
	/* Polling must not override TCPM standby/reset or suspend's charge-off. */
	if (sm->switching_inhibited || sm->suspended || (sm->typec_owned &&
	    (!sm->typec_charge || sm->typec_fault || sm->typec_ma < 100)))
		goto out_unlock;
	ret = sm5714_charge_fault(sm);
	if (ret)
		goto out_unlock;

	ret = sm5714_get_temp(sm, &temp);
	if (ret) {
		sm->thermal_state = SM5714_THERMAL_STOP;
		dev_warn_ratelimited(sm->dev,
				     "pack thermistor unavailable; charging disabled: %d\n",
				     ret);
		goto out_unlock;
	}
	thermal_state = sm5714_charge_thermal_state(sm, temp);
	sm->thermal_state = thermal_state;
	if (thermal_state == SM5714_THERMAL_STOP) {
		dev_warn_ratelimited(sm->dev,
				     "charging suspended at pack temperature %d.%d C\n",
				     temp / 10, abs(temp % 10));
		ret = 0;
		goto out_unlock;
	}

	usb_type = sm5714_get_usb_type(sm);
	if (usb_type < 0) {
		ret = usb_type;
		goto out_unlock;
	}
	ret = sm5714_get_online_raw(sm);
	if (ret <= 0) {
		if (!ret)
			ret = -ENODEV;
		goto out_unlock;
	}

	switch (usb_type) {
	case POWER_SUPPLY_USB_TYPE_PD:
		/* Fixed9V ordinary switching only:13.5W input, existing pack limit. */
		input_ma = 1500;
		fast_ma = 2100;
		break;
	case POWER_SUPPLY_USB_TYPE_DCP:
		input_ma = 1800;
		/* 2100 mA maps to the stock bootloader's CHGCNTL2=0x86. */
		fast_ma = 2100;
		break;
	case POWER_SUPPLY_USB_TYPE_CDP:
		input_ma = 1500;
		fast_ma = 1500;
		break;
	case POWER_SUPPLY_USB_TYPE_SDP:
	default:
		/* Unknown sources must never be treated as high-current ports. */
		input_ma = 500;
		fast_ma = 500;
		break;
	}
	if (sm->typec_owned)
		input_ma = min(input_ma, sm->typec_ma);

	if (thermal_state == SM5714_THERMAL_REDUCED) {
		input_ma = min(input_ma, 500U);
		fast_ma = min(fast_ma, 500U);
	}

	/*
	 * Match chg_set_enq4fet(): lower the input limit before closing Q4,
	 * then restore the limit advertised by the MUIC classification.
	 */
	ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
				     GENMASK(6, 0),
				     sm5714_input_current_reg(min(input_ma, 500U)));
	if (ret)
		goto out_unlock;

	ret = i2c_smbus_write_byte_data(sm->chg, SM5714_CHG_REG_CHGCNTL2,
					sm5714_fast_current_reg(fast_ma));
	if (ret)
		goto out_unlock;

	/*
	 * Re-arm the float voltage as well: the charger block loses its
	 * programming when the cable has been out long enough for the chip to
	 * power-cycle, so probe-time programming alone is not enough.
	 */
	ret = sm5714_set_float_voltage(sm);
	if (ret)
		goto out_unlock;

	/* Preserve a completed charge rather than forcing Q4 on at FULL. */
	ret = sm5714_get_status(sm);
	if (ret < 0)
		goto out_unlock;
	if (ret == POWER_SUPPLY_STATUS_FULL) {
		ret = 0;
		goto out_unlock;
	}

	if (input_ma > 500)
		usleep_range(DIV_ROUND_UP(input_ma - 500, 250) * 1000,
			     DIV_ROUND_UP(input_ma - 500, 250) * 1000 + 1000);

	ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_CNTL1,
				     SM5714_CHG_CNTL1_ENQ4FET,
				     SM5714_CHG_CNTL1_ENQ4FET);
	if (ret)
		goto out_unlock;

	ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
				     GENMASK(6, 0), sm5714_input_current_reg(input_ma));
	if (ret)
		sm5714_disable_charging(sm);
	else
		dev_info(sm->dev, "ordinary charging: USB type %d, %u mA input, %u mA battery\n",
			 usb_type, input_ma, fast_ma);

out_unlock:
	/* A failed write may still have reached the chip; best-effort open Q4. */
	if (ret) {
		if (ret != -ENODEV && sm->typec_owned) {
			sm->typec_fault = true;
			sm5714_revoke_switching_locked(sm);
		}
		sm5714_disable_charging(sm);
	}
	return ret;
}

static int sm5714_configure_charging(struct sm5714_battery *sm)
{
	int ret;

	mutex_lock(&sm->chg_lock);
	ret = sm5714_configure_charging_locked(sm);
	mutex_unlock(&sm->chg_lock);
	return ret;
}

/*
 * Samsung chg_set_enq4fet()/VBUSCNTL encoding, already used by ordinary
 * switching above. Verify both safety settings; 100mA is not VSYS isolation.
 * Preserve the first error but attempt both operations even on an I2C fault.
 */
static int sm5714_verify_switching_off_locked(struct sm5714_battery *sm)
{
	int ret, value, first;

	lockdep_assert_held(&sm->chg_lock);
	first = sm5714_disable_charging(sm);
	value = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_CNTL1);
	ret = value < 0 ? value : (value & SM5714_CHG_CNTL1_ENQ4FET) ? -EIO : 0;
	if (!first)
		first = ret;
	ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
				     GENMASK(6, 0), sm5714_input_current_reg(100));
	if (!first)
		first = ret;
	value = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_VBUSCNTL);
	ret = value < 0 ? value : (value & GENMASK(6, 0)) ? -EIO : 0;
	if (!first)
		first = ret;
	return first;
}

static bool sm5714_fixed_grant_locked(struct sm5714_battery *sm)
{
	lockdep_assert_held(&sm->chg_lock);
	return !sm->suspended && !sm->typec_fault && sm->typec_owned &&
		sm->typec_charge && sm->typec_ma >= 100 &&
		(sm->typec_mv == 5000 || sm->typec_mv == 9000);
}

int sm5714_battery_switching_acquire(u64 *lease)
{
	struct sm5714_battery *sm;
	int ret = -ENODEV;

	if (!lease)
		return -EINVAL;
	*lease = 0;
	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (!sm)
		goto out;
	mutex_lock(&sm->chg_lock);
	if (sm->switching_lease) {
		ret = -EBUSY;
	} else if (!sm5714_fixed_grant_locked(sm)) {
		ret = -EAGAIN;
	} else if (sm5714_switching_issuer == U64_MAX) {
		ret = -EOVERFLOW;
	} else {
		/* Inhibit before touching Q4, without destroying the fixed budget. */
		sm->switching_inhibited = true;
		sm->switching_lease = ++sm5714_switching_issuer;
		*lease = sm->switching_lease;
		ret = sm5714_verify_switching_off_locked(sm);
		if (ret) {
			sm->typec_fault = true;
			sm5714_revoke_switching_locked(sm);
		}
	}
	mutex_unlock(&sm->chg_lock);
	if (*lease) {
		power_supply_changed(sm->psy_usb);
		power_supply_changed(sm->psy_bat);
	}
out:
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_switching_acquire);

/* Read-only ownership check; no I2C or permission to reopen Q4. */
int sm5714_battery_switching_check(u64 lease)
{
	struct sm5714_battery *sm;
	int ret = -ENODEV;

	if (!lease)
		return -EINVAL;
	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (sm) {
		mutex_lock(&sm->chg_lock);
		if (!sm->switching_inhibited || sm->switching_lease != lease)
			ret = -ESTALE;
		else if (sm->suspended || sm->typec_fault || !sm->typec_owned ||
			 !sm->typec_charge)
			ret = -EAGAIN;
		else
			ret = 0;
		mutex_unlock(&sm->chg_lock);
	}
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_switching_check);

int sm5714_battery_switching_release(u64 lease)
{
	struct sm5714_battery *sm;
	int ret = -ENODEV;

	if (!lease)
		return -EINVAL;
	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (!sm)
		goto out;
	mutex_lock(&sm->chg_lock);
	if (!sm->switching_inhibited || sm->switching_lease != lease) {
		ret = -ESTALE;
	} else if (!sm5714_fixed_grant_locked(sm)) {
		ret = -EAGAIN;
	} else {
		/* Caller must first prove pump OFF and fresh physical fixed VBUS.
		 * Hold chg_lock through restore: no poller/TCPM interleaving.
		 */
		sm->switching_inhibited = false;
		ret = sm5714_configure_charging_locked(sm);
		if (ret)
			sm->switching_inhibited = true;
		else
			sm5714_switching_blocked = false;
		sm->switching_lease = 0;
	}
	mutex_unlock(&sm->chg_lock);
	power_supply_changed(sm->psy_usb);
	power_supply_changed(sm->psy_bat);
out:
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_switching_release);

/* TCPM budget is not a measured VBUS voltage or proof of PS_RDY on its own. */
static void sm5714_inhibit_typec_locked(struct sm5714_battery *sm)
{
	/* Companion lifetime is held outside chg_lock. Keep the fault latch,
	 * cleared grant, pack gate and minimum input together for every error
	 * entry; no fault path can accidentally leave the old budget live.
	 */
	lockdep_assert_held(&sm->chg_lock);
	sm5714_revoke_switching_locked(sm);
	sm->typec_fault = true;
	sm->typec_charge = false;
	sm->typec_ma = 0;
	sm5714_disable_charging(sm);
	sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
			       GENMASK(6, 0), sm5714_input_current_reg(100));
}

int sm5714_battery_set_pd_contract(unsigned int mv, unsigned int ma)
{
	struct sm5714_battery *sm;
	int ret;

	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (!sm) {
		ret = -ENODEV;
		goto out;
	}
	mutex_lock(&sm->chg_lock);
	if ((mv != 0 && mv != 5000 && mv != 9000) || (!mv && ma)) {
		sm5714_inhibit_typec_locked(sm);
		ret = -ERANGE;
		mutex_unlock(&sm->chg_lock);
		goto out;
	}
	if (mv != sm->typec_mv || ma != sm->typec_ma)
		sm5714_revoke_switching_locked(sm);
	sm->typec_mv = mv;
	/* Store the grant; configure_charging separately caps actual input draw. */
	sm->typec_ma = ma;
	mutex_unlock(&sm->chg_lock);
	ret = sm5714_configure_charging(sm);
	if (ret == -ENODEV) /* detached/charger POK has not risen; Q4 stays open */
		ret = 0;
	power_supply_changed(sm->psy_usb);
	power_supply_changed(sm->psy_bat);
out:
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_set_pd_contract);

int sm5714_battery_set_typec_charge(bool charge)
{
	struct sm5714_battery *sm;
	int ret;

	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (!sm) {
		ret = -ENODEV;
		goto out;
	}
	mutex_lock(&sm->chg_lock);
	sm->typec_charge = charge;
	if (!charge) {
		sm5714_revoke_switching_locked(sm);
		sm->typec_mv = 0;
		sm->typec_ma = 0;
	}
	mutex_unlock(&sm->chg_lock);
	ret = sm5714_configure_charging(sm);
	if (ret == -ENODEV)
		ret = 0;
	power_supply_changed(sm->psy_usb);
	power_supply_changed(sm->psy_bat);
out:
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_set_typec_charge);

void sm5714_battery_typec_fault(void)
{
	struct sm5714_battery *sm;

	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (sm) {
		mutex_lock(&sm->chg_lock);
		sm5714_inhibit_typec_locked(sm);
		mutex_unlock(&sm->chg_lock);
		power_supply_changed(sm->psy_usb);
		power_supply_changed(sm->psy_bat);
	}
	mutex_unlock(&sm5714_companion_lock);
}
EXPORT_SYMBOL_GPL(sm5714_battery_typec_fault);

int sm5714_battery_typec_claim(void)
{
	struct sm5714_battery *sm;
	int ret = -EPROBE_DEFER;

	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (sm) {
		mutex_lock(&sm->chg_lock);
		/* No silent rebind clears a first-fault latch on a live contract. */
		if (sm->typec_claimed) {
			ret = -EBUSY;
		} else {
			sm->typec_owned = true;
			sm->typec_claimed = true;
			sm->typec_charge = false;
			sm->typec_mv = 0;
			sm->typec_ma = 0;
			ret = sm5714_disable_charging(sm);
			if (!ret)
				ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
							     GENMASK(6, 0), sm5714_input_current_reg(100));
		}
		mutex_unlock(&sm->chg_lock);
	}
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_typec_claim);

int sm5714_battery_get_bc12_limit(void)
{
	struct sm5714_battery *sm;
	int type, ret = -ENODEV;

	mutex_lock(&sm5714_companion_lock);
	sm = sm5714_companion;
	if (sm) {
		type = sm5714_get_usb_type(sm);
		ret = type < 0 ? type : type == POWER_SUPPLY_USB_TYPE_DCP ? 1800 :
			type == POWER_SUPPLY_USB_TYPE_CDP ? 1500 : 500;
	}
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}
EXPORT_SYMBOL_GPL(sm5714_battery_get_bc12_limit);

/*
 * The fuel gauge exposes its measurements through an SRAM read window: point
 * RADDR at the word of interest, then read RDATA.
 */
static int sm5714_fg_read_sram(struct sm5714_battery *sm, u8 addr)
{
	int ret;

	mutex_lock(&sm->sram_lock);

	ret = i2c_smbus_write_word_data(sm->fg, SM5714_FG_REG_SRAM_RADDR, addr);
	if (ret < 0)
		goto out;

	ret = i2c_smbus_read_word_data(sm->fg, SM5714_FG_REG_SRAM_RDATA);
out:
	mutex_unlock(&sm->sram_lock);
	if (ret < 0)
		dev_dbg(sm->dev, "SRAM read 0x%02x failed: %d\n", addr, ret);
	return ret;
}

/*
 * Current and temperature are legitimately negative when the battery is
 * discharging or cold, so these helpers report the value through *val and keep
 * the return code purely for I/O errors.  Folding the two together would make a
 * discharging battery look like a failing I2C transfer.
 */

/* State of charge arrives as an unsigned Q8.8 percentage. */
static int sm5714_get_capacity(struct sm5714_battery *sm, int *val)
{
	int raw = sm5714_fg_read_sram(sm, SM5714_FG_SRAM_SOC);

	if (raw < 0)
		return raw;

	*val = clamp(((raw * 10) >> 8) / 10, 0, 100);
	return 0;
}

/* Battery voltage is offset from 2700 mV in units of 10/109 mV. */
static int sm5714_get_voltage(struct sm5714_battery *sm, u8 sram_addr, int *val)
{
	int raw = sm5714_fg_read_sram(sm, sram_addr);
	int mv;

	if (raw < 0)
		return raw;

	if (raw & 0x8000)
		mv = 2700 - (((raw & 0x7fff) * 10) / 109);
	else
		mv = ((raw * 10) / 109) + 2700;

	*val = mv * 1000;
	return 0;
}

static int sm5714_get_ocv(struct sm5714_battery *sm, int *val)
{
	int raw = sm5714_fg_read_sram(sm, SM5714_FG_SRAM_OCV);

	if (raw < 0)
		return raw;

	*val = ((raw * 1000) >> 11) * 1000;
	return 0;
}

/*
 * Current is a sign-magnitude value in units of 1/2044 A.  Bit 15 marks a
 * discharge, which matches the power supply class convention of negative
 * current flowing out of the battery.
 */
static int sm5714_get_current(struct sm5714_battery *sm, u8 sram_addr, int *val)
{
	int raw = sm5714_fg_read_sram(sm, sram_addr);
	int ma;

	if (raw < 0)
		return raw;

	ma = ((raw & 0x7fff) * 1000) / 2044;
	if (raw & 0x8000)
		ma = -ma;

	*val = ma * 1000;
	return 0;
}

static int sm5714_get_temp(struct sm5714_battery *sm, int *val)
{
	int temp_mc;
	int ret;

	/*
	 * The stock X710 policy uses the external pack thermistor.  The SM5714
	 * SRAM value is the fuel-gauge die temperature and rises/falls by several
	 * degrees as Q4 switches, so it is not a valid battery safety signal.
	 */
	ret = iio_read_channel_processed(sm->battery_temp, &temp_mc);
	if (ret)
		return ret;
	if (temp_mc < -20000 || temp_mc > 90000) {
		dev_warn_ratelimited(sm->dev,
				     "pack thermistor returned implausible %d mC\n",
				     temp_mc);
		return -ERANGE;
	}

	*val = DIV_ROUND_CLOSEST(temp_mc, 100);
	return 0;
}

static int sm5714_get_online_raw(struct sm5714_battery *sm)
{
	int ret = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_STATUS1);

	if (ret < 0)
		return ret;

	return !!(ret & SM5714_CHG_STATUS1_VBUS_POK);
}

static int sm5714_get_status(struct sm5714_battery *sm)
{
	int st1, st2;

	st1 = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_STATUS1);
	if (st1 < 0)
		return st1;
	if (!(st1 & SM5714_CHG_STATUS1_VBUS_POK))
		return POWER_SUPPLY_STATUS_DISCHARGING;
	st2 = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_STATUS2);
	if (st2 < 0)
		return st2;

	if (st2 & SM5714_CHG_STATUS2_TOPOFF)
		return POWER_SUPPLY_STATUS_FULL;
	if (st2 & SM5714_CHG_STATUS2_CHG_ON)
		return POWER_SUPPLY_STATUS_CHARGING;
	return POWER_SUPPLY_STATUS_NOT_CHARGING;
}

static int sm5714_bat_get_property(struct power_supply *psy,
				   enum power_supply_property psp,
				   union power_supply_propval *val)
{
	struct sm5714_battery *sm = power_supply_get_drvdata(psy);
	int ret;

	switch (psp) {
	case POWER_SUPPLY_PROP_STATUS:
		ret = sm5714_get_status(sm);
		if (ret < 0)
			return ret;
		val->intval = ret;
		return 0;
	case POWER_SUPPLY_PROP_PRESENT:
		val->intval = 1;
		return 0;
	case POWER_SUPPLY_PROP_TECHNOLOGY:
		val->intval = POWER_SUPPLY_TECHNOLOGY_LION;
		return 0;
	case POWER_SUPPLY_PROP_CAPACITY:
		ret = sm5714_get_capacity(sm, &val->intval);
		break;
	case POWER_SUPPLY_PROP_VOLTAGE_NOW:
		ret = sm5714_get_voltage(sm, SM5714_FG_SRAM_VBAT, &val->intval);
		break;
	case POWER_SUPPLY_PROP_VOLTAGE_AVG:
		ret = sm5714_get_voltage(sm, SM5714_FG_SRAM_VBAT_AVG,
					 &val->intval);
		break;
	case POWER_SUPPLY_PROP_VOLTAGE_OCV:
		ret = sm5714_get_ocv(sm, &val->intval);
		break;
	case POWER_SUPPLY_PROP_CURRENT_NOW:
		ret = sm5714_get_current(sm, SM5714_FG_SRAM_CURRENT,
					 &val->intval);
		break;
	case POWER_SUPPLY_PROP_CURRENT_AVG:
		ret = sm5714_get_current(sm, SM5714_FG_SRAM_CURRENT_AVG,
					 &val->intval);
		break;
	case POWER_SUPPLY_PROP_TEMP:
		ret = sm5714_get_temp(sm, &val->intval);
		break;
	case POWER_SUPPLY_PROP_HEALTH:
		ret = sm5714_charge_fault(sm);
		if (ret) {
			val->intval = ret == -EOVERFLOW ? POWER_SUPPLY_HEALTH_OVERVOLTAGE :
				ret == -ETIMEDOUT ? POWER_SUPPLY_HEALTH_WATCHDOG_TIMER_EXPIRE :
				POWER_SUPPLY_HEALTH_UNKNOWN;
			return 0;
		}
		ret = sm5714_get_temp(sm, &val->intval);
		if (ret)
			val->intval = POWER_SUPPLY_HEALTH_UNKNOWN;
		else if (val->intval < 100)
			val->intval = POWER_SUPPLY_HEALTH_COLD;
		else if (val->intval >= 500)
			val->intval = POWER_SUPPLY_HEALTH_OVERHEAT;
		else
			val->intval = POWER_SUPPLY_HEALTH_GOOD;
		return 0;
	case POWER_SUPPLY_PROP_CHARGE_FULL_DESIGN:
		if (!sm->info ||
		    sm->info->charge_full_design_uah < 0)
			return -ENODATA;
		val->intval = sm->info->charge_full_design_uah;
		return 0;
	case POWER_SUPPLY_PROP_VOLTAGE_MAX_DESIGN:
		if (!sm->info ||
		    sm->info->voltage_max_design_uv < 0)
			return -ENODATA;
		val->intval = sm->info->voltage_max_design_uv;
		return 0;
	case POWER_SUPPLY_PROP_VOLTAGE_MIN_DESIGN:
		if (!sm->info ||
		    sm->info->voltage_min_design_uv < 0)
			return -ENODATA;
		val->intval = sm->info->voltage_min_design_uv;
		return 0;
	default:
		return -EINVAL;
	}

	return ret;
}

static int sm5714_usb_get_property(struct power_supply *psy,
				   enum power_supply_property psp,
				   union power_supply_propval *val)
{
	struct sm5714_battery *sm = power_supply_get_drvdata(psy);
	int ret;

	switch (psp) {
	case POWER_SUPPLY_PROP_ONLINE:
		ret = sm5714_get_online_raw(sm);
		break;
	case POWER_SUPPLY_PROP_USB_TYPE:
		ret = sm5714_get_usb_type(sm);
		if (ret < 0)
			return ret;
		val->intval = ret;
		return 0;
	case POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT:
		ret = i2c_smbus_read_byte_data(sm->chg, SM5714_CHG_REG_VBUSCNTL);
		if (ret < 0)
			return ret;
		/* Configured switching limit, not measured input current or PD grant. */
		val->intval = (100 + (ret & GENMASK(6, 0)) * 25) * 1000;
		return 0;
	default:
		return -EINVAL;
	}

	if (ret < 0)
		return ret;

	val->intval = ret;
	return 0;
}

static enum power_supply_property sm5714_bat_props[] = {
	POWER_SUPPLY_PROP_STATUS,
	POWER_SUPPLY_PROP_PRESENT,
	POWER_SUPPLY_PROP_HEALTH,
	POWER_SUPPLY_PROP_TECHNOLOGY,
	POWER_SUPPLY_PROP_CAPACITY,
	POWER_SUPPLY_PROP_VOLTAGE_NOW,
	POWER_SUPPLY_PROP_VOLTAGE_AVG,
	POWER_SUPPLY_PROP_VOLTAGE_OCV,
	POWER_SUPPLY_PROP_VOLTAGE_MAX_DESIGN,
	POWER_SUPPLY_PROP_VOLTAGE_MIN_DESIGN,
	POWER_SUPPLY_PROP_CURRENT_NOW,
	POWER_SUPPLY_PROP_CURRENT_AVG,
	POWER_SUPPLY_PROP_CHARGE_FULL_DESIGN,
	POWER_SUPPLY_PROP_TEMP,
};

static enum power_supply_property sm5714_usb_props[] = {
	POWER_SUPPLY_PROP_ONLINE,
	POWER_SUPPLY_PROP_USB_TYPE,
	POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT,
};

static const struct power_supply_desc sm5714_bat_desc = {
	.name		= "sm5714-battery",
	.type		= POWER_SUPPLY_TYPE_BATTERY,
	.properties	= sm5714_bat_props,
	.num_properties	= ARRAY_SIZE(sm5714_bat_props),
	.get_property	= sm5714_bat_get_property,
};

static const struct power_supply_desc sm5714_usb_desc = {
	.name		= "sm5714-usb",
	.type		= POWER_SUPPLY_TYPE_USB,
	.properties	= sm5714_usb_props,
	.num_properties	= ARRAY_SIZE(sm5714_usb_props),
	.get_property	= sm5714_usb_get_property,
	.usb_types	= BIT(POWER_SUPPLY_USB_TYPE_UNKNOWN) |
			  BIT(POWER_SUPPLY_USB_TYPE_SDP) |
			  BIT(POWER_SUPPLY_USB_TYPE_CDP) |
			  BIT(POWER_SUPPLY_USB_TYPE_DCP) |
			  BIT(POWER_SUPPLY_USB_TYPE_PD),
};

/*
 * The charger interrupt is shared with the MUIC and fuel-gauge blocks.  Until
 * that MFD interrupt domain is implemented, poll VBUS and charging state once
 * per second so desktop indication follows a cable event promptly.  Capacity
 * still changes slowly and is sampled only every ten passes.
 */
static void sm5714_poll_work(struct work_struct *work)
{
	struct sm5714_battery *sm = container_of(to_delayed_work(work),
						 struct sm5714_battery,
						 poll_work);
	int online = sm5714_get_online_raw(sm);
	int usb_type = sm5714_get_usb_type(sm);
	int capacity = sm->last_capacity;
	int status, status_before = sm5714_get_status(sm);
	int temp, ret;
	bool changed = false;

	if (sm->poll_count++ % SM5714_CAPACITY_POLL_DIVIDER == 0 &&
	    sm5714_get_capacity(sm, &capacity))
		capacity = sm->last_capacity;

	if (online != 0) {
		ret = online < 0 ? online : sm5714_charge_fault(sm);
		if (!ret)
			ret = sm5714_get_temp(sm, &temp);
		if (ret) {
			/* A bad pack reading cannot authorize inherited Q4 state. */
			mutex_lock(&sm->chg_lock);
			changed = sm->thermal_state != SM5714_THERMAL_STOP;
			sm->thermal_state = SM5714_THERMAL_STOP;
			sm5714_revoke_switching_locked(sm);
			if (sm->typec_owned)
				sm->typec_fault = true;
			sm5714_disable_charging(sm);
			mutex_unlock(&sm->chg_lock);
			dev_warn_ratelimited(sm->dev,
					     "charge safety read failed; charging disabled: %d\n",
					     ret);
		} else if (!sm->last_online || usb_type != sm->last_usb_type ||
			   (sm->last_status == POWER_SUPPLY_STATUS_FULL &&
			    status_before == POWER_SUPPLY_STATUS_NOT_CHARGING) ||
			   sm5714_charge_thermal_state(sm, temp) !=
			   sm->thermal_state) {
			ret = sm5714_configure_charging(sm);
			if (ret)
				dev_warn_ratelimited(sm->dev,
						     "ordinary charge configuration failed: %d\n",
						     ret);
			changed = true;
		}
	} else if (online == 0 && sm->last_online) {
		mutex_lock(&sm->chg_lock);
		sm5714_revoke_switching_locked(sm);
		sm5714_disable_charging(sm);
		mutex_unlock(&sm->chg_lock);
	}

	status = sm5714_get_status(sm);
	if (status >= 0 &&
	    (status != sm->last_status || capacity != sm->last_capacity || changed)) {
		sm->last_status = status;
		sm->last_capacity = capacity;
		power_supply_changed(sm->psy_bat);
	}
	if (online >= 0 && !!online != sm->last_online) {
		sm->last_online = !!online;
		power_supply_changed(sm->psy_usb);
		power_supply_changed(sm->psy_bat);
	}
	if (usb_type >= 0 && usb_type != sm->last_usb_type) {
		sm->last_usb_type = usb_type;
		power_supply_changed(sm->psy_usb);
	}

	schedule_delayed_work(&sm->poll_work,
			      msecs_to_jiffies(SM5714_POLL_INTERVAL_MS));
}

static void sm5714_cancel_poll(void *data)
{
	struct sm5714_battery *sm = data;

	cancel_delayed_work_sync(&sm->poll_work);
	sm5714_disable_charging(sm);
}

static void sm5714_put_battery_info(void *data)
{
	struct sm5714_battery *sm = data;

	power_supply_put_battery_info(sm->psy_bat, sm->info);
}

static int sm5714_suspend(struct device *dev)
{
	struct sm5714_battery *sm = dev_get_drvdata(dev);
	int ret;

	mutex_lock(&sm->chg_lock);
	sm->suspended = true;
	sm5714_revoke_switching_locked(sm);
	mutex_unlock(&sm->chg_lock);
	cancel_delayed_work_sync(&sm->poll_work);
	/* Thermal polling cannot protect an unattended suspended charge. */
	mutex_lock(&sm->chg_lock);
	ret = sm5714_disable_charging(sm);
	mutex_unlock(&sm->chg_lock);
	return ret;
}

static int sm5714_resume(struct device *dev)
{
	struct sm5714_battery *sm = dev_get_drvdata(dev);

	mutex_lock(&sm->chg_lock);
	sm->suspended = false;
	mutex_unlock(&sm->chg_lock);
	sm->last_online = false;
	schedule_delayed_work(&sm->poll_work, 0);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(sm5714_pm_ops, sm5714_suspend, sm5714_resume);

static void sm5714_unpublish_companion(void *data)
{
	struct sm5714_battery *sm = data;

	mutex_lock(&sm5714_companion_lock);
	if (sm5714_companion == sm)
		sm5714_companion = NULL;
	mutex_lock(&sm->chg_lock);
	if (sm->switching_inhibited)
		sm5714_switching_blocked = true;
	sm5714_revoke_switching_locked(sm);
	sm->suspended = true;
	sm5714_disable_charging(sm);
	mutex_unlock(&sm->chg_lock);
	mutex_unlock(&sm5714_companion_lock);
}

static int sm5714_publish_companion(struct sm5714_battery *sm)
{
	int ret = 0;

	mutex_lock(&sm5714_companion_lock);
	if (sm5714_companion) {
		ret = -EBUSY;
	} else {
		mutex_lock(&sm->chg_lock);
		sm->switching_inhibited = sm5714_switching_blocked;
		mutex_unlock(&sm->chg_lock);
		sm5714_companion = sm;
	}
	mutex_unlock(&sm5714_companion_lock);
	return ret;
}

static int sm5714_probe(struct i2c_client *client)
{
	struct power_supply_config psy_cfg = {};
	struct device *dev = &client->dev;
	struct sm5714_battery *sm;
	int ret;

	if (!i2c_check_functionality(client->adapter,
				     I2C_FUNC_SMBUS_BYTE_DATA |
				     I2C_FUNC_SMBUS_WORD_DATA))
		return -EOPNOTSUPP;

	sm = devm_kzalloc(dev, sizeof(*sm), GFP_KERNEL);
	if (!sm)
		return -ENOMEM;

	sm->dev = dev;
	sm->chg = client;
	/* A retained9V contract must not inherit Stage1's DCP1800mA at boot.
	 * Start inhibited even if TCPC probe is delayed or fails entirely.
	 */
	sm->typec_owned = IS_ENABLED(CONFIG_TYPEC_SM5714);
	i2c_set_clientdata(client, sm);

	sm->battery_temp = devm_iio_channel_get(dev, "battery-temp");
	if (IS_ERR(sm->battery_temp))
		return dev_err_probe(dev, PTR_ERR(sm->battery_temp),
				     "cannot get battery thermistor\n");

	ret = devm_mutex_init(dev, &sm->sram_lock);
	if (ret)
		return ret;
	ret = devm_mutex_init(dev, &sm->chg_lock);
	if (ret)
		return ret;

	ret = i2c_smbus_read_byte_data(client, SM5714_CHG_REG_DEVICEID);
	if (ret < 0)
		return dev_err_probe(dev, ret, "no charger at 0x%02x\n",
				     client->addr);
	dev_info(dev, "SM5714 charger device id 0x%02x\n", ret);

	sm->fg = devm_i2c_new_dummy_device(dev, client->adapter,
					   SM5714_FG_I2C_ADDR);
	if (IS_ERR(sm->fg))
		return dev_err_probe(dev, PTR_ERR(sm->fg),
				     "cannot claim fuel gauge at 0x%02x\n",
				     SM5714_FG_I2C_ADDR);

	ret = i2c_smbus_read_word_data(sm->fg, SM5714_FG_REG_DEVICE_ID);
	if (ret < 0)
		return dev_err_probe(dev, ret, "no fuel gauge at 0x%02x\n",
				     SM5714_FG_I2C_ADDR);
	dev_info(dev, "SM5714 fuel gauge device id 0x%04x\n", ret);

	sm->muic = devm_i2c_new_dummy_device(dev, client->adapter,
					     SM5714_MUIC_I2C_ADDR);
	if (IS_ERR(sm->muic))
		return dev_err_probe(dev, PTR_ERR(sm->muic),
				     "cannot claim MUIC at 0x%02x\n",
				     SM5714_MUIC_I2C_ADDR);

	ret = i2c_smbus_read_byte_data(sm->muic, SM5714_MUIC_REG_DEVICE_ID);
	if (ret < 0)
		return dev_err_probe(dev, ret, "no MUIC at 0x%02x\n",
				     SM5714_MUIC_I2C_ADDR);
	dev_info(dev, "SM5714 MUIC device id 0x%02x\n", ret);

	/* Reject an inherited Android charging state until our limits are known. */
	ret = sm5714_disable_charging(sm);
	if (ret)
		return dev_err_probe(dev, ret, "cannot open charging path\n");
	if (sm->typec_owned) {
		ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
					     GENMASK(6, 0), sm5714_input_current_reg(100));
		if (ret)
			return dev_err_probe(dev, ret, "cannot establish pending-TCPM input cap\n");
	}

	psy_cfg.drv_data = sm;
	psy_cfg.fwnode = dev_fwnode(dev);

	sm->psy_bat = devm_power_supply_register(dev, &sm5714_bat_desc,
						 &psy_cfg);
	if (IS_ERR(sm->psy_bat))
		return dev_err_probe(dev, PTR_ERR(sm->psy_bat),
				     "cannot register battery\n");

	sm->psy_usb = devm_power_supply_register(dev, &sm5714_usb_desc,
						 &psy_cfg);
	if (IS_ERR(sm->psy_usb))
		return dev_err_probe(dev, PTR_ERR(sm->psy_usb),
				     "cannot register charger\n");

	ret = power_supply_get_battery_info(sm->psy_bat, &sm->info);
	if (ret)
		return dev_err_probe(dev, ret, "monitored battery data required\n");
	ret = devm_add_action_or_reset(dev, sm5714_put_battery_info, sm);
	if (ret)
		return ret;
	if (sm->info->voltage_max_design_uv != 4440000 ||
	    sm->info->charge_full_design_uah != 8160000)
		return dev_err_probe(dev, -EINVAL,
				     "unexpected X710 battery design data\n");
	sm->float_uv = sm->info->voltage_max_design_uv;
	ret = sm5714_set_float_voltage(sm);
	if (ret)
		dev_warn(dev, "cannot set 4.44 V float at probe; will retry on attach: %d\n",
			 ret);
	else
		dev_info(dev, "battery regulation voltage %u mV\n",
			 sm->float_uv / 1000);

	sm->last_status = sm5714_get_status(sm);
	if (sm5714_get_capacity(sm, &sm->last_capacity))
		sm->last_capacity = -1;
	ret = sm5714_get_online_raw(sm);
	if (ret < 0)
		return dev_err_probe(dev, ret, "cannot read VBUS state\n");
	sm->last_online = !!ret;
	sm->last_usb_type = sm5714_get_usb_type(sm);

	if (sm->last_online) {
		ret = sm5714_configure_charging(sm);
		if (ret)
			dev_warn(dev, "ordinary charging remains disabled: %d\n", ret);
		sm->last_status = sm5714_get_status(sm);
	}

	INIT_DELAYED_WORK(&sm->poll_work, sm5714_poll_work);
	ret = devm_add_action_or_reset(dev, sm5714_cancel_poll, sm);
	if (ret)
		return ret;
	schedule_delayed_work(&sm->poll_work,
			      msecs_to_jiffies(SM5714_POLL_INTERVAL_MS));

	/* Publish only after supplies, thermistor and teardown actions are ready. */
	ret = devm_add_action_or_reset(dev, sm5714_unpublish_companion, sm);
	if (ret)
		return ret;
	return sm5714_publish_companion(sm);
}

static const struct of_device_id sm5714_of_match[] = {
	{ .compatible = "siliconmitus,sm5714" },
	{ }
};
MODULE_DEVICE_TABLE(of, sm5714_of_match);

static const struct i2c_device_id sm5714_i2c_id[] = {
	{ "sm5714" },
	{ }
};
MODULE_DEVICE_TABLE(i2c, sm5714_i2c_id);

static void sm5714_shutdown(struct i2c_client *client)
{
	sm5714_unpublish_companion(i2c_get_clientdata(client));
	sm5714_cancel_poll(i2c_get_clientdata(client));
}

static struct i2c_driver sm5714_driver = {
	.driver = {
		.name = "sm5714-battery",
		.of_match_table = sm5714_of_match,
		.pm = pm_sleep_ptr(&sm5714_pm_ops),
	},
	.probe = sm5714_probe,
	.shutdown = sm5714_shutdown,
	.id_table = sm5714_i2c_id,
};
module_i2c_driver(sm5714_driver);

MODULE_DESCRIPTION("Silicon Mitus SM5714 charger and fuel gauge");
MODULE_LICENSE("GPL");
