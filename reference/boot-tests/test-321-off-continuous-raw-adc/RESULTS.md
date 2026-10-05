# Test321 — OFF raw capture passed, exact baseline restored

One registered candidate boot `6d6fe2e7-4da4-4d20-95cb-465812e81f09` uniquely followed baseline
`e71954cf-fb78-4ee3-aa76-cbaafe5841fc`. Config/notes/normal cmdline and matched
181-module boot payload are exact. No second candidate boot or converter replay.

Actual worker: eight raw reads,0READY observations,42steps,507ms transaction
(2672–3179ms BOOTTIME). Disable2673,enable2734:61ms software rearm bracket.
First ADC read2757–2758ms; remaining reads2817–2818,...,3177–3178ms.
First enable-to-read23ms, next previous-read-end-to-read59ms; read brackets1ms.
These are software operation times, not chip conversion instants. Native source/
pack epochs stable; exact ADC controls0c/df restored, errors/cleanup/OFF-errors0.

Raw VBUS4.941V,IBUS0,die25.5C; VBAT3.5350–3.5355V. Only a single ADC VBAT
LSB change is observed. Native real pack3.705–3.747V during brackets,20%/28C;
independent pack/SM5440 readings differ about170–212mV in this OFF state.
Do not manufacture a calibration offset or claim fresh/coherent100ms conversion.
Continuous READY was not necessary for successful raw register transport; failed
Test318 remains STOP and its READY requirements/results remain unchanged.

Candidate ADB,deviceNCM,hostNCM SSHprobe,Wi-Fi preflight rescue, Sink/Device,
realpack thermal, float/current control readback, no failed unit/DCC/Code43 pass.
Completed RAW waited for sshd startup without repeating ADC;15s sameboot endpoint
passes. Full candidate and endpoint kernel journals retained. No detected new
CPU/panic/Oops/I2C or unclassified fault. Each boot retains10 known startupMDSS/
SMMU contexts with UNKNOWN root cause: no overall stability-clean claim.

Unconditional original accepted311 boot plus original181 modules restored;
allfive partitions/readback exact, BCB cleared and root unmounted. Final boot
`ecaa3c64-5c69-4bbe-b755-1a2aff6a88ca` uniquely attributed, normal config/notes/cmdline, real thermal
and controls pass. Native ADB/deviceNCM/hostNCM/WindowsCode0 pass. A single fresh
ADB discovery followed by authenticated Wi-Fi SSH at10.139.153.84 proves the
same final boot; no stale DHCP address polling. Final pack20%/3.710V/29.8C/Good,
pumpOFF/IBUS0/fault0. Mutation state `rollback_required:false`.

The outer host shell returned1 because it tried assigning zsh's reserved
`status` variable after the Python controller completed and printed success.
Terminal wrapper error retained separately; verified physical capture and exact
restoration are authoritative. No rerun to hide this host error.

Registration0f870fa6 and acceptedpreflightdbdd5b99 were pushed before physical
mutation.29 runner/parser host tests PASS0.160s/no skips; unchanged kernel and
all-suite qualification reused, `kernel_build.executed:false`. Historical full
run remains NOT PASS as recorded in the RAW qualification, not rerun/relabeled.
No new source/kernel build, Actions or main merge during this physical round.

No PPS,pumpON,current/protection/ENHIZ/DTS/rootfs/USB/adbd change. Fixed5<=1.8A,
fixed9<=1.5A,4.44V and real-pack thermal fail-closed remain. No extra cable dance.

Result: **OFF_RAW_CAPTURE_AND_EXACT_BASELINE_RESTORE_PASS** within this scope.
No calibration/current/cutoff/OCP/100ms freshness or higher-power acceptance.
Next complete the actual native charging adapter/worker and its fault/PM/fallback
integration with direct activation still disabled; keep raw observations out
of charging admission until their required safety provenance is established.
**Full charging port remains NOT READY.**
