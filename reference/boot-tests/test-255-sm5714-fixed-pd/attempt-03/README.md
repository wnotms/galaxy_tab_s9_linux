# Test255 attempt03: owner-authorized 18W PD battery telemetry

On 2026-09-29 the owner explicitly revised the workflow: connect the existing
18W PD supply directly and inspect power/battery behavior. This new attempt
supersedes the independent 5V-only-source and inline-meter prerequisites **for
this bounded telemetry observation only**. Earlier stopped/partial attempts
remain unchanged. No hardware driver, DTS, charging policy, kernel, rootfs,
service, USB/ADB setting, reboot or flashing is part of this attempt.

## What is measured

- Fuel-gauge battery voltage and signed current, SOC, pack thermistor and
  health/status are actual device telemetry. Battery net power in watts is
  `voltage_now_uV * current_now_uA / 1e12`. Positive means net battery charge;
  negative means net discharge. This excludes system consumption and losses.
- TCPM voltage/current are negotiated policy state, not measured input
  voltage/current. SM5714 `input_current_limit` is the configured switching
  limit read from hardware, not actual current draw. Contract voltage times
  this limit is a configured input ceiling, **not measured charger power**.
- The adapter's 18W label is its capability. No claim of actually drawing
  18W, independently measuring VBUS or validating the 9.5V physical limit
  can be made without an input measurement device. This revised observation
  carries that measurement limitation; no kernel safety boundary is relaxed.

## Registered sequence

1. On current boot `d745248e6a164243b9ccc5e6ede21fb2`, capture and verify the
   exact installed Test255 embedded config, notes, all five partitions, 181
   candidate modules, all three rollback module directories, protected
   rootfs/Test253 hashes, full kernel journal, failed units, battery state,
   Sink/Device and Wi-Fi SSH. Preserve raw evidence and push registration
   before asking the owner to connect the charger.
2. Use Lenovo YG65G USB-C2 18W only, USB-C1 idle, computer USB disconnected,
   Wi-Fi retained. Begin capture before the manual transition. Give an
   observed attach at most 45 seconds to establish a fixed 5V/9V contract;
   no sysfs requests or source policy writes. Record actual negotiated result.
3. Sample battery/USB/TCPM/roles on a target5s interval (archive actual gaps) and preserve complete kernel
   journals every30s. After contract stabilization, observe5 minutes. Stop
   on first non-clean; if clean, continue a further20 minutes on the same
   boot without another plug or reboot. Save the5-minute checkpoint separately.
4. Report protocol voltage/current, configured input limit/ceiling, battery
   net-power range/mean, raw current, voltage, SOC and temperature trend.
   A stable5V result is classified as5V; it cannot pass fixed9V acceptance.
   Lack of positive battery-current trend is suspect, not a forged charging
   pass. Never change current or float voltage to obtain a result.
5. Ask the owner to unplug the charger; confirm150s of USB offline,
   Discharging and negative current over Wi-Fi. Then reconnect to the PC and
   check nativeADB/NCM/Wi-Fi, Windows PnP and Sink/Device on the same boot,
   preserving bounded recovery transients and a150s stable window.

## Limits and stopping

Installed policy stays fixed5V/9V, max9V input1500mA (13.5W configured ceiling),
5V input<=1800mA, pack-current policy2100mA, float4440mV, original thermistor,
thermal and fail-safe rules. No PPS/APDO request, SM5440, Source/Host, OTG,
DP, Stage3, deliberate heating or protection-limit tests.

Stop and request charger unplug on temperature>=45°C, rapid pack rise>=3°C
within60s, VBAT>4.44V, positive battery current>2.1A, health notGood, negotiated
voltage outside fixed5V/9V, active PPS/AVS, input limit exceeding policy/grant,
lost contract/attach loop, TCPC/I2C/reset fault, reboot, kernel fault,
Wi-Fi rescue loss or unexplained suspect. Software can check contract state;
the independently measured actual-VBUS>9.5V gate remains **unobserved**, not
passed. Preserve first-failure evidence and do not retry automatically.

This is a battery/contract telemetry test with declared measurement limits,
not full original Test255 independent-voltage acceptance or a universal
hardware safety proof. Existing rollback remains available; no automatic
rollback is commanded by this attempt.
