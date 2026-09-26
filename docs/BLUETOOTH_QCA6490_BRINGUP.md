# QCA6490 / WCN6855 Bluetooth bring-up on the X710

State: **levels 0–6 pass, level 7 is fixed but its automatic path is unverified,
levels 8–13 are not reached.** Nothing was flashed for Bluetooth; the round's
changes are host tooling plus a userspace helper and a systemd unit.

This document keeps "the driver compiled", "the firmware loaded", "the controller
is usable" and "verified on hardware" as separate claims, in the layered order the
round's brief specifies. Every level below carries one of
`NOT_TESTED` / `FAILED` / `REACHED` / `PHYSICALLY_VERIFIED`.

## 1. Hardware identity

| item | value | how it is known |
|---|---|---|
| device | Samsung Galaxy Tab S9 Wi-Fi, SM-X710, `gts9wifi` | board name in the DTB |
| SoC | Qualcomm SM8550 (`kalama`) | `compatible` |
| WLAN/BT combo | **QCA6490 / WCN6855-class** | stock X710 downstream tree |
| **not** | WCN7850 / Kiwi v2 — that is the **X910** | `AGENT.md`; no X910 blob was used |
| Bluetooth transport | QUP **SE14** at `0x898000`, four-wire UART | `898000.serial` in the DTB, `qup_uart14_cts_rts` pinctrl |
| BT control pins | `BT_EN` GPIO81, `SWCTRL` GPIO82, `XO` GPIO204 | board DTS |
| supply topology | `wcn6855-pmu` → `pwrseq-qcom-wcn` → `bluetooth` target | `pwrseq.0` registered under `wcn6855-pmu` |
| driver stack | serdev → `hci_uart` → `hci_qca` + `btqca` | `serial0-0/driver -> hci_uart_qca` |

## 2. Level status

| level | what | status | evidence |
|---|---|---|---|
| 0 | config / modules | **PHYSICALLY_VERIFIED** | all four modules loaded, vermagic `7.2.0-rc3-gts9wifi-dirty` matches `uname -r` |
| 1 | uart14 / serdev bind | **PHYSICALLY_VERIFIED** | `serial0-0` bound to `hci_uart_qca`, modalias `of:NbluetoothT(null)Cqcom,wcn6855-bt` |
| 2 | WCN6855 pwrseq match | **PHYSICALLY_VERIFIED** | `wcn6855-pmu` → `pwrseq-qcom_wcn`, `pwrseq.0` registered, refcount 2 |
| 3 | BT_EN GPIO81 high | **PHYSICALLY_VERIFIED** | `gpio81 : out high func0 16mA no pull` |
| 4 | QCA ROM read | **PHYSICALLY_VERIFIED** | ROM `0x00000201`, SOC `0x400c1211`, patch `0x000038e6` |
| 5 | rampatch request/load | **PHYSICALLY_VERIFIED** | `qca/wcnhpbtfw21.tlv` downloaded, FW build `BTFW.HSP.2.1.0-00660-USB_UART_PATCHZ-6` |
| 6 | NVM request/load | **PHYSICALLY_VERIFIED** | `qca/wcnhpnv21g.bin` downloaded, `QCA setup on UART is completed` |
| 7 | hci0 usable | **REACHED**, automatic path unverified | manual: `UP RUNNING`, `BD Address: 38:8A:06:59:04:E7`; see §6 |
| 8 | BlueZ power on | **REACHED** | `bluetoothctl show` reports the controller, `Powered: yes` |
| 9 | scan | **REACHED** (with firmware + address) | `btmgmt find` discovers LE devices, incl. a named one |
| 10 | pair / connect | **NOT_TESTED** | needs a physical peer device |
| 11 | reboot reconnect | **NOT_TESTED** | blocked by the wedge in §8 |
| 12 | Wi-Fi + BT coexistence | **NOT_TESTED** | not yet attempted |
| 13 | cold boot | **NOT_TESTED** | the one attempt ended in the pre-existing CPU wedge |

## 3. The problem the round expected did not exist

The brief's first priority was to prove `hci_qca → pwrseq "bluetooth" → GPIO81`.
It was already working, and the preflight proved it in one read-only session:

```
 gpio80  : out high func0 16mA pull up        <- WLAN_EN
 gpio81  : out high func0 16mA no pull        <- BT_EN, driven by the sequencer
 gpio82  : in  high func0 2mA pull down       <- SWCTRL
 gpio204 : out low  func0 2mA pull down       <- XO
```

`hci_qca` finds the provider without `enable-gpios` in the DT, exactly as upstream
intends: no `enable-gpios` means `devm_pwrseq_get(&serdev->dev, "bluetooth")`
(`drivers/bluetooth/hci_qca.c:2454`), and the provider matches because
`vddaon-supply` resolves to a regulator whose grandparent is the `qcom,wcn6855-pmu`
node (`pwrseq_qcom_wcn_match_regulator()`). The strongest single proof that BT_EN
was high is that the controller **answered on UART** — a WCN6855 with BT_EN low
does not talk at all.

So the old note in `WIFI_QCA6490_BRINGUP.md` §8 ("BT_EN was low while hci_qca
retried") described a state that no longer holds, and this round did not have to
touch power sequencing, the PMU, the regulators or the DTS.

## 4. Level 5–6: the firmware, named by the chip rather than guessed

The driver derives the filename from the controller's own version word:

```
Bluetooth: hci0: QCA controller version 0x12110201
```

`scripts/lib/btfw-name.py` re-derives the names from the pinned source
(`drivers/bluetooth/btqca.h:51`, `btqca.c:795`, `btqca.c:842`, `btqca.c:934`) so
the mapping is checkable rather than asserted:

```
soc_ver = 0x12110201
rom_ver = ((soc_ver & 0xf00) >> 4) | (soc_ver & 0xf) = 0x21
variant = "g"   because (soc_id 0x400c1211 & 0xff00) == 0x1200   (GlobalFoundries)
    -> qca/wcnhpbtfw21.tlv   (fallback qca/hpbtfw21.tlv)
    -> qca/wcnhpnv21g.bin
```

That is exactly what the driver went on to request, which is the check that the
derivation is right.

**Rampatch and NVM are two separate problems, and were staged in two passes.**
The NVM's name depends on the board ID, which is only readable once the rampatch
is loaded, so staging it in advance would have been the guess the brief forbids.
`scripts/stage-bluetooth-firmware.sh` therefore fetches the rampatch pair first,
and the NVM afterwards with `--nvm <name the driver printed>`.

| file | sha256 | size |
|---|---|---|
| `wcnhpbtfw21.tlv` | `77d8979da5c613c85550549dcef8fb8ec6fe2e5576942855ea03179a11597c1f` | 152784 |
| `hpbtfw21.tlv` | `a911f66a137ec8b9e65f90942e1c21ea2604734a88e486519b77e750d0fc20d2` | 160124 |
| `wcnhpnv21g.bin` | `75229ef38873a51f711c2a38f3d6adcb80e8105e8e1d5e8570aea94b33441fe0` | 6450 |

All three from upstream **linux-firmware** (`.../firmware/linux-firmware/+/refs/heads/main/qca/`).
No forum, no fork, and Samsung's stock partition was not needed for these. The
blobs land under `out/`, which is gitignored; nothing proprietary is committed.

Result on a clean boot, with no `modprobe` and no manual step:

```
[    4.227639] Bluetooth: hci0: QCA Downloading qca/wcnhpbtfw21.tlv
[    4.923657] Bluetooth: hci0: QCA Downloading qca/wcnhpnv21g.bin
[    5.105865] Bluetooth: hci0: QCA FW build version: BTFW.HSP.2.1.0-00660-USB_UART_PATCHZ-6
[    5.106184] Bluetooth: hci0: QCA setup on UART is completed
```

## 5. The real blocker: the controller has no address of its own

With firmware loading, `hci0` came up **`DOWN RAW`**, `btmgmt info` said
`Index list with 0 items`, and `hciconfig` showed `ACL MTU: 0:0`. The cause is
upstream's generic NVM plus `btqca`'s placeholder check:

```
drivers/bluetooth/btqca.c:702   qca_check_bdaddr()
        if (!bacmp(&bda->bdaddr, &config->bdaddr))
                hci_set_quirk(hdev, HCI_QUIRK_USE_BDADDR_PROPERTY);
```

Parsing the staged NVM with the driver's own `struct tlv_type_nvm` layout shows
the tag holds the *same* placeholder the controller reports:

```
tag 2 BD_ADDR: ad5a00000000   ->  00:00:00:00:5A:AD    (`bdaddr_t` is byte-reversed)
controller reports                00:00:00:00:5A:AD
```

With the quirk set and no address supplied, `hci_sync` leaves the controller
unconfigured and closes it (`net/bluetooth/hci_sync.c:5501`), so only an
*unconfigured* index event is sent — which is why sysfs showed `hci0` while BlueZ
saw nothing.

Two consequences worth keeping:

* **This is why the ROM-only state looked healthier.** `qca_check_bdaddr()` is
  called at the *end* of `qca_uart_setup()` (`btqca.c:1013`), so with firmware
  missing the function returned early and the check never ran. Loading the correct
  firmware is what exposed the missing address.
* **The kernel cannot fix this from the DTS.** `local-bd-address` is a static
  property (`hci_dev_get_bd_addr_from_property()`, `hci_sync.c:3612`) and this
  address is unique per unit — provisioning data, not a board constant. A DTS
  value would be wrong for every tablet but one, and inventing one is exactly what
  the brief forbids.

### Where the real address is

Samsung's own file, on the X710, read read-only:

```
$ mount -t ext4 -o ro,noload /dev/disk/by-partlabel/efs /mnt/ro-efs
$ cat /mnt/ro-efs/bluetooth/bt_addr
38:8A:06:59:04:E7
$ sha256sum /mnt/ro-efs/bluetooth/bt_addr
a3e01a6deb0aa2a89b3e18f50637fbeb71bd94ddac823add9cdb3c677049125a
```

17 bytes of ASCII. `38:8A:06` is a **Samsung Electronics** OUI (IEEE registry), so
this is the unit's assigned address and not a Qualcomm default. The partition was
unmounted immediately and nothing was written to it.

The `btd` partition (2 MiB) was inspected too and holds only an `SM-X710`/`CUSTOM`
metadata trailer — no address. `param` is empty apart from an `SHDN` marker.

## 6. The fix, and exactly how far it is verified

`rootfs-overlay/usr/libexec/gts9-bluetooth-address` reads the address from
`/efs/bluetooth/bt_addr` through a `ro,noload` mount and hands it to the standard
BlueZ management interface (`btmgmt public-addr`). A systemd unit runs it, and a
drop-in makes `bluetoothd` wait for it.

This is the interface's designed path, not a workaround: because the controller
comes up unconfigured, `btmgmt` itself advertises `public-address` as a supported
option, and setting it is what transitions the controller to configured.

**Verified by running the helper on the tablet**, against a controller reset to the
broken state:

```
before: Index list with 0 items
gts9-bt-addr: set public address 38:8A:06:59:04:E7 (from /run/gts9-bt-efs/bluetooth/bt_addr)
GTS9_DEBIAN_STAGE=bluetooth-address-set

$ hciconfig hci0
hci0:	BD Address: 38:8A:06:59:04:E7  ACL MTU: 1024:7  SCO MTU: 240:4
	UP RUNNING

$ btmgmt find
hci0 dev_found: ED:68:88:8E:60:2A type LE Public rssi -111 flags 0x0000 name DEPRTS888E
```

Also exercised: the already-configured path and the missing-partition path, both of
which exit 0 and record a distinct stage. `efs` is left unmounted and the mountpoint
removed in every path.

**NOT verified: the automatic boot path.** The reboot intended to test it ended in
the CPU wedge described in §8, so the unit has not been observed applying the
address on a clean boot. That is the single most important outstanding item, and it
is a wiring question, not a controller question.

### Two bugs in the first version, found only by testing on the tablet

Both are recorded in the helper because neither is obvious from reading it:

1. `ConditionPathExists=/sys/class/bluetooth/hci0` in the unit made systemd **skip
   the unit outright** on a cold boot — the condition is evaluated once, and
   `hci_qca` registers `hci0` from the DT serdev a few seconds later. The helper now
   waits for `hci0` itself, which is bounded and cannot race.
2. `btmgmt ... </dev/null` **hangs**, and `/dev/null` is precisely what systemd
   gives a unit on stdin; the unit had to be killed by `TimeoutStartSec`. Feeding
   stdin from a pipe works and returns in milliseconds. Every `btmgmt` call is now
   both piped and wrapped in `timeout`.

`btmgmt info` additionally blocks when it runs before `bluetoothd` has opened the
management socket, which is the cold-boot case, so the address is set first and the
probe afterwards is best-effort.

## 7. BD_ADDR provenance

| question | answer |
|---|---|
| is it the real Samsung address? | **yes** — from `/efs/bluetooth/bt_addr`, Samsung OUI `38:8A:06` |
| is it random or generated? | **no** — read from the device, validated as six hex pairs, never invented |
| all-zero or Qualcomm default? | **no** — all-zero is explicitly refused by the helper |
| is it in firmware? | **no** — the upstream NVM carries the `00:00:00:00:5A:AD` placeholder |
| written anywhere? | **no** — the partition is mounted `ro,noload` and unmounted; nothing is written back |

## 8. The CPU wedge that interrupted the round

The cold-boot test rebooted the tablet into the repository's **pre-existing CPU
wedge**, not a Bluetooth failure:

```
rcu: rcu_preempt kthread starved for 2498 jiffies! g869 f0x0 RCU_GP_DOING_FQS(6) ->state=0x0 ->cpu=7
```

It matches `docs/CPU_WEDGE_EVIDENCE.md:113` structurally, matches a wedge archived
earlier the same day *before this round began* (`test-213-production-initramfs/`,
committed 14:52), stalls the CPUs that document already names (4 and 5), and — the
decisive point — **no kernel code was changed or flashed this round**:

```
$ git diff --exit-code 24dd156 HEAD -- kernel/ boot/     # no output
```

`kernel/` and `boot/` are byte-identical to the RTC-verified state of test 216.
Attribution is therefore recorded as *"a wedge coincident with Bluetooth work"*,
per the brief, and not as "Bluetooth caused a wedge". The documented post-fix base
rate is 1 in 29 boots (3.4%), so one wedge across a handful of test boots is within
expectation. A true A/B (same workload with and without the helper, enough boots to
separate 3.4%) has not been run, so the possibility that Bluetooth contributes is
**not** excluded — only unsupported. Details: `test-219-cpu-wedge-during-bt/`.

## 9. What must not regress — and has not

Nothing in this round touches Wi-Fi, and the checks below were taken from the
running tablet after the firmware install and after the address fix:

| check | result |
|---|---|
| `qca/` firmware added | new files only; `ath11k/WCN6855/hw2.1/` untouched |
| ath11k / WLAN firmware | **not modified** — the same `fw_build_id WLAN.HSP.1.1-04866.5-...-IOE-1` |
| patch 0008 / AOP PDC votes | **not touched** |
| PCIe PIPE mux fix | **not touched** |
| WLAN_EN GPIO80 | unchanged, `out high` |
| `wlp1s0` | associated with a DHCP lease after the firmware install |
| DTS | **byte-identical** — `kernel/` is unchanged this round |
| RTC offset scheme | **not touched** |
| production initramfs | **not touched** |
| USB serial console | **not re-added** |
| `/persist`, `/efs`, `btd`, `param` | read-only mounts only; nothing written |

The shared-PMU question the brief raises (§25) is still open in one specific
respect: `btmgmt power off` / `power on` cycling has not been tested, so whether the
upstream pwrseq lifecycle can drop the WLAN rail when Bluetooth is turned off is
**NOT_TESTED**, not "fine".

## 10. Reproducing

```sh
scripts/bluetooth-preflight.sh                 # read-only; prints every level
scripts/stage-bluetooth-firmware.sh --fetch    # rampatch pair from upstream
scripts/stage-bluetooth-firmware.sh --install
scripts/lib/btfw-name.py --dmesg <saved trace> # re-derive the names

# after the rampatch loads, the driver prints the NVM it wants; stage exactly that
scripts/stage-bluetooth-firmware.sh --nvm wcnhpnv21g.bin
scripts/stage-bluetooth-firmware.sh --install
```

`--install` re-hashes every file on the tablet after copying and fails on a
mismatch.

## 11. Risks and unknowns

1. **The automatic address path is unverified** (§6). Highest priority.
2. **Pairing, reconnect, coexistence and cold boot are untested** — levels 10–13.
   No physical peer device has been attached.
3. **The NVM is upstream's generic one.** It boots the controller and scan works,
   but board-specific RF calibration has not been compared against Samsung's own
   NVM, which has not been located. `btmgmt info` reports the real address and the
   expected manufacturer/version, so the obvious failure modes are absent, but
   "generic NVM is equivalent" is **not** established.
4. **`public-addr` is stored where?** The controller keeps the address for the life
   of the power-on only; the helper re-applies it every boot from `efs`. If Samsung's
   own NVM (which would carry the address) is ever found, that would be the cleaner
   source, and this helper would become unnecessary.
5. **Reading `efs` at boot** is a new read of an Android partition by mainline. It is
   `ro,noload` and never written, but it is a new dependency on that partition
   existing and being ext4.
6. **`SWCTRL` (GPIO82) is described but never driven.** It is `in high` and nothing
   in the upstream pwrseq provider handles a swctrl line for WCN6855; the controller
   works regardless, so this is recorded as unexplained rather than fixed.
7. **The CPU wedge** (§8) remains an independent, unresolved project issue. It can
   interrupt any physical test round, including this one.
