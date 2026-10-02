/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_HW_H
#define _SM5440_HW_H

/* Samsung X710 sm5440_charger.h/.c register map/conversions; see the source
 * hash manifest and docs/SM5440_REGISTER_AUDIT.md. No guessed IBAT ADC or OCP
 * enable recipe. Pure arithmetic is shared with executable host tests.
 */
#ifdef __KERNEL__
#include <linux/bitops.h>
#include <linux/types.h>

/* Copied passive facts, not a live adapter, calibrated ADC or ON grant. */
struct sm5440_passive_measurement {
	u64 observed_ms;
	u32 vbus_uv, vbat_uv, ibus_ua;
	int die_decic;
	bool online;
};

/* OFF-mode diagnostic observation, NOT a replacement for the100ms fresh API.
 * All times are BOOTTIME milliseconds. Completion is software publication
 * provenance, not the physical ADC sampling instant. Age uses oldest start.
 */
struct sm5440_passive_observation {
	struct sm5440_passive_measurement measurement;
	u64 request_ms, completed_ms, returned_ms, oldest_age_ms;
	u64 acquisition_seq;
	unsigned long request_epoch;
};

int sm5440_passive_read_cached(struct sm5440_passive_measurement *out);
/* Sleepable OFF-mode new conversion request; clears output on any refusal.
 * No hard-realtime/OCP guarantee, no active-mode or userspace ON interface.
 */
int sm5440_passive_request_fresh(struct sm5440_passive_measurement *out);
/* External sleepable caller, no charger/TCPM locks; telemetry only. */
int sm5440_passive_observe(struct sm5440_passive_observation *out);
#endif

/* Software freshness/delivery refusal budget, not converter/cutoff timing. */
#define SM5440_FRESH_REQUEST_MS 100U
/* Separate diagnostic collection budget; never an active freshness grant. */
#define SM5440_PASSIVE_OBSERVATION_MS 500U

#define SM5440_INT1	0x00
#define SM5440_INT4	0x03
#define SM5440_STATUS1	0x08
#define SM5440_CNTL2	0x0d
#define SM5440_VBUSCNTL	0x13
#define SM5440_VBATCNTL	0x14
#define SM5440_PRTNCNTL	0x19
#define SM5440_CNTL5	0x10
#define SM5440_ADCCNTL1	0x1c
#define SM5440_ADCCNTL2	0x1d
#define SM5440_ADC_VBUS	0x1e
#define SM5440_DEVICEID	0x2b
#define SM5440_MODE_MASK	GENMASK(3, 2)
#define SM5440_MODE_OFF	0
#define SM5440_ADC_ENABLE BIT(0)
#define SM5440_ADC_RATE	BIT(1)
#define SM5440_ADC_AVG32	BIT(3)
#define SM5440_ADC_READY	BIT(0)
#define SM5440_ADC_CHANNELS 0xdf /* vendor init_reg_param: VBUS/VBAT/IBUS/DIE */

enum sm5440_fault {
	SM5440_FAULT_VOUT_OVP = BIT(0),
	SM5440_FAULT_VBAT_OVP = BIT(1),
	SM5440_FAULT_REVERSE_OCP = BIT(2),
	SM5440_FAULT_VBUS_OVP = BIT(3),
	SM5440_FAULT_VBUS_UVLO = BIT(4),
	SM5440_FAULT_THERMAL = BIT(5),
	SM5440_FAULT_STARTUP = BIT(6),
	SM5440_FAULT_REVBLK = BIT(7),
	SM5440_FAULT_CFLY_SHORT = BIT(8),
	SM5440_FAULT_WATCHDOG = BIT(9),
	SM5440_FAULT_TIMER = BIT(10),
	SM5440_FAULT_MODE_LOST = BIT(11),
	SM5440_FAULT_VBUSPOK_LOST = BIT(12),
};

static inline unsigned int sm5440_raw13(u8 high, u8 low)
{
	return ((unsigned int)high << 5) | (low >> 3);
}

static inline unsigned int sm5440_vbus_uv(u8 high, u8 low)
{
	return 4096000U + sm5440_raw13(high, low) * 1000U;
}

static inline unsigned int sm5440_vbat_uv(u8 high, u8 low)
{
	return 2048000U + sm5440_raw13(high, low) * 500U;
}

static inline unsigned int sm5440_ibus_ua(u8 high, u8 low)
{
	return sm5440_raw13(high, low) * 625U;
}

static inline unsigned int sm5440_die_decic(u8 raw)
{
	return 225U + raw * 5U;
}

/* Validated bounds, round DOWN; future active code must not use vendor's
 * automatic +50mV/+300mA margins to exceed the independently approved caps.
 */
static inline int sm5440_vbat_code(unsigned int mv)
{
	if (mv < 3800 || mv > 4440)
		return -1;
	return (mv - 3800) * 10 / 125;
}

static inline int sm5440_ibus_code(unsigned int ma)
{
	if (ma < 1000 || ma > 1800)
		return -1;
	return ma / 50;
}

static inline int sm5440_frequency_code(unsigned int khz)
{
	if (khz != 450 && khz != 650 && khz != 850)
		return -1;
	return (khz - 250) / 50;
}

static inline unsigned int sm5440_decode_faults(const u8 st[4], bool running,
					       unsigned int mode)
{
	unsigned int faults = 0;

	if (st[0] & BIT(4))
		faults |= SM5440_FAULT_VOUT_OVP;
	if (st[0] & BIT(3))
		faults |= SM5440_FAULT_VBAT_OVP;
	if (st[0] & GENMASK(1, 0))
		faults |= SM5440_FAULT_REVERSE_OCP;
	if (st[2] & BIT(7))
		faults |= SM5440_FAULT_VBUS_OVP;
	/* Detached VBUS_UVLO is expected when the passive pump is OFF. */
	if (running && (st[2] & BIT(6)))
		faults |= SM5440_FAULT_VBUS_UVLO;
	if (st[2] & GENMASK(4, 3))
		faults |= SM5440_FAULT_THERMAL;
	if (st[1] & GENMASK(1, 0))
		faults |= SM5440_FAULT_THERMAL;
	if (st[2] & BIT(2))
		faults |= SM5440_FAULT_STARTUP;
	if (st[2] & BIT(1))
		faults |= SM5440_FAULT_REVBLK;
	if (st[2] & BIT(0))
		faults |= SM5440_FAULT_CFLY_SHORT;
	if (st[3] & BIT(2))
		faults |= SM5440_FAULT_WATCHDOG;
	if (st[3] & BIT(1))
		faults |= SM5440_FAULT_TIMER;
	if (running && mode != 1)
		faults |= SM5440_FAULT_MODE_LOST;
	if (running && !(st[2] & BIT(5)))
		faults |= SM5440_FAULT_VBUSPOK_LOST;
	/* IBUSLIM/VBATREG are regulation, not invented normal OCP flags. */
	return faults;
}

#endif
