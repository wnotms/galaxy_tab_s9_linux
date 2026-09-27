# Test 232: native USB ADB alongside existing NCM/SSH

Owner request: “adbd能否直接使用usb连接，类似安卓手机” and
“能否不影响当前ssh的前提下加入”; owner then confirmed “已进入 TWRP”.
Prior physical-test/reboot authorization remains active. This is a userspace
transport test, not a wedge series or a pstore/ECC experiment.

Start state: test-231 production hashes restored; subsequent CPU5 wedge was
captured and owner recovered to TWRP. No boot partition writes planned here.

Deploy only the seven changed USB config/unit/helper files from the reproducible
overlay tar, after backing up the existing files. Preserve NCM config, SSH
keys/config, VID/PID/serial and NCM interface ordering. Keep packaged adbd.service
masked. New FunctionFS mount uses no_disconnect=1. Mount/daemon/readiness/bind
failure must leave NCM available. Never unbind a live gadget to add ADB.

After a normal reboot, check native USB enumeration, native adb shell, NCM
address, SSH authentication and TCP ADB. Observe at least 150 seconds and save
boot identity/journal. If healthy, keep one SSH session streaming heartbeats
while stopping adbd once and verifying that its restart is safely deferred;
compare gadget binding and network state. Reboot normally once afterward to
restore native USB ADB. The guard is needed because reopening ep0 after close
would reset the gadget despite no_disconnect.
No disconnect/reboot/panic is induced. Any CPU wedge stops the test and is
archived separately; a USB endpoint does not fix an unresponsive CPU.

No driver installation or kernel image change is part of this trial. If Windows
does not bind native ADB, preserve NCM and record the enumeration limitation.
