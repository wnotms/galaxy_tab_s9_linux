# Test267 installation checkpoint

New boot b9f296d8 and181 paired module files installed with readback. All other
four partitions unchanged. Exact Test263 modules saved to .gts9-test267-original;
older Test263/Test260 backups retained. Root unmounted/BCB cleared; still TWRP.
Candidate has not booted or passed physical acceptance at this checkpoint.

Existing sm5440_passive_pc_sample() startup REVBLK classifier also requires
VBAT<4.3V. This driver limit is not changed by the registered full-battery
snapshot boundary. A full pack may therefore fail the narrow startup classifier;
if so, retain first evidence and stop/restore Test263, never exempt that fault
or broaden the kernel gate to finish the trial.

Host tests42 passed; kernel build/full1379 reused, no repeated kernel/full run.
No PPS/pumpON/current/protection/thermal/USB change.
