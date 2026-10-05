/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_NATIVE_H
#define _SM5440_NATIVE_H

#include "sm5440-supervisor.h"

/* Explicit in-kernel adapter operations, not a userspace charging interface.
 * CLAIM drains the ordinary poller before returning an owner. The owner must
 * RELEASE even after a failed operation. No supplier/regmap pointer escapes.
 * START/RESUME remain unavailable: no native activation grant exists yet.
 */
enum sm5440_native_operation {
	SM5440_NATIVE_CLAIM,
	SM5440_NATIVE_PREPARE,
	SM5440_NATIVE_ADC_BEGIN,
	SM5440_NATIVE_ADC_ADVANCE,
	SM5440_NATIVE_START,
	SM5440_NATIVE_PAUSE,
	SM5440_NATIVE_RESUME,
	SM5440_NATIVE_MONITOR_BEGIN,
	SM5440_NATIVE_MONITOR_ADVANCE,
	SM5440_NATIVE_BIND_SOURCE,
	SM5440_NATIVE_CHECK_OFF,
	SM5440_NATIVE_RELEASE,
};

struct sm5440_native_owner {
	u64 instance, generation;
};

struct sm5440_native_input {
	const struct x710_charge_facts *facts;
	const struct x710_physical_sample *physical;
	const struct sm5714_pd_snapshot *source;
	u64 consumer_epoch, switching_lease;
	unsigned int mv, ma;
};

struct sm5440_native_result {
	struct sm5440_native_owner owner;
	struct x710_physical_sample physical;
	/* Only valid with a successful newly completed ADC operation. */
	u32 vbus_uv;
	int die_decic;
	bool die_valid;
	bool owned, draining, hardware_quiesced;
	int operation_error, cleanup_error;
};

int sm5440_native_control(enum sm5440_native_operation operation,
			  const struct sm5440_native_owner *owner,
			  const struct sm5440_native_input *input,
			  struct sm5440_native_result *result);

#endif
