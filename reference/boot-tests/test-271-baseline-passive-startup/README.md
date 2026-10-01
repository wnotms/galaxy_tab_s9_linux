# Test271 — one baseline startup diagnostic, not high-power acceptance

Owner's new "继续，允许实机测试" authorizes this separately registered single normal
Test263 warm boot. Test270 high-power admission remains NOT READY; this is not
continuation of that STOP, reclassification of Test267, or another candidate flash.
Fresh gauge VBAT4.215V is now below the original <4.3V startup range; old SM5440
fault0x80/cached4.3215V is retained. A normal new baseline boot starts its existing
probe/confirmation lifecycle; no manual latch clear, rebind or classifier change.

Purpose: does the unchanged passive driver complete its original narrow startup
confirmation and provide continuing fresh OFF-mode ADC cache at this lower pack
condition? One ordinary systemctl reboot, proven by changed bootID and unique
journal history. PCUSB SDP500mA, Sink/Device; keep charger disconnected.30s at5s
sampling follows first ready startup evidence;90s maximum to find the new boot.

Entry for this baseline diagnostic: batteryGood/present,5..100% SOC, fresh gauge
3.5..<4.3V and20..<38C, exact263 config/notes/cmdline, ADB and actualWi-Fi plus
recorded Windows USB/noCode43. SOC84% may undergo an ordinary OFF-pump baseline
boot but **still fails the unchanged high-power <80% admission gate**. Neither
this purpose nor a passing startup diagnosis grants direct-charge admission.
No historical passive/high-power gate/helper is edited or filtered to pass.

After boot require original startup_evidence() classification, retained raw
fault event plus two fresh confirmations<=5s when present, passiveGood/OFF,
original snapshot validator/raw decoding, fault0/pending0, current0, PCVBUS
4.5..5.5V, snapshotVBAT<4.3V, die22.5..<42C, age<=2500ms and advancing conversion
stamps. Config/notes/cmdline/roles/protection stay unchanged, no failed unit,
CPU/kernel/newpassive fault; final ADB and Wi-Fi respond and Windows noCode43.
Complete boundary journals and per-sample increments are retained; ended target
boot journal and new boot remain attributed separately. No active100ms sampling/
calibration/OCP acceptance or functional hostNCM claim is made.

Stop first new failure; no second reboot, automatic retry, PPS/pumpON/raise
current, thermal/gate/USB/rootfs/partition/module change. No baseline software
change needs rollback. On failure preserve the new first snapshot/journal,
leave fixed switching path unchanged, report readiness NOT READY.

8 focused actual fixture/parser gates + syntax pass, original kernel263 and
Test269 qualification reused; no rebuild/full1396 repeat. The new runner is
host-only orchestration, never writes configuration or registers. Push this
registration before systemctl reboot. Test269 live adapter does not exist and
its retarget function is not exercised by this physical baseline diagnosis.
