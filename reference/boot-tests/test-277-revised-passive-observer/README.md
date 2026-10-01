# Test277 — revised passive observer acceptance

Independent new test, not a retry/rewrite of Test275. Owner's continued physical
work authorization covers this passive test. Review failed275 persistent logs
and exact263 rollback before deployment: failure source journal ends before
module load, pstore empty, actual freeze cause remains unproved. Test276 fixes
a definite observer task lifetime bug; original274 module MUST NOT be loaded.

Reuse sealed272399eb497 provider Image/config/DTB/181-module archive and existing
boot bundle d837b52f. Revised external observer2767a887eab/9aafabf6 uses owned
kthread lifetime; all hardware inputs remain frozen. No rebuild, config/DT/USB/
rootfs/thermal/protection/ADC/100ms change. No PPS, pumpON, higher current,
charger change or calibration claim. Ordinary5V<=1.8A/9V<=1.5A/4440mV unchanged.

One candidate boot on existing PC USB, Sink/Device, SDP500mA. Entry exact263
baseline+five partitions+181modules/rescue identity once; candidate readback once.
Unique .gts9-test277-original/stage/tested slots; preserve all older backups.
Module only in /tmp/test277-observer.ko, one explicit load, no autoload/force-load.

Maximum8calls/1s/unchanged100ms validity; collection maximum30s. First refusal
or8completed calls ends earlier. Record actual elapsed time; a refusal is NOT an
acquisition pass, and short collection is NOT a30s stability window. Preserve
raw results before one unload. Verify module/debugfs absence and sameboot
ADB/Wi-Fi/deviceNCM health. Unload health and fresh-acquisition outcome are
separate. Full kernel JSON at entry/end or first fault, source timestamps kept.
No full partitions/modules/full journal repeated during sampling. HostNCM TCP
is not required by owner's device-only endpoint criterion.

First API refusal stops requests; never reload/retry/clear latch/relax limits.
Any kernel/safety/identity/rescue/unload failure stops physical testing. Retain
first evidence and exact263 rollback if accessible, otherwise ask owner for
TWRP. No repeated shell timeouts to pursue a successful outcome. Frozen275pure
parser gates reused, exact bounded startup attribution still diagnostic-only:
20startupSMMU suspects remain unresolved, no global whitelist or CLEAN claim.

After observation/unload or failure recovery, restore exact263 boot+181modules
unconditionally, preserve tested candidate and all older backups. One baseline
endpoint, not another acquisition attempt. Safe BCB helper+ordinary reboot;
never Debian adb reboot recovery. Commit/push registration before physical write,
results afterwards. Local runner/gate tests and syntax only; reuse272 build/
provider qualification and27626affected/full1481/W1/sparse. No Actions/CI.

Device-normal completion does not qualify higher power. Fresh timing if refused,
independent calibration, nonzero-current/OCP, livePPS adapter and PM remain
unqualified. ActiveStage3 NOT READY.
