# Intermittent USB enumeration failure before production rollout

The tablet displayed a Debian login on diagnostic DCC-disabled boot
`3527c008-4415-43db-bdcb-b55e8adc31ee`, but Windows showed **Unknown USB
Device (Device Descriptor Request Failed), Code 43**. `adb devices` was empty.
The owner's normal reboot produced boot
`b78d646f-c0c5-4c71-9c4c-17ca7d037260`; Windows and ADB then enumerated
the same USB cable/port without a configuration change.

The prior boot journal shows FunctionFS prepared at 5.002 s, gadget bound to
`a600000.usb` at 5.707 s, and `FUNCTIONFS_ENABLE` at 7.120 s. At 8.933 s,
adbd reported a transport read returning zero and `Cannot send after transport
endpoint shutdown`. It did not log another enable before the owner rebooted at
892 s. The new boot bound the gadget at 5.415 s, enabled FunctionFS at 5.809 s,
and retained ADB/NCM. Its current `a600000.usb` UDC state is `configured` and
both `ffs.adb` and `ncm.usb0` are linked. Neither boot's journal contains a
CPU lockup/panic marker. The preceding boot's persistent journal survives and
is saved in `prior-all.jsonl`; the new boot is in `current-all.jsonl`.

This establishes a failed enumeration/transport in one startup, not which
side of the USB connection caused it. The image's deferred `aux_bridge` probe
also appears in previously successful boots and is a separate missing PS5169
bridge provider. Do not change the USB gadget or SSH configuration from this
single sample. The registered production TWRP and warm-boot paths must each
verify Windows ADB and NCM/SSH; any recurrence stops rollout for host/device
trace collection rather than an unobserved retry.
