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
 * It does not control the TCPC, OTG boost or SM5440 direct charger.  Register
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
#include <linux/pm.h>
#include <linux/power_supply.h>
#include <linux/workqueue.h>

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
};

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

static int sm5714_configure_charging(struct sm5714_battery *sm)
{
	unsigned int input_ma, fast_ma;
	enum sm5714_charge_thermal_state thermal_state;
	int usb_type;
	int temp;
	int ret;

	mutex_lock(&sm->chg_lock);
	/* Never inherit Android's unknown limits or leave Q4 closed on error. */
	ret = sm5714_disable_charging(sm);
	if (ret)
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

	if (thermal_state == SM5714_THERMAL_REDUCED) {
		input_ma = min(input_ma, 500U);
		fast_ma = min(fast_ma, 500U);
	}

	/*
	 * Match chg_set_enq4fet(): lower the input limit before closing Q4,
	 * then restore the limit advertised by the MUIC classification.
	 */
	ret = sm5714_chg_update_bits(sm, SM5714_CHG_REG_VBUSCNTL,
				     GENMASK(6, 0), sm5714_input_current_reg(500));
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
	if (ret)
		sm5714_disable_charging(sm);
	mutex_unlock(&sm->chg_lock);
	return ret;
}

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
			  BIT(POWER_SUPPLY_USB_TYPE_DCP),
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

	cancel_delayed_work_sync(&sm->poll_work);
	/* Thermal polling cannot protect an unattended suspended charge. */
	return sm5714_disable_charging(sm);
}

static int sm5714_resume(struct device *dev)
{
	struct sm5714_battery *sm = dev_get_drvdata(dev);

	sm->last_online = false;
	schedule_delayed_work(&sm->poll_work, 0);
	return 0;
}

static DEFINE_SIMPLE_DEV_PM_OPS(sm5714_pm_ops, sm5714_suspend, sm5714_resume);

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

	return 0;
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
