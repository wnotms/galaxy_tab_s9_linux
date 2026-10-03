# Test307 — critically low battery / ordinary charge state incident

**STOP. Read-only evidence captured; no candidate deployment or active charge.**

One bounded SSH lookup of the previous address returned `No route to host`.
Windows ADB still showed `gts9wifi-0001 device`. Current boot is
fd198d7c3c8940a591724a2f50ea0a34, Wi-Fi10.139.153.16. No reboot was issued by
this work; why the boot changed from57535... is not established. Notes/config
match retained Test299, but the new cmdline contains `lpcharge=1` and does not
match the normal Test306 registration. No full partition/module hashing was
spent on this unsafe battery state; baseline acceptance is not claimed.

Actual gauge observation:0%,2.775V, about+6mA,31.5°C, Good health but
`Not charging`; USB online/SDP, reported input limit1800mA. Real pack thermal
zone remained enabled. Full same-boot kernel JSON has1109 rows and no matched
CPU/panic/RCU/CSD/lockup signature. This is a bounded signature scan, not a
stability acceptance or proof that every hardware fault is absent.

The kernel logged500mA input/battery configuration at1.520775s and1.979544s.
Documented stable-register reads found Q4OFF, input1800mA, fast code0x97,
float4200mV; see summary/raw. Operation mode5 remains ordinary switching.
Watchdog was disabled at the later read (WDTCNTL04); prior state/reset cause
is unknown. Register state contradicts the initial configuration logs, but
does not prove which hardware/firmware action changed it.

Eight atomic register-pointer/read transactions were performed after matching
the actual supply device, bound driver and OF compatible. No register-data
write, INT-latch read, unbind/reset/force-mode operation, current raise, PPS,
pump activation, rootfs change, partition/module replacement or reboot occurred.
Initial capture incorrectly equated I2C device name with driver name and
asserted before any bus access. That error/raw script is preserved; corrected
capture uses the actual binding and compatible. It is not a failed hardware
experiment and did not trigger a replay of ADC/PPS/pump activity.

Ordinary charging recovery via the previously accepted18W USB-C2 source was
requested; owner confirmation remains pending. Further device polling was
stopped. Do not flash Test306 or enable active charging at this voltage.

The source-level gap is missing verification of the programmed ordinary charge
state while the cable remains attached. Plan in
`docs/SM5714_PROGRAM_STATE_RECOVERY.md` adds a bounded, source/sensor/fault-gated
reapplication of existing values, never wholesale vendor init, watchdog clear,
raised limits or repeated NOT_CHARGING retries. Implementation/build/hardware
acceptance are **not yet complete**. Test306 remains unexecuted and must not
bypass its original source/normal-cmdline/battery gates.

This evidence/plan change runs no new kernel build or full host regression:
`executed: false`. Raw/derived identities and hashes were checked locally;
reuse Test305/Test306 qualification only for their exact unchanged code/artifacts.
Full wired charging port goal is active; full Stage3 NOT READY.
