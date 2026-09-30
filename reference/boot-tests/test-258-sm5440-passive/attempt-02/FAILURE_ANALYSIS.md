# First passive fault: evidence and limits

Candidate boot f96739d4c57b4968b971889368351458 has the exact registered config/
notes and paired boot/vendor/module installation. Probe reports SM5440 revision2
at0-0063, with its driver bound and generated hub3 child enabled. No PPS/pump-ON
API exists in this profile. Initial ADB/NCM/Wi-Fi and Windows no-Code43 gates
passed; Sink/Device and no failed unit were observed.

Kernel source timestamps: probe at1.605932s, first
`passive fault bitmap=0x82` at1.608590s. First host sample at uptime30.07s shows
Not charging/Unspecified failure and no online/VBUS/IBUS/die fields. Battery
gauge reports4008mV,-165mA,61%,29.6C,Good; this is not a pump ADC measurement.

0x82 is the driver's SOFTWARE fault bitmap, not a raw hardware register. In
sm5440-hw.h it denotes VBAT_OVP(bit1) and REVBLK(bit7). The corresponding vendor
hardware definitions are INT1 VBATOVP bit3 and INT3 REVBLK bit1, from owner GPL
msm-kernel/drivers/battery/charger/sm5440_charger/sm5440_charger.h. The vendor
IRQ handler logs separate INT/status arrays and handles forced cut-off using
direct-charge state plus mode. It is not evidence that these passive bits may
be ignored or that an active production recipe can be copied here.

Current sm5440_sample_once combines earlier INT latches, later consumed INT4
events and final STATUS values before decoding. The bitmap loses which array
provided each bit. No raw INT/STATUS/ADC or protection-register snapshot was
captured by this qualified driver, so this evidence cannot distinguish a prior
latch from a live comparator condition or an uninitialized protection state.
No default/reset threshold was read; do not claim VBATCNTL was3800mV. Battery
gauge4008mV below4440mV does not independently validate pump protection/ADC or
prove the two flags harmless. No physical overheating/overvoltage is established.

Source-level explanation of missing fields: bitmap logging occurs only after
sample_once succeeds (including mode-OFF checks before and after conversion).
The poller stores that sample, latches the fault and stops further polling.
After2500ms, get_property refuses cached online/voltage/current/temperature as
stale, while health retains Unspecified failure. This is consistent with the
observed missing fields; it is not evidence of a newly measured ADC timeout.
The test stopped rather than clearing the latch/retrying/relaxing its health gate.

The generic kernel scan detected no CPU stall/panic signature in the saved
window; it does not turn this SM5440 warning into a clean hardware result. No
new current/float/thermal/USB/TCPM/driver modification was made during analysis.
Registered exact Test255 rollback followed; candidate modules are retained
separately and the earlier attempt's seals remain unchanged.

Next offline work, before another registered test: preserve raw first-sample
INT versus STATUS arrays, mode and ADC completion/sample bytes with source
timestamps; audit vendor interpretation while OFF and protection reset-state
provenance. Keep fault refusal, current/float/thermal ceilings and pump OFF.
Do not clear/disable protection, suppress VBAT_OVP/REVBLK or enable PPS to make
the test pass. A changed driver needs its own scoped build/candidate validation.
No next candidate or physical retry is created by this analysis.
