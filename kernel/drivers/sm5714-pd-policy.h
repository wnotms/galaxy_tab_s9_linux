/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5714_PD_POLICY_H
#define _SM5714_PD_POLICY_H

/* Pure Request bounds; protocol encoding comes from Linux7.2-rc3 usb/pd.h.
 * This is a board safety gate, not PDO selection or a second PD engine.
 * Fixed limits are Test255's accepted ceilings. PPS limits are future bringup
 * bounds only; the live Stage3A transport never authorizes PPS.
 */
#ifdef __KERNEL__
#include <linux/usb/pd.h>
#endif

#define SM5714_FIXED_5V_MA	1800U
#define SM5714_FIXED_9V_MA	1500U
#define SM5714_PPS_MIN_MV		8200U
#define SM5714_PPS_MAX_MV		10500U
#define SM5714_PPS_MAX_MA		1800U

static inline bool sm5714_validate_fixed_request(u32 pdo, u32 rdo)
{
	unsigned int mv, op, maximum, limit, board;

	/* No EPR position/capability, GiveBack, or reserved bits21:20. */
	if (pdo_type(pdo) != PDO_TYPE_FIXED ||
	    (rdo & (BIT(31) | BIT(27) | GENMASK(22, 20))))
		return false;
	mv = pdo_fixed_voltage(pdo);
	if (mv != 5000 && mv != 9000)
		return false;
	board = mv == 9000 ? SM5714_FIXED_9V_MA : SM5714_FIXED_5V_MA;
	limit = min(pdo_max_current(pdo), board);
	op = rdo_op_current(rdo);
	maximum = rdo_max_current(rdo);
	/* CAP_MISMATCH may describe desired maximum above a weak source offer.
	 * Its operating current still cannot exceed that offer or board limit.
	 */
	return op && op <= limit && maximum >= op && maximum <= board &&
		((rdo & RDO_CAP_MISMATCH) || maximum <= limit);
}

static inline bool sm5714_validate_pps_request(u32 pdo, u32 rdo)
{
	unsigned int minimum, maximum, offer, mv, ma;

	/* APDO type0=PPS only. Reject AVS/EPR and reserved APDO fields.
	 * Bit27 is the source PPS power-limited flag, not a reserved bit.
	 */
	if ((pdo >> 30) != 3 || ((pdo >> 28) & 3) ||
	    (pdo & (GENMASK(26, 25) | BIT(16) | BIT(7))))
		return false;
	/* PPS RDO: voltage20mV bits19:9, current50mA bits6:0.
	 * GiveBack/bit31/EPR and reserved22:20/8:7 are forbidden.
	 */
	if (rdo & (BIT(31) | BIT(27) | GENMASK(22, 20) | GENMASK(8, 7)))
		return false;
	minimum = ((pdo >> 8) & 0xff) * 100;
	maximum = ((pdo >> 17) & 0xff) * 100;
	offer = (pdo & 0x7f) * 50;
	mv = ((rdo >> 9) & 0x7ff) * 20;
	ma = (rdo & 0x7f) * 50;
	return minimum && minimum <= maximum && offer && ma &&
		mv >= minimum && mv <= maximum && ma <= offer &&
		mv >= SM5714_PPS_MIN_MV && mv <= SM5714_PPS_MAX_MV &&
		ma <= SM5714_PPS_MAX_MA;
}

static inline bool sm5714_validate_request(const u32 *offers, unsigned int count,
					 u32 rdo, bool pps_authorized)
{
	unsigned int index = rdo_index(rdo);

	if (!offers || !count || count > PD_MAX_PAYLOAD ||
	    !index || index > count || (rdo & BIT(31)))
		return false;
	if (pdo_type(offers[index - 1]) == PDO_TYPE_FIXED)
		return sm5714_validate_fixed_request(offers[index - 1], rdo);
	return pps_authorized && sm5714_validate_pps_request(offers[index - 1], rdo);
}

#endif
