# Test268 — battery-only readiness, not candidate acceptance

Owner requests continued physical testing after Test267 STOP/rollback. Current
Test263 boot4bbd8221/identity/services/Wi-Fi remain verified, batteryGood/SOC100,
4.394V/32.3C. Existing passive0x80/fault1 persists; ADC snapshot is stale and
cannot supply a new entry measurement. Test267 remains failed/immutable.

This new purpose observes normal SM5714 battery discharge for150s at5s intervals
after the owner confirms unplugging PCUSB. Keep Wi-Fi, do not attach a charger
or reboot. Verify USBonline0/Discharging/negative current and pack<42C, healthy
battery,3.4..4.44V, SOC5..100; initial20..<38C and no>=10C fast rise. Keep the
entire old passive cache/fault/protection/mode provenance unchanged, with no
I2C register access, new conversion, unbind/rebind, latch clearing or hardware
write. Its frozen OFF/IBUS0 cache is not fresh hardware evidence. New kernel/
CPU/I2C/passive fault, reboot, lostWi-Fi/identity or health/thermal/voltage/current
anomaly stops immediately; no repeat-to-clean.

Capture full kernel journal at boundaries and incremental journal per sample.
Single combined command captures boot/gauge/USB/cache/failedunits. No repeated
module/partition hashes, kernel build/full regression or CI.8 focused gate tests
and syntax pass. Kernel qualification reused from installed Test263; Test266
remains offline/not accepted. No active charging/current change/PPS/pumpON.

Human action acknowledgement precedes the timed window; no300s human-wait timer.
This is an endpoint window, not precise unplug/reconnect latency. A completed
battery window does not repair or qualify SM5440. Gauge voltage/SOC readiness
is only a hint; it cannot replace fresh SM5440 ADC. Next candidate boot/flash
requires a separate registration with actual entry conditions, not stale values.
If still full/out of range, end this bounded window without indefinite discharge
waiting or automatic reboot. ActiveStage3 remains NOT READY.

No software/partition change, so no rollback operation is needed for this phase.
Leave USB disconnected unless the owner is later asked to reconnect; no automatic
charging/reconnect phase is included in this registration.
