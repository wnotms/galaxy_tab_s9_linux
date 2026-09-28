# Test253 attempt04: bounded physical USB ADB recovery accepted

The owner adopted the corrected observer and exact bounded FunctionFS warning
classification ("使用新方案"). Three fresh owner-operated computer USB unplug/
replug cycles completed on the same boot461c1408e42643afae5b48162771d077, PID834
and unchanged installed Test253 daemon053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5.
No kernel/config/DTB/modules/partitions/rootfs settings, daemon/gadget/controller
or host-server restart, backend switch or extra reboot occurred in this attempt.
The device remains the authorized Test252 Stage1 candidate, not promoted Test249
production. Previous Test253 stops and Test252's original stopped USB gate remain
unchanged. No Stage2/3 or further charging test was started.

| Cycle | Observed offline lower bound | Native+NCM recovery upper bound | Responsive window | First recovery errors retained | New bounded DISABLE W |
| --- | ---: | ---: | ---: | --- | ---: |
| 01 | 37.058s | 14.100s | 155.487s | NCM SSH8s timeout, then recovery | 1 |
| 02 | 40.166s | 15.346s | 155.466s | Native not-found; NCM SSH8s timeout, then recovery | 1 |
| 03 | 54.755s | 15.060s | 151.345s | NCM SSH8s timeout, then recovery | 0 |

All three real native-shell/NCM recoveries occurred inside the registered60s
window, measured conservatively from the last confirmed offline command START;
no invented delay was subtracted. UDC stayed configured while USB supply was
offline and host ADB disappeared; the observer correctly used supply+host state.
After each recovery, real native ADB, NCM authenticated SSH and Wi-Fi SSH stayed
responsive through>=150s elapsed checks and a continuous raw Wi-Fi journal stream.
Kernel source timestamps and full journals are retained. No new CPU-stall/panic,
other kernel fault/suspect, extra boot or extra cable transition was detected.

The two new exact pre-enable DISABLE warnings were tightly matched to monitor
spawn/DISABLE, physical-transition source range and one-count-per-cycle, then
ENABLE/worker within the adopted5s/1s bounds. Cycle01 ENABLE followed W0.153834s;
cycle02 followed W0.115724s. Cycle03 had no new W. No other new daemon warning/
error was accepted. This is not a blanket warning exemption or an explanation
of every event-queuing/host failure.

All first failures are preserved in command/stderr evidence. Every cycle had
one initial NCM SSH timeout that recovered in the bounded window; cycle02 also
had native enumeration not ready on the first shell request. The final verdict
is **passed bounded cable recovery with observed transients**, not three
transient-free/strict Test250 CLEAN transport rounds. No CPU-fault attribution
is made from those host transport errors.

Full fresh preflight, cycle01/02 full post-gates and the single final full gate
pass exact config410e4fe28f6fcc25950aba0029f8cda310b39ddbf1653f3eaa7b334e62f3b722,
notesfc35e05b1f8ddaf38faf228cd4aa7f02408e15d92beb908077c979536f99f0ed, all five
partition hashes, all181 paired candidate and181 retained original files,
DCC absence, exact running daemon and protected NCM/SSH/gadget/guard/holder/
packaged-daemon settings. `/dev/hvc0`, tty hvc0 and its active getty remain absent.
Final boot uptime4538.53s; no failed units, Code43 or new kernel fault. ADB,
source-bound NCM banner/authenticated SSH and Wi-Fi SSH pass. The final full gate
is also cycle03's post-cycle gate; its reference preserves original raw times
without repeating an unnecessary hash scan. Final Windows ADB37.0.1-15733141/
LIBADBUSB server-status bytes match the pre-cycle host-recovery snapshot.

The existing same-boot1MiB exact byte/SHA roundtrip prerequisite from attempt03
is preserved (SHA16e5a093c19e2c4e90d6a78d14768789aff01bee49d43ec7bc04fac0708b7ff4),
not claimed as a new transfer. Host code had1124 full tests plus33 focused tests
passed before hardware; adoption repeated33. Final evidence archive87 tests
also passed with no skip. No source change required another full source suite
or kernel rebuild. No CI/main merge was requested or performed.

This validates the installed userspace cable-recovery path only within these
registered windows. It is not long-term USB/CPU reliability, failure-rate, cold
boot or charging acceptance. Raw connected Windows `adb reconnect` from attempt02
remains unaccepted; the separately verified host-server rescan is a workaround
for that missing-host-transport state. Historical Code43/other USB incidents
and the independent UPower217/USER prerequisite issue remain unresolved.
