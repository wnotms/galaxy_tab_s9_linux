/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _X710_CHARGE_CONTROLLER_H
#define _X710_CHARGE_CONTROLLER_H

#include "sm5440-native.h"

enum x710_controller_command {
	X710_CONTROLLER_OFF_ROUNDTRIP,
	X710_CONTROLLER_START,
	X710_CONTROLLER_REFRESH,
	X710_CONTROLLER_RETARGET,
	X710_CONTROLLER_MONITOR,
	X710_CONTROLLER_STOP,
};

/* Explicit kernel-only requests; no automatic PPS, pump or userspace control.
 * Direct commands remain unarmed. A timed-out waiter cancels forward progress,
 * not cleanup; inspect status until the original worker drains. New requests
 * cannot replace an in-flight or unresolved session.
 */
struct x710_controller_result {
	u64 generation, started_ms, completed_ms, instance, source_generation, lease;
	struct sm5440_native_owner hardware_owner;
	enum x710_charge_state state;
	int error, cleanup_error;
	bool inflight, cancelled, unresolved, hardware_quiesced, active;
	bool pps_observed, fixed_observed, switching_released;
};

int x710_charge_controller_request(enum x710_controller_command command,
				   unsigned int mv, unsigned int ma,
				   struct x710_controller_result *out);
void x710_charge_controller_cancel(void);
int x710_charge_controller_status(struct x710_controller_result *out);

#endif
