# USB runtime recovery — ADB and NCM restored, root cause open

One registered runtime UDC unbind/rebind on the exact existing Test331 boot
restored Windows composite/ADB/NCM enumeration, all ProblemCode 0. ADB shell
returned the original machine and boot ID. The NCM interface is Up and a socket
bound to interface12/source169.254.174.241 received the Debian SSH banner from
169.254.42.1:22. Wi-Fi SSH and GDM remained active. No reboot or candidate flash.

Before recovery, UDC retained configured/super-speed-plus while Windows had no
present tablet. After recovery it enumerated configured/high-speed. VID/PID,
ffs.adb+ncm.usb0, configuration links and service files were unchanged. Existing
adbd PID856 handled UNBIND/rebind without replacement. No kernel, firmware,
module, partition, charging policy, PPS request or pump activation change.
This proves one successful recovery, not a permanent fix or a Test366 retry.
Root cause remains open; DWC3, host suspend, Type-C transition and physical-link
causes are not yet distinguished. Owner now requests a persistent USB fix.

Host import failure occurred before any device command and is preserved. The
full Windows property probe timed out; completed CIM and later enumeration are
the actual host proof. Result assembly initially failed reading GB18030 as UTF-8;
raw evidence stayed unchanged and the corrected decoder verified ASCII status
fields. Neither host failure triggered another device rebind.

Final battery snapshot:99%,29.1°C,Good,VBAT ADC4.446V. This exceeds the old
sensor candidate's strict <4.44V gate, so no new candidate/charging acceptance was
attempted and these readings are not a charging PASS. Owner has unplugged for
natural discharge; no stress load. Native Escape driver remains compiled, not
deployed; interim XKB and GNOME remain intact. SSC/rotation/full port incomplete.

Complete original kernel/unit evidence is retained. The same two original GMU
suspect pairs persist, without additional GMU messages in the later1272-row
capture. Post-rebind errors use source monotonic time, not wall-clock --since,
because this boot contains time jumps. No host suites/build/Actions executed for
results; executed:false. Persistent reconnect fix needs independent code/test
qualification and registration before deployment.
