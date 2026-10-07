# Bounded Fedora-source pump candidate — offline PASS

Source `cf02c8223fd0f6829be854f4663854d0f8b42475`, Linux7.2-rc3 unchanged.
**READY_FOR_EXPLICIT_SCOPE_AND_FRESH_PREFLIGHT**, not hardware acceptance.
No candidate deployment/reboot/PPS/pump operation in this phase. Overall port
NOT_READY; actual current/protection/ADC/cutoff behavior still untested.

## Change and source evidence

Only `kernel/drivers/sm5440-fedora.c` changed among kernel inputs. Added default
false/read-only `direct_charge_once`, mutually exclusive with all three old modes.
Existing ordinary/defaultOFF and continuous opt-in paths remain available;
Test338 selects only the bounded path. Existing fixed5<=1.8A/fixed9<=1.5A,
SM5714float4.44V/thermal/suspend, SM5440regulation4.4V, TCPM/source-bound lease,
Test337 physical fixed-return and async ordinary recovery are unchanged.

One attempt/no retry/resume,30s software budget,100ms scheduling/500ms delivery
gap refusal, raw625uA/500uV safety checks, realpack<=3.6A/die<85C/VBAT<4.4V,
200mV ADC/gauge coherence, existing traced init readback beforeON. First refusal
turns OFF/returns fixed through the existing proof; failed cleanup is retained.
Read-to-clear fault harvest/current checks precede4s refresh; refresh parks the
pump and refuses re-arm after the deadline. Successful terminal needs positive
actual pump/gauge observations. PM terminally cancels this test mode.

Samsung `sm5440_init_reg_param` and same-model Fedora `hw_init` are referenced in
`source-reference.json`; no new protection recipe/register values. Vendor says
`SM5440 can't used HW_OCP`/`need_to_sw_ocp=1`; inheritedCNTL2=0xf2 is not hardware
OCP. Software scheduling/delivery checks are not hard-realtime physical cutoff
proof, and internal ADC/register readback is not independent calibration.

## Executed validation

| Check | Result |
| --- | --- |
| Actual C/owned pack/source/lease/fallback/ADC/policy |284 PASS/no skip,6.611s |
| New guardian/evidence + unchanged ordinary/discovery dependencies |44 PASS/no skip,0.303s |
| Full incremental ARM64 Image/DT/modules build |PASS,81.939s,8jobs/ccache/shared cache |
| Changed object W=1/sparse C=2 |PASS,12.793s,no warning; exact qualified object restored |
| Test331 resolved config/DT/release |exact byte-identical; config.diff/dtb.diff empty |
| Protected kernel inputs |108 unchanged;16 prior formal artifact files preserved |
| Modules |exact181-file set; runtime allocated bytes unchanged; built-in metadata identity changes only |
| Guardian/post-return observer |syntax PASS; raw stable reads/ADC only, final stop unbind; no IRQ-latch/config data writes |
| Full host suite/routing/CI/Actions |executed:false; affected coverage only under latest owner workflow |

New C tests exercise once-only completion, all16 exclusive boot-mode combinations,
fractional overcurrent, every entry I2C-refusal position, sensor/generation loss,
first fault/no restart, late refresh deadline, cleanup failure and suspend.
All older tests remain; development harness corrections recorded separately.

Machine-readable qualification, build environment/time/artifact hashes are in
`summary.json`, `PACKAGE.json` and `SHA256.json`. Armed boot SHA256:
`f7c5e153d4221e82282154bc3dd3373e38b61483a5e9355928cfaad8c456404a`.
No DTS/config/DCC/CPU/USB/DWC3/adbd/rootfs/SM5714 policy change.

## Test338 preparation

Independent [registration](../../boot-tests/test-338-bounded-direct-1p8a/README.md)
binds only one<=30s1.8A pump attempt,30s healthy ordinary return,15s unplug and
unconditional exact331 rollback. Device-local guardian captures full journal at
boundaries, follows new rows between them and always stops/unbinds the worker.
New post-return observer permits only the deliberately unbound pump provider,
sameboot/OFF/owned native completion/realpack/fixed gates. No automatic higher
current or new physical scope is inferred from Test337's pump-OFF pass.

One read-only current check: nativeADB not listed; strict enrolled WiFi166 works,
same accepted331boot6dc80750/config51/notes03/normalcmdline/DCCabsent. Battery58%,
3.883V,24.4C,Discharging/−1.064A/Good. This is not full deployment preflight or
a Test338 physical failure; live allfive/modules/OFF/rescue gates remain required.
No code or configuration was changed on the device.
