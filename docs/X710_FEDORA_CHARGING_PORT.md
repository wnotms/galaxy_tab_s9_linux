# Fedora X710 charging source port

Owner direction on 2026-10-06: use the same-model Fedora source directly; stop
repairing the custom single-shot ADC diagnostic. Test326 remains a recorded
100ms timeout. Exact Test323 boot/modules have been restored. Neither a failed
diagnostic nor the change of implementation proves a hardware qualification.

## Source and implementation

Use `nacht20-de/gts9wifi-fedora-linux` commit
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9`, whose remote HEAD was checked on
2026-10-06. Preserve the GPL-2.0-only source and a reproducible diff. The port is
`sm5440-fedora.c`, built only by the explicit `sm5440-fedora` profile. The former
SM5440 driver, converter, diagnostic results and tests remain historical and
are not selected by this profile.

Carry over the actual Fedora register operations, ADC arithmetic, continuous
ADC reads, PPS target calculation, frequency selection, OFF/settle/ON refresh,
hardware watchdog and bounded retry worker. Do not require a per-read INT4 READY
or route this worker through the custom 100ms single-shot acquisition. Raw
continuous ADC is the Fedora operating model, not a claim of independently
calibrated or atomic multi-channel measurements.

Adapt only the board integration and bring-up boundaries:

- Linux TCPM remains the protocol owner. Use existing source-generation and
  switching-lease APIs instead of copying Fedora's battery `fast_charge` UI.
- Retain fixed5V <=1.8A and fixed9V <=1.5A. First PPS capability/request is capped
  at1.8A and8.2–10.5V; no5A parameter or automatic current ramp.
- Preserve SM5714 float4.44V and real pack thermistor/fail-closed policy. Entry
  requires SOC5–<80%, VBAT3.5–<4.3V, pack15–<38C, healthy attached battery.
  Initial active observation stops at pack42C, VBAT4.4V or die85C.
- Verify pump OFF before changing PPS or restoring switching. Check actual VBUS
  on return to fixed within100mV and zero pump input current; a failed cleanup
  leaves switching inhibited and latches refusal, rather than ignoring errors.
- Keep direct charging opt-in, default false. Probe must not reset the chip,
  request PPS, inhibit switching or activate the pump. A tested candidate and
  separate physical registration are required before enabling the opt-in.
- PM/remove/shutdown drain the worker before cleanup. Refuse suspend if cleanup
  fails; preserve the hardware watchdog when pump OFF cannot be verified.
  Only a healthy active poll resets consecutive failures. No new callback layers,
  unlocked charging worker races or long waits under a core charger mutex.

No DTS/TCPC/DWC3/gadget/adbd/rootfs/CPU/GPU change is needed. The existing
hub3/0x63 GPI-DMA overlay is sufficient; source/pack APIs identify companions
without a new TCPM power-supply phandle.

## Validation and next device work

Compile the actual port, test its register and entry/refresh/fallback/error
paths with host mocks, and compare resolved config/DTB and protected inputs to
Test323. Reuse the incremental build tree and frozen baseline artifacts. Keep
the live accepted device unchanged during this source port.

Next physical registration first checks this new default-OFF driver and ordinary
fixed charging. Then register one conservative1.8A PPS/pump run using Lenovo C1
with C2 empty, Wi-Fi rescue, source/pack/ADC telemetry and exact Test323 rollback.
Do not add another custom ADC repair round. Preserve first fault and stop;
no repeated REVBLK/PPS requests, no intentional overvoltage/heating/current
protection test. Higher currents remain separate stages after the first succeeds.
