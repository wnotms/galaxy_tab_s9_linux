# Test 232: USB ADB and existing SSH coexistence verified

Final state: Debian boot **a80804be-229c-46f7-aae8-bd797fb22883**, native USB ADB,
TCP ADB and SSH responsive. The final continuous SSH observation ended at
178.98 seconds, with no failed systemd units or detected CPU non-response
signature in the captured journal. Native USB and TCP shells were checked again
afterward. No further reboot was issued. This is a bounded observation, not a
resolution of the earlier CPU/pstore problems.

## Verified behavior

* Windows automatically enumerated Android Composite ADB Interface at MI_02
  and the existing NCM adapter at MI_00, ifIndex 10. No host driver was installed.
* NCM address remains 169.254.42.1/16. NCM config, SSH config and authorized_keys
  hashes match before/after deployment. Production kernel/boot partitions were
  not changed during this trial; only the nine recorded userspace files changed.
* A 1 MiB payload completed native USB push/pull with exact byte/hash equality.
* During boot 79135c6d-ed39-4e11-b2cc-96e7ee8c027a, one SSH connection emitted
  all 100 heartbeats and exited zero. Observed uptime interval 51.03–249.70 s,
  maximum gap 2.01 s. Stopping adbd at 134.75 s did not interrupt that session,
  unbind the controller or remove NCM. A restart request was safely skipped by
  ExecCondition. The planned 150-second observation was completed after stopping
  adbd, rather than before the stop; the exact timings are retained.
* The final startup fixed the discovered bind race: ep0 opened at 5.632238 s,
  FUNCTIONFS_BIND arrived at 5.743727 s (about 0.1115 s). All three transports
  answered with the same final boot ID. No bind timeout occurred in this log.

## Implementation and limits

NCM is configured before adbd starts. FunctionFS uses no_disconnect=1, with
mount-ID provenance. An independent idle process holds ep0 because Debian adbd
can reopen it internally after a transport error; losing the last reference
would otherwise reset the shared gadget. Readiness polling is bounded to five
seconds at 50 ms intervals. Missing prerequisites/timeouts/bind failure retain
the NCM-only path. Already-bound gadgets are not rebuilt to add ADB.

The service guard prevents restarting adbd while the shared ADB function is
bound. After daemon/USB transport failure, native USB ADB can require a normal
reboot to recover; preserving SSH takes priority over USB ADB auto-reconnect.
Do not bypass the guard or unmount FunctionFS to recover ADB on a live SSH link.
This shares one controller and cannot provide independence from a kernel/USB
controller failure. USB unplug/replug endurance was not tested.

## Failed attempts retained

FIRST_BOOT.md records an unresponsive log-screen boot whose retained journal
ends at about seven seconds. Enumeration alone did not prove shell usability;
no positive CPU failure signature survived, so its cause remains unattributed.
STARTUP_RACE.md records a subsequent healthy network boot where adbd's one-second
bind deadline expired. The corrected preparation/polling order was then deployed
without unbinding the live gadget and verified on the final normal boot.

## Validation and usage

26 focused USB tests passed in 3.325 s; 74 related tests passed in 1.161 s.
Mocking irrelevant host sync/NIC waits reduced the USB fixture suite from
27.452 s to 3.325 s without deleting tests or changing device waits. Individual
shell syntax, the ccache production build and on-device systemd unit verification
passed. The build was not flashed. No full 900-plus-test regression was needed.

```sh
adb -s gts9wifi-0001 shell
ssh root@169.254.42.1
adb connect 169.254.42.1:5555
```

The USB serial selector matters when USB and TCP ADB are both connected.
Set /etc/gts9-usb-adb to 0 for NCM-only on the next normal boot. Source revision
53c144a is the final device implementation; fe108d8 optimizes host fixtures only.
