# Cycle01: accepted under the adopted bounded recovery policy

The owner performed one computer USB unplug/replug, with Wi-Fi maintained, no
charger/reboot/config change. Conservative observed offline lower bound37.058s.
UDC stayed configured while USB supply was offline and Windows ADB absent;
the corrected observer detected the physical transition. Real native USB shell
succeeded on its first attempt with unchanged boot/PID834/hash.

NCM SSH attempt01 timed out at8s; attempt02 succeeded. The source-bound banner
passed. Combined native/NCM recovery conservative upper bound14.100s from the
last confirmed offline command START, below60s. The timeout is retained and
marked a recovery transient, not hidden or attributed to a CPU fault. This
acceptance uses the adopted cable-recovery window, not Test250's strict clean
transport definition or proof of no USB transients.

One exact pre-enable DISABLE W occurred at3534.201144, matching monitor11802;
ENABLE3534.354978 (0.153834s later), worker3534.355389. It passes only the adopted
exact/context/source-range/one-count/5s+1s bounds. Complete raw stream and final
journals are retained. Continuous actual ADB/Wi-Fi/NCM checks completed155.487s
after recovery, with no new kernel fault/suspect or extra boot/cable transition.

Full post-cycle five partitions/config/notes/181 candidate+181 original hashes,
DCC absence, daemon/protected settings/failed units/kernel/ADB/NCM/Wi-Fi checks
passed with no Code43. No device/host-server restart, reset, software change or
reboot occurred. This is1/3 adopted cable cycles; final series acceptance is
pending. Previous stopped attempts/Test252 remain stopped.
