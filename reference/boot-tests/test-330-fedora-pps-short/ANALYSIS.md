# First production PPS failure: evidence and source findings

Observed: fixed9V/1.5A121s → TCPM ONLINE2/VOLTAGE_NOW8.72V/CURRENT_NOW1.8A,
CURRENT_MAX3A121.88/122.40s → ONLINE1 fixed9V/current1.5A on fallback. Two
PPS mode samples demonstrate actual TCPM PPS state, not merely a request log.
Continuous Fedora ADC reported9.268V during the8.72V request, IBUS0 and modeOFF;
no independent meter calibration exists, so do not equate requested or ADC
voltage with a separately certified VBUS value. 169 samples contain no modeON;
no `direct charge started` log. Start error-11 and physical fallback error-110
prevent the registered30s pump window. First exception and cleanup failure
remain separate in raw events; the top-level guard error alone is not a cause.

Source-confirmed integration defects, not claims of a complete hardware root
cause:

1. `sm5440_read_pack()` correctly takes an owned PPS snapshot initially, but
   its final coherence read always calls `sm5714_pd_read_snapshot()`. That
   public API calls `sm5714_read_fixed_pinned()` and requires ONLINE1/pps=false.
   Consequently it cannot validate an active PPS contract and returns-EAGAIN.
   `sm5440_pump_on()` rechecks the pack before CHG_ON, so this is a concrete
   adapter obstruction. The trace lacks a start-step label, so do not claim
   the exact recorded-11 site is individually instruction-traced.
2. Fixed physical return requires ADC delta<=100mV and rawIBUSzero. After
   protocol return to9V, ADC readings remain about9.272–9.293V, outside that
   proof gate; this is consistent with the recorded-110. No relaxation,
   calibration offset, fake READY or retry was applied. Physical bus/source/
   measurement behavior remains unresolved and requires source/evidence review.
3. Guardian cleanup incorrectly rejects USB_TYPE `[PD_PPS]` while ONLINE1.
   Pinned TCPM USB_TYPE describes source capability; ONLINE distinguishes active
   fixed/PPS. Raw ONLINE1/9V/1.5A proves protocol fixed return despite PPS-capable
   type. This host check can mislabel protocol recovery. It does not invalidate
   the real kernel physical-proof timeout or establish switching-path recovery.
4. The followed kernel journal fault was sampled after the logged monotonic
   fault; preserve timestamps and account for journal delivery latency. The
   kernel held the switching path inhibited, and cleanup unbound the worker;
   no repeated pump starts were observed. Do not assert zero delivery latency.

Safety outcome: source unplugged on request, then PC/TWRP exact Test323
boot/saved327-original181 restore with allfive readback/BCBclear/rootunmount.
Final attributed67673895 normal boot, passive pumpOFF/ordinaryPC charging,
ADB/Code0/deviceNCM/enrolledWiFi healthy; no CPU/panic signature. Restoring
recovery was successful; this is not a successful live fixed-switching handoff.

Next is offline minimal phase-correct snapshot use and correct ONLINE-based
observer classification, with fault/coherence tests. Keep physical-proof limits
and same-model Fedora ADC unchanged until independently justified; no PPS replay,
5min/20min observation or current/power increase in this failed series.
