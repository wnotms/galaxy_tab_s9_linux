# Test364 offline qualification and read-only baseline

80 affected tests across five modules passed, zero skips. Both offline shell
helpers passed `bash -n`. The actual 328-file stock archive was installed and
restored in a temporary host root; exact content/mtime and ownership ledger
were verified. No real device assets changed during this check.

Reuse the native-SoCinfo kernel/181-module/DTB qualification in
`reference/desktop-bringup/native-socinfo-kernel/`, platform ramdisk/boot/footer
qualification in `reference/desktop-bringup/ssc-early-firmware/`. No kernel or
routing change in this registration; build executed:false. Full3032 remains
NOTPASS, including the recorded retired prerequisites and later scoped SSC
import fix; this is not a new full-regression claim.

Fresh read-only preflight confirmed the accepted Test331 boot/config/notes,
allfive partition hashes and181 exact module files, authenticated WiFi plus
ADB/device NCM, ordinary sink/device role, no failed units/no kernel faults.
Battery71%,32.7C,Good. ADSPoffline/no native SoCinfo/no fastrpc is the expected
old state, not the planned candidate acceptance.

A first early exploratory ADB stdin method timed out; the registered shell
capture returned the same boot immediately. This host-input error was not
a CPU-wedge verdict. An unsupported host-runner `--match` CLI option also
exited before testing; the actual affected unittest discovery produced the
80-test result saved here. Neither error caused a device change.

No PPS request, pump activation, current change, runtime daemon start, desktop
start or device write has occurred at registration. One controlled candidate
boot follows only after this registration is committed and pushed.
