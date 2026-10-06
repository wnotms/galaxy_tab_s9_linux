# Test328 — Fedora PPS 1.8 A first short run

Purpose: answer whether the accepted Fedora X710 charging implementation can
start bounded PPS/direct charging, remain healthy for 30 seconds and return to
fixed 9 V switching charging. Not 45 W acceptance or higher-current qualification.

Baseline: Test327 physical PASS, source376693d7 and qualificationf105ffed.
Reuse the exact kernel/config/DTB/notes and all181 matched modules. The only
boot payload difference is `sm5440_fedora.direct_charge=1`. No source, battery
policy, rootfs, USB/ADB or DTS modifications. Emergency rollback is the recorded
Test323 boot with `.gts9-test327-original`181 modules; successful completion
restores the Test327 default-OFF boot, leaving matched modules unchanged.

Sequence: registered/pushed inputs → fresh PC preflight → TWRP boot-only install
and readback → one attributed normal PC boot with pump OFF → authenticated Wi-Fi
and device-local guardian armed → owner connects Lenovo YG65G USB-C1 alone,
C2 empty → first PPS/pump start → 30s observation → checked driver unbind,
pump OFF and fixed9V/switching fallback → owner returns PC → default-OFF restore.
No repeated pump starts or automatic test retries. Guard waits at most240s;
refresh pump-OFF intervals at most2s. USB rescue/device NCM and Wi-Fi must work.

Entry: SOC20–<80%, pack20–<38°C, VBAT3.5–<4.3V, healthy real thermistor, exact
identity, pump OFF. Firmware PPS startup remains15–<38°C with the same<4.3V
ceiling. Active stop: SOC>=80%, pack>=42°C, VBAT>=4.4V, die>=85°C, measured
IBUS>1.8A, physical VBUS outside7.7–10.5V or >500mV from negotiated PPS,
invalid ADC, I2C fault, first kernel charging fault/CPU fault, reboot or lost
rescue. No threshold/current escalation. PPS requests8.2–10.5V/1.8A only.
TCPM ONLINE=2 identifies PPS; CURRENT_NOW is requested current, CURRENT_MAX is
the source APDO ceiling, as verified in this pinned Linux TCPM source.

Raw continuous ADC uses Fedora arithmetic without custom ADC fixes or read-clear
INT access. Physical ADC is not independently calibrated; power is an
instantaneous estimate, not a charger-output-meter or reliability claim.
Device-local cleanup drains the worker; independently requires unbound driver,
CNTL5 OFF, TCPM fixed9V and switching input<=1.5A. Cleanup failure is non-clean,
never silently accepted. Unknown OFF/lost rescue: unplug source immediately,
recover via PC/TWRP and exact323 rollback; do not retry charging.

Host validation: new guard/runner tests only; unchanged kernel qualification
is reused. No kernel rebuild/full host suite or GitHub Actions. Current images
count in retention window Test319–328. Full charging port remains NOT_READY;
5min/20min/higher-current tests require separate registration and authorization.
