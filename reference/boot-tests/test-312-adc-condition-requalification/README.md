# Test312 — ADC condition profile with accepted ordinary recovery

Purpose: offline qualify the existing one-conversion, pump-OFF ENHIZ diagnostic
with the ordinary charging driver accepted in Test311. Do not deploy the older
Test305 profile that would replace that driver. Test311's existing adjacent
SM5440/gauge pairs still differ263/211/329mV; original REVBLK is retained.
The voltage cause remains UNKNOWN, and neither sensor is independent calibration.

Only select CONFIG_SM5440_ADC_CONDITION_TEST=y relative to accepted Test308/311
resolved config. Existing vendor-backed diagnostic code is unchanged: verify
pump OFF, record CNTL6/ADC validity, temporarily clear bit7, one bounded conversion,
restore and exactly read back original ENHIZ/ADC-off state. Original error and
restoration error remain separate; incomplete restoration stops. No reschedule,
companion publication, PPS request, pump ON, protection/current programming or
reset. Current fixed5/9V caps, 4.44V float, real-pack thermal, USER_NS/container,
DCC absence, DTS/USB/adbd/rootfs and TCPM remain unchanged.

Use the same eight-job ARM64/toolchain/ccache standard build, reusing the existing
308 incremental directory after freezing all formal artifacts and necessary
vmlinux/generated-header/CRC inputs. Former cache is then the new diagnostic
provider, not still a qualified308 cache. No complete build tree copy. Artifacts
and module archive go to out/kernel-x710-312-adc-condition in WSL.

Qualify actual ADC transaction and ordinary recovery host tests, changed-driver
W=1/sparse, exact embedded/resolved config, DTB, protected-source and181 modules.
Reuse unchanged prior tests; no full regression or Actions merely for this
existing isolated profile. Save real execution results, including failures.

Test312 is offline only. Physical comparison needs a separate registration,
fresh accepted311 identity/rescue/battery gate and explicit exact308/311
rollback, one PC-USB candidate boot, original/restored-condition and ADC/gauge
raw evidence,15s endpoint, unconditional accepted311 restoration. No physical
ADC/calibration/PPS/actuator acceptance follows from compilation.
