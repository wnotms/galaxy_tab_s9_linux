# Test plan: X710 Bluetooth, levels 8–13

**Status: NOT RUN.** Written before the tests, so the evidence cannot be selected
after the fact. Levels 0–7 are already covered by
`reference/boot-tests/test-217-bluetooth-preflight/` and `test-218-bluetooth-firmware/`;
this file covers what those could not reach.

Everything here needs the tablet powered on and reachable. The last attempt ended
in the repository's pre-existing CPU wedge (`test-219-cpu-wedge-during-bt/`), so
the first step is a physical power cycle by the owner.

## Preconditions

| requirement | why |
|---|---|
| tablet powered on and reachable over USB NCM (`scripts/gts9-ssh.sh`) | every step below is remote |
| the current `init_boot` flashed, with the two `qca/` files installed | levels 5–6 only pass with firmware present |
| a Bluetooth mouse or keyboard available | §20: prefer HID over audio, so an audio-stack problem cannot be mistaken for a controller problem |
| a Wi-Fi AP to associate with | needed for the coexistence cases |
| owner present for the power cycle | the wedge cannot be cleared remotely |

Before starting, confirm the baseline is the expected one:

```sh
scripts/bluetooth-preflight.sh          # expect levels 0-6 to report as passing
ls -l /lib/firmware/qca/                # wcnhpbtfw21.tlv, hpbtfw21.tlv, wcnhpnv21g.bin
```

## Test 1 — the unit applies the address automatically on a cold boot

**The single most important outstanding item: it is fixed but unverified.**

A reboot is not enough evidence on its own, because the address would also be
applied if someone ran the helper by hand. So:

1. power cycle the tablet (full `poweroff`, then power on — not `reboot`);
2. do not log in, do not run anything manually;
3. then read:

   ```sh
   systemctl status gts9-bluetooth-address.service
   journalctl -u gts9-bluetooth-address.service -b
   hciconfig hci0
   ```

**Pass:** the unit is `active (exited)`, its log contains
`set public address 38:8A:06:59:04:E7`, and `hciconfig` shows
`BD Address: 38:8A:06:59:04:E7` with `UP RUNNING` and `ACL MTU: 1024:7`.

**Fail:** the unit is `inactive` with an unmet condition (the cold-boot trap that
was already fixed once), or `Result: timeout` (the `btmgmt` stdin trap), or the
address is still `00:00:00:00:5A:AD`.

Save as `test-NNN-bluetooth-coldboot/unit-status.txt`.

## Test 2 — the unit must not fight an already-configured controller

```sh
systemctl restart gts9-bluetooth-address.service
journalctl -u gts9-bluetooth-address.service -n 5
```

**Pass:** it logs either `set public address ...` again or
`controller already configured; leaving it alone`, exits 0, and `hci0` stays
`UP RUNNING` throughout — the controller must not be reset or dropped.

## Test 3 — Bluetooth power cycling must not disturb Wi-Fi

The brief's §25. The two share `wcn6855-pmu`, the regulators and XO, but have
separate enables, so turning Bluetooth off must not take the WLAN rail with it.

```sh
ip -br addr show wlp1s0            # note the state
ping -c 3 <gateway>
bluetoothctl power off
sleep 3
ip -br addr show wlp1s0            # must be unchanged
ping -c 3 <gateway>                # must still work
ls /sys/bus/pci/devices/0000:01:00.0   # the endpoint must still exist
bluetoothctl power on
sleep 3
hciconfig hci0                     # must be UP RUNNING again
```

**Pass:** `wlp1s0` never drops, ping is uninterrupted, the PCI endpoint never
disappears, and `hci0` returns after `power on`.

**Fail:** any of the above changes. Per the brief, do **not** add a userspace
workaround — record it and investigate the pwrseq dependency/refcount lifecycle.

## Test 4 — scan (level 9, and the first test at this level with firmware)

At least one LE device and one BR/EDR device should be in range.

```sh
btmgmt find            # both LE and BR/EDR; run for 30 s
```

**Pass:** at least one device is discovered, and the output is recorded.

Record explicitly whether only BLE was available — the brief requires the test
conditions to be stated when that is the case.

## Test 5 — pairing and reconnect (levels 10–11)

Use a mouse or keyboard. Pairing keys and device addresses of the owner's
personal hardware must **not** be committed.

```sh
bluetoothctl
  power on
  agent on
  default-agent
  scan on
  pair   <ADDR>
  trust  <ADDR>
  connect <ADDR>
  # verify input actually works, if it is a HID device
  disconnect <ADDR>
  connect    <ADDR>      # manual reconnect
  quit
```

**Pass:** the device binds, input works, and it reconnects after an explicit
`disconnect`.

Then, for level 11:

```sh
systemctl reboot
# after boot, with no manual step:
bluetoothctl info <ADDR>
```

**Pass:** the pairing is remembered and the device reconnects (or connects on
demand) without re-pairing.

**Not a failure:** no audio from an A2DP device. The audio stack is a separate
work item in this project and must not be reported as a Bluetooth controller
problem.

## Test 6 — coexistence under load (level 12)

Three cases, in order:

| case | setup | pass |
|---|---|---|
| A | Wi-Fi connected, Bluetooth off | association holds, ping and an HTTP fetch work |
| B | Wi-Fi connected, `btmgmt find` running | association stays up, ping works during the scan |
| C | Bluetooth HID connected **and** an HTTP transfer running | no `ath11k` reset, no MHI RDDM, no controller reset |

```sh
dmesg | grep -iE "ath11k|mhi|RDDM|firmware crash|hci0.*reset"
```

**Pass:** nothing in that grep during any of the three cases.

This round does **not** measure throughput; it only confirms the two do not break
each other.

## Test 7 — cold boot after the whole sequence (level 13)

The Wi-Fi work already showed warm and cold handoffs differ, so a `modprobe`-only
test is not enough.

1. full `poweroff`, wait for the rail to drop, power on;
2. do not touch anything;
3. check `BT_EN`, the ROM read, the firmware load, `hci0` and BlueZ:

   ```sh
   grep -E "gpio(80|81) " /sys/kernel/debug/gpio
   dmesg | grep -E "QCA ROM Version|QCA FW build version|setup on UART"
   hciconfig hci0
   bluetoothctl show | head -3
   ```

**Pass:** all five recover with no manual step.

**If warm works and cold fails:** do **not** hide it with a sleep or a retry loop.
Re-examine the AOP PDC votes, the PMU sequence, XO_CLK, BT_EN and regulator state,
as the brief requires.

## Evidence layout

```text
reference/boot-tests/test-NNN-bluetooth-*/
  README.md
  unit-status.txt          test 1
  idempotency.txt          test 2
  coexistence-power.txt    test 3
  scan.txt                 test 4
  pairing.txt              test 5      (no personal addresses or keys)
  reconnect.txt            test 5
  coexistence-load.txt     test 6
  coldboot.txt             test 7
```

## The rule this plan exists to enforce

A working `btmgmt find` is **not** "Bluetooth works". The levels above are
sequential for a reason: pairing on top of an unverified automatic address path
would produce a result that cannot be attributed. Test 1 first.
