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

Windows Kernel-PnP Configuration events at 09:11:23 local time independently
record event 400 with `USB\\DEVICE_DESCRIPTOR_FAILURE` for
`USB\\VID_0000&PID_0002`, followed by event 411 with status `0x2B` (Code 43).
The raw event fields are preserved in `windows-pnp-events.json` (Windows
PowerShell's Chinese message text was not decoded cleanly by WSL). This
correlates with the earlier device-side transport closure, but does not
identify which side first aborted the descriptor exchange.

This establishes a failed enumeration/transport in one startup, not which
side of the USB connection caused it. The image's deferred `aux_bridge` probe
also appears in previously successful boots and is a separate missing PS5169
bridge provider. Do not change the USB gadget or SSH configuration from this
single sample. The registered production TWRP and warm-boot paths must each
verify Windows ADB and NCM/SSH; a failure requires same-boot diagnosis before
acceptance rather than an unobserved reboot retry.

Production test249 narrowed a second, distinct USB issue. Both production
boots enumerated Windows ADB promptly, with the Debian gadget bound to
`a600000.usb`, `usb0` carrier up and `sshd` listening. The TWRP-entry boot had
a successful Windows TCP check to `169.254.42.1:22`. On the ordinary warm boot,
Windows' first NCM TCP check at 09:49:05 failed despite the NCM adapter being
up with a preferred `169.254.219.80/16` address; the same check at 09:50:31
succeeded without reboot or configuration change, and the SSH protocol banner
was then read. The first failure and later success are retained separately in
`production-warm/windows-ncm-ssh*.txt`. Current Windows adapter/IP/neighbor
and Debian link/socket state are retained nearby. This is a transient NCM
connectivity failure, not a repeat of the Code43/ADB enumeration failure.
Neither root cause is proven by these observations; a future recurrence should
capture simultaneous host USB/network events and gadget-side packet traces
before changing the USB or Type-C configuration.
