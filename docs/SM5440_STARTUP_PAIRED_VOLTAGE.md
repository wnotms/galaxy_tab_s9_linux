# SM5440 startup paired-voltage diagnostic

Purpose: compare the first SM5440 OFF-mode startup samples with a nearby
SM5714 fuel-gauge VOLTAGE_NOW read. Test293 compared readings separated by
281 seconds; that cannot establish a sensor discrepancy.

Only the first sample and pending startup confirmations receive one standard
power_supply read, outside io_lock and the lifetime registry. SM5714 reads
fresh SRAM under its existing sram_lock. Record ADC-read completion upper
bound, gauge read start/end, errno and voltage. A missing supplier or I/O error
is unknown, never a fabricated value or retry. Release every supplier reference.

Diagnostic data cannot authorize charging, change the startup predicate,
clear fault, change converter/AVG32/read-to-clear sequence, alter the five-second
deadline, or relax 100ms freshness. At most three startup samples; retain the
first REVBLK sample and final failed sample. Gauge delay is an observer effect;
separate timestamps expose it, without asserting simultaneous conversions or
external calibration. Snapshot reads stay cache-only.

Build the passive profile, retain exact config/DTB and paired modules. Target
changed-driver/helper/cache/lifetime tests only; reuse unchanged Test294 gates.
Then independently register Test295: one candidate boot on PC USB, collect
startup journal and cached snapshot, 15-second endpoint, unconditional exact
Test263 rollback. No late observer module, PPS, pump ON, or current increase.
Known startup refusal remains a refusal; diagnostic completion is not health
acceptance. Any new CPU/kernel/USB/thermal fault stops collection and rolls back.
