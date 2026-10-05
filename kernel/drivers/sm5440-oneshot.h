/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _SM5440_ONESHOT_H
#define _SM5440_ONESHOT_H

#include "sm5440-conversion.h"
#include "sm5714-stage2.h"

/* Diagnostic copies only. The actual native converter keeps its100ms budget.
 * No snapshot is a calibration/OCP/charging acceptance grant.
 */
#define SM5440_ONESHOT_SAMPLES 4U

struct sm5440_oneshot_sample {
	struct sm5440_conversion adc;
	struct sm5714_pack_snapshot before, after;
};

struct sm5440_oneshot_context {
	struct sm5440_oneshot_sample sample[SM5440_ONESHOT_SAMPLES];
	struct sm5714_pd_snapshot source;
	u64 generation;
	unsigned int count, readiness_checks;
	int error, cleanup_error, off_error, first_readiness_error;
	bool attempted, finished;
};

#endif
