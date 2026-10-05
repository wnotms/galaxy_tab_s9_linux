/* SPDX-License-Identifier: GPL-2.0-only */
#ifndef _X710_CHARGE_OBSERVER_H
#define _X710_CHARGE_OBSERVER_H

#include "sm5714-stage2.h"
#include "sm5440-hw.h"

/* Zero tuple: ordinary fixed observation. Nonzero tuple: existing PPS owner.
 * These tokens are copied, never created/acquired/released by the observer.
 */
struct x710_observer_owner {
	u64 instance, source_generation, lease;
};

/* Native timestamps/epochs, not an ON, OCP or calibration grant. Errors zero
 * the entire output. Diagnostic RAW observations cannot populate this bundle.
 */
struct x710_charge_observation {
	struct sm5714_pd_snapshot source;
	struct sm5714_pack_snapshot pack;
	struct sm5440_passive_measurement physical;
	u64 generation, started_ms, completed_ms, oldest_ms;
};

/* Sleepable explicit kernel caller only, no charger/TCPM locks held. One
 * ordered worker, no automatic start/retry. Timeout invalidates publication;
 * the existing operation drains before another request may be admitted.
 */
int x710_charge_request_observation(const struct x710_observer_owner *owner,
				    struct x710_charge_observation *out);

#endif
