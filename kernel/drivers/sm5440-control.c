// SPDX-License-Identifier: GPL-2.0-only
/* Samsung X710 OFF-only register preparation, not pump activation.
 * Hardware sources: sm5440_set_ibuslim/set_vbatreg/set_freq and X710 freq_siop.
 * See docs/SM5440_OFF_SETTINGS_TRANSACTION.md. Do not import disabled OCP init,
 * vendor offsets, ENHIZ/reset or protocol policy into these helpers.
 */
#include <linux/errno.h>
#include <linux/regmap.h>

#include "sm5440-control.h"
#include "sm5440-hw.h"

/* Vendor register map/field masks, not guessed protection enables. */
static const u8 sm5440_setting_regs[SM5440_CONTROL_SETTINGS] = {
	0x16, /* IBUSCNTL: vendor sm5440_set_ibuslim(), 50mA/code. */
	SM5440_VBATCNTL, /* vendor sm5440_set_vbatreg(), 12.5mV/code. */
	0x12, /* CNTL7: vendor sm5440_set_freq(), 50kHz/code. */
};
static const u8 sm5440_setting_masks[SM5440_CONTROL_SETTINGS] = { 0x7f, 0x3f, 0x1f };
/* CNTL1/2/3/4/6, VBUS/VOUT protection, PRTNCNTL, thermal thresholds.
 * CNTL1 is witnessed in full: neither watchdog enable nor reset is allowed.
 */
static const u8 sm5440_witness_regs[SM5440_CONTROL_WITNESSES] = {
	0x0c, 0x0d, 0x0e, 0x0f, 0x11, 0x13, 0x15, 0x19, 0x1a, 0x1b,
};

static int sm5440_control_off(struct regmap *map, struct sm5440_control *c)
{
	unsigned int mode;
	int ret;

	c->off_verified = false;
	ret = regmap_read(map, SM5440_CNTL5, &mode);
	if (ret)
		return ret;
	if (mode & SM5440_MODE_MASK)
		return -EBUSY;
	c->off_verified = true;
	return 0;
}

static int sm5440_control_status(struct regmap *map, struct sm5440_control *c,
				  u8 status[4])
{
	int ret = sm5440_control_off(map, c);

	if (!ret)
		ret = regmap_bulk_read(map, SM5440_STATUS1, status, 4);
	if (ret)
		return ret;
	if (sm5440_decode_faults(status, false, 0) || (status[2] & BIT(6)))
		return -EIO;
	return status[2] & BIT(5) ? 0 : -ENOLINK;
}

/* Full-byte readback detects an ignored write or drift in unowned bits. */
static int sm5440_control_update(struct regmap *map, u8 reg, u8 mask,
				  u8 value, u8 original)
{
	unsigned int after;
	int ret;

	ret = regmap_update_bits(map, reg, mask, value);
	if (!ret)
		ret = regmap_read(map, reg, &after);
	if (!ret && after != ((original & ~mask) | (value & mask)))
		ret = -EIO;
	return ret;
}

static int sm5440_control_witness(struct regmap *map, struct sm5440_control *c,
				   bool capture)
{
	unsigned int value;
	int i, ret;

	for (i = 0; i < SM5440_CONTROL_WITNESSES; i++) {
		ret = regmap_read(map, sm5440_witness_regs[i], &value);
		if (ret)
			return ret;
		if (capture)
			c->witness[i] = value;
		else if (value != c->witness[i])
			return -EIO;
	}
	if (capture)
		c->witness_valid = true;
	return 0;
}

/* Do not restore inherited high limits until OFF is actually read back.
 * A successful OFF write alone is not proof. On uncertainty retain pending.
 * Restore only owned fields; full-byte verification also flags unrelated drift.
 */
int sm5440_control_restore(struct regmap *map, struct sm5440_control *c)
{
	int i, ret, err;

	if (!map || !c)
		return -EINVAL;
	if (!c->pending)
		return c->restore_error;
	ret = regmap_update_bits(map, SM5440_CNTL5, SM5440_MODE_MASK, SM5440_MODE_OFF);
	err = sm5440_control_off(map, c);
	if (!ret)
		ret = err;
	if (!c->off_verified)
		goto out;
	for (i = SM5440_CONTROL_SETTINGS - 1; i >= 0; i--) {
		if (!(c->attempted & BIT(i)))
			continue;
		err = sm5440_control_update(map, sm5440_setting_regs[i],
					    sm5440_setting_masks[i], c->before[i],
					    c->before[i]);
		if (!ret)
			ret = err;
	}
	err = sm5440_control_off(map, c);
	if (!ret)
		ret = err;
	err = sm5440_control_witness(map, c, false);
	if (!ret)
		ret = err;
out:
	c->restore_error = ret;
	if (ret) {
		c->state = SM5440_CONTROL_FAULT;
	} else {
		c->pending = false;
		c->state = c->operation_error ? SM5440_CONTROL_FAULT : SM5440_CONTROL_DONE;
	}
	return ret;
}

int sm5440_control_prepare(struct regmap *map, unsigned int input_ma,
			   struct sm5440_control *c)
{
	u8 target[SM5440_CONTROL_SETTINGS];
	unsigned int value, khz;
	int i, code, ret;

	if (!map || !c)
		return -EINVAL;
	if (c->state != SM5440_CONTROL_IDLE || c->pending)
		return -EALREADY;
	code = sm5440_ibus_code(input_ma);
	if (code < 0)
		return -ERANGE;
	/* X710 board frequency policy, not an arbitrary caller-selected frequency. */
	khz = input_ma <= 1100 ? 450 : input_ma <= 1700 ? 650 : 850;
	target[0] = code;
	target[1] = sm5440_vbat_code(4440);
	target[2] = sm5440_frequency_code(khz);
	ret = regmap_read(map, SM5440_DEVICEID, &value);
	if (!ret && (value & 0xf) != 1)
		ret = -ENODEV;
	if (ret)
		goto fault;
	ret = sm5440_control_status(map, c, c->status_before);
	if (ret)
		goto fault;
	ret = sm5440_control_witness(map, c, true);
	if (ret)
		goto fault;
	for (i = 0; i < SM5440_CONTROL_SETTINGS; i++) {
		ret = regmap_read(map, sm5440_setting_regs[i], &value);
		if (ret)
			goto fault;
		c->before[i] = value;
	}
	for (i = 0; i < SM5440_CONTROL_SETTINGS; i++) {
		ret = sm5440_control_status(map, c, c->status_after);
		if (ret)
			goto fault;
		/* I2C can report failure after silicon accepted the write. */
		c->attempted |= BIT(i);
		c->pending = true;
		ret = sm5440_control_update(map, sm5440_setting_regs[i],
					    sm5440_setting_masks[i], target[i], c->before[i]);
		if (ret)
			goto fault;
	}
	ret = sm5440_control_status(map, c, c->status_after);
	if (!ret)
		ret = sm5440_control_witness(map, c, false);
	if (ret)
		goto fault;
	c->state = SM5440_CONTROL_PREPARED;
	return 0;
fault:
	c->operation_error = ret;
	c->state = SM5440_CONTROL_FAULT;
	if (c->pending)
		sm5440_control_restore(map, c);
	return ret;
}
