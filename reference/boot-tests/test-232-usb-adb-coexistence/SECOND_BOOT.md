# Second boot: USB and network channels operational

Boot 79135c6d-ed39-4e11-b2cc-96e7ee8c027a used the endpoint-holder revision
2233403 (deployed file hashes in deploy-v2/readback.txt). Native USB adb shell,
TCP ADB and Windows OpenSSH authenticated successfully to this same boot.
No failed systemd units were reported. Holder PID 803 retained fd 3 on ep0;
FunctionFS mount ID 94 matched the prepared mount. NCM remained usb0 at
169.254.42.1/16, with port 22 and 5555 listeners.

A 1 MiB binary payload completed native USB push/pull and exact byte/hash
comparison while a single SSH session continuously emitted heartbeats.
The later daemon-stop continuity check and final reboot are reported in
RESULTS.md when complete. This boot does not explain the preceding stall.
