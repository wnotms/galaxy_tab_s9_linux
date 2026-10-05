# Owner-confirmed USB reconnect: access unavailable

Owner replied “已重连”. One bounded native ADB device-list query completed but
listed no devices. The targeted Windows present-device query completed with no
matching production/Android/descriptor-failure device. A separate expanded USB /
host-address query hit its 20-second host timeout; it produced no output. This
failed query is preserved, and Windows Code43 is **unknown**, not excluded.

A single authenticated Wi-Fi attempt to the last known 10.139.153.84 address
failed with “No route to host” before authentication. No current boot ID, current
identity, kernel journal, battery state or device-side USB state could be obtained.
An empty device list does not prove CPU stall, a driver fault, or a successful
physical cycle. Cable-disconnect/reconnect timing was not observed by the agent.

The separately retained 11:31:52Z snapshot is a **prior** observation, not current:
accepted311 boot 5e039c8f, lpcharge=1, battery 0%, 3.213V, net −351mA, 30.5°C on
PC SDP500mA. It does not explain today's access loss or establish shutdown cause.
Owner has been asked for current screen/power state, Wi-Fi address and whether a
manual reboot occurred. No reboot, flash, driver/service reset, partition/module
write, charging-policy change, ADC request, PPS request or pump activation sent.

Verdict: **ACCESS_UNAVAILABLE_STOP**. Physical testing cannot continue without
access and current entry-state evidence. Host tests/build executed:false; no
GitHub Actions. Raw host outputs/errors/commands/timeouts retained without replay.
