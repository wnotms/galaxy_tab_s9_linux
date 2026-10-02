/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _X710_PD_SESSION_H
#define _X710_PD_SESSION_H
#include <linux/types.h>

/* Diagnostic result, never an active-pump or physical-protection grant. */
struct x710_pd_session_result {
	u64 started_ms, completed_ms, instance, source_generation, lease;
	int error, cleanup_error;
	bool pps_observed, fixed_observed, switching_released;
};

/* Sleepable explicit kernel consumer only. No worker/sysfs/automatic start.
 * Pump remains OFF. Errors after ownership require inspecting cleanup_error
 * and switching_released; a nonzero lease is not reusable authorization.
 */
int x710_pd_off_roundtrip(unsigned int mv, unsigned int ma,
			  struct x710_pd_session_result *out);
#endif
