# Test309 ordinary charger program-witness acceptance

Purpose: one normal Test308 candidate boot on PC USB and a15-second same-boot
endpoint. Verify existing ordinary programming and essential device rescue,
without intentionally resetting the charger or manufacturing a fault. This is
not SM5440 ADC/PPS/pump acceptance or proof of long-term charging reliability.

Source158d0dd3 / Test308:102 affected tests, ARM64 build/W=1/sparse,96 protected
files, exact feature config/DT and181 paired module files already qualified.
Reuse that qualification. The one config-text delta versus accepted299 is the
existing default-off ADC declaration; both its diagnostic and PPS policy remain
disabled. DTB is byte-identical; float4.44V and thermal/current policy remain.
Test306 retains its original registration/results/input seal; never substitute
this ordinary candidate into that condition experiment.

## Entry and sequence

Last authoritative Test307 reading was0%/2.775V/Not charging/lpcharge=1. Physical
entry is STOP until ordinary recharge is confirmed and a fresh normal baseline
meets registered limits: SOC5..<80, gauge3.5..<4.3V, real pack20..<38C, Good and
present. Keep PPS/pump OFF. No flash/reboot or live register repair is done by
package creation, import, host tests or this registration.

1. After safe recharge, connect PC USB. One combined readonly preflight proves
   accepted299 config/notes/normal cmdline/battery/rescue/SinkDevice/DCC absence;
   allfive partition hashes and181 original module hashes are checked once.
   Save boot history/full kernel JSON/real pack zone/Windows USB evidence. One
   host NCM probe is recorded; host-only timeout with device NCM/ADB healthy
   does not cause repeated waits. Low battery or lpcharge stops before BCB.
2. Registration/source/stage must be committed and pushed to origin/test.
   Recheck one live safety/identity boundary within300s; from the first possible
   BCB request record cleanup required. Use the existing normal-reboot recovery
   helper and native TWRP readiness/board/root checks. Write only paired boot
   and modules; verify allfive partitions/181 files at readback, clear BCB and
   unmount. No rootfs service/config or USB policy change.
3. One normal candidate boot. Readiness ends as soon as ADB/services/device NCM
   respond (maximum150s); no extra startup sleep or observer module. Unique
   boot attribution, candidate config/notes, pack state, SinkDevice and DCC
   absence are mandatory. Collect full kernel JSON/history/Windows evidence
   and one host NCM probe concurrently. Check actual real pack thermal zone.
4. Read seven documented stable SM5714 controls by guarded atomic pointer/read
   transactions. Match power_supply provider, actual bound driver and OF
   compatible before any bus access. No configuration-data writes, INT reads,
   force-mode ioctl, fault clearing, unbind or controller reset. Confirm POK,
   no OVP/WDT fault, ordinary mode5/Q4ON, input100..500mA (AICL reduction allowed),
   fast500mA code and4.44V code. This reads actual controls rather than inferring
   programming from initialization logs or current sign.
5. Observe15s, then repeat one current/controls/real-thermal packet and full
   boundary journal on the same boot. No full partition/module rehash. No drift
   is a valid normal result. If a natural mismatch occurred, preserve it and
   require exactly one verified recovery within5s; missing/second/failed
   recovery stops. Do not induce reset/thermal/I2C failures on hardware.
6. On registered device PASS retain the candidate and paired181 files. A
   subsequent host-only completion-record failure is reported separately and
   cannot automatically reflash an already completed device scope. On first
   actual failure preserve evidence and restore exact accepted299 once. Unsafe
   battery/lost rescue/unknown partition state stops automatic recovery and
   requests manual TWRP; no blind retry or another candidate boot. Missing
   failed-candidate boot history remains a gap, never a clean attribution.

## Stop / rollback / later work

See registration.json for explicit conditions. Critical battery/invalid real
sensor, kernel CPU/panic/stall, new I2C/program fault, mismatched actual controls,
PPS/pump/diagnostic capability, Code43, device rescue loss, unexplained reboot
or missing evidence stops. The inherited passive startup REVBLK refusal is
classified exactly as before; it is not waived for a new fault and does not
prove ADC physical validity or authorize direct charging. The inherited negative
`charging_authorized` reporting flag never grants PPS/pump/ADC qualification;
ordinary switching is independently constrained by the existing kernel policy.

Exact accepted299 rollback boot/modules are retained, with unique309 original
module slots and readback. The passive thermal registration fix stays in both
candidate and rollback. This registered test makes no ADC request and does not
increase current, negotiate PPS, activate SM5440, change DTS/kernel config,
rootfs, gadget, TCPM core or adbd.

A successful short PC scope is not full Stage3 completion. Next assess ordinary
fixed9V charging with Wi-Fi observation, then independently register any ADC
condition comparison. Physical ADC validity/freshness, active protections,
actual PPS/handoff/fallback and PM acceptance remain required. Do not silently
carry Test309 acceptance into a different charger/power-path scope.

## Commands (physical actions NOT executed at registration)

```sh
python3 reference/boot-tests/test-309-ordinary-program-acceptance/host_flow.py preflight
python3 reference/boot-tests/test-309-ordinary-program-acceptance/host_flow.py run
# Only for registered cleanup; --from-recovery requires confirmed manual TWRP:
python3 reference/boot-tests/test-309-ordinary-program-acceptance/host_flow.py restore --from-recovery
```

Windows tools remain in D:\android\platform-tools. Only the bounded7-file
package is staged in D:\android\gts9-active\gts9-test309 (~238MiB).
