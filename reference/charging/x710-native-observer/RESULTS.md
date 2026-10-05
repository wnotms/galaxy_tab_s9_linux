# Native observation worker — offline qualification

The actual `x710-charge-observer.c` worker is compiled/linked under the existing
inactive policy profile. It connects real native source/pack and OFF-fresh ADC
providers through one ordered request worker, brackets connection/battery
identity, preserves acquisition timestamps, discards late publications, drains
on PM and never automatically queues on resume. No userspace activation,
automatic sampling, switching lease acquisition, PPS Request or pump enablement.

The data acquisition part is implemented, compiled and host-tested. This does
**not** complete the actual charging control/actuator/monitor/fallback adapter.
Independent physical conversion/calibration/current/cutoff/OCP qualification and
PPS/ON acceptance remain outstanding. No physical test or deployment this round;
the accepted311 baseline last verified by Test321 remains installed.

## Validation

* Final ARM64 Image.gz/DTB/modules build PASS: 168.276s, jobs8/ccache,
  same Linux7.2-rc3 pin/toolchain. Reused existing303 policy directory; its former
  Test303 provider identity is superseded, original formal outputs unchanged.
* Actual supplier/lease/ADC/session/transaction dependencies: 189 PASS,
  4.367s,0skips;15 new observer tests execute the real C collector,
  worker, request and PM functions with threaded kernel/supplier substitutes.
* W=1/sparse actual new object PASS:7.724s; no changed-driver warning.
  Known upstream vDSO `__kernel_getrandom` declaration warning retained.
* checkpatch:0errors/0warnings; shell syntax/diff whitespace pass.
* Exact embedded/resolved config, compiled overlay, native references and linked
  worker/PM/request symbols pass. Collector is fully inlined: actual DWARF
  inlined-subroutine ranges and object supplier references are preserved.
* DTB byte-identical to accepted311. All181 matched module files/archive checked.
  167modules differ in BTF/build-ID/debug-directory bookkeeping; every other
  allocated runtime byte/type/flags/size/alignment and non-debug symbol is equal.
  Debug additions/removal are restricted to303/308 build directory strings and
  debug_str symbol offsets; runtime relocations remain byte-identical.
* 61 protected sources and 20 original formal output hashes unchanged.
  No new full suite: latest owner affected-only workflow; prior historical full
  failure remains NOT PASS, not relabeled. No Actions/main merge.

## Exact config differences

Compared with accepted311: `X710_CHARGING_POLICY:n->y` and
`SM5440_ADC_CONDITION_TEST:n->absent`. The latter depends on `!X710_CHARGING_POLICY`;
this is actual Kconfig menu disappearance, not diagnostic enablement. TIMING/RAW
also remain absent. Compared with original Test303 policy config: no differences.
DCCn, USER_NS/mqueue/container gates, SM5714/ADC5 Gen3, float/thermal/fixed ceilings
remain. No fragment/DTS/SM5714/SM5440 register/TCPM/DWC3/gadget/adbd/rootfs changes.

## Corrected failures, retained evidence

Initial preparation failed because the new Makefile patch lacked sufficient
trailing context. The next actual ARM64 build found local `current` colliding
with the kernel task macro. Renamed it to `valid`, added the macro to the host
fixture and passed final build/189tests. Original compiler log retained; no
hardware replay. The previously trimmed303 directory needed object regeneration;
subsequent work can reuse the reconstructed incremental policy cache.

Initial artifact inspection incorrectly reused RAW-profile expectations and
classified all module debug differences as runtime changes; it also required a
separate symbol for the inlined collector. Actual dependency, ELF runtime/symbol
comparison and DWARF/reference evidence resolve these classifications. Initial
failed reports are retained alongside the final proof; no unexpected runtime
change is waived. An exact old308 debug directory removal is explicitly checked.

Next connect this data path to the actual serialized control worker and actuator
with activation disabled, then qualify the remaining physical safety/fallback
conditions. Do not replay Test318 or claim Test321 RAW transport proves ADC/OCP.
**Full SM5714/SM5440/PPS charging port: NOT READY.**
