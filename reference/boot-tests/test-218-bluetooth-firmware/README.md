# Test 218 — the WCN6855 Bluetooth firmware, and why hci0 then went RAW

Source: an SSH session on the running tablet, boot `136df623`, 2026-09-26.
Nothing was flashed. Two files were installed into `/usr/lib/firmware/qca/`,
which is rootfs content, not a partition.

## What was already working (from test 217)

Levels 0–4 passed before this test, so the round's expected problem — "does
`hci_qca` reach BT_EN?" — did not exist:

```
gpio81 : out high func0 16mA no pull      <- BT_EN driven high by the sequencer
Bluetooth: hci0: setting up wcn6855
Bluetooth: hci0: QCA ROM Version  :0x00000201
```

`serial0-0` is bound to `hci_uart_qca`, `wcn6855-pmu` is bound to
`pwrseq-qcom_wcn`, and `pwrseq.0` is registered. The ROM answered, which is only
possible with BT_EN high. The failure was level 5: no firmware file existed.

## The files the driver asked for, and where they came from

`btqca` derives the name from the controller's own version word, so nothing was
guessed. `scripts/lib/btfw-name.py` re-derives it from the pinned source:

```
soc_ver = 0x12110201
rom_ver = ((soc_ver & 0xf00) >> 4) | (soc_ver & 0xf) = 0x21
variant = "g"   because (soc_id 0x400c1211 & 0xff00) == 0x1200  (GlobalFoundries)
```

| file | sha256 | size |
|---|---|---|
| `wcnhpbtfw21.tlv` | `77d8979da5c613c85550549dcef8fb8ec6fe2e5576942855ea03179a11597c1f` | 152784 |
| `hpbtfw21.tlv` | `a911f66a137ec8b9e65f90942e1c21ea2604734a88e486519b77e750d0fc20d2` | 160124 |
| `wcnhpnv21g.bin` | `75229ef38873a51f711c2a38f3d6adcb80e8105e8e1d5e8570aea94b33441fe0` | 6450 |

All three from upstream `linux-firmware` at
`.../kernel/git/firmware/linux-firmware/+/refs/heads/main/qca/`. The NVM was
staged in a **second pass**, after the rampatch was loaded and the driver printed
the name it actually wanted:

```
Bluetooth: hci0: QCA Downloading qca/wcnhpbtfw21.tlv
Bluetooth: hci0: QCA Downloading qca/wcnhpnv21g.bin
```

## Result: levels 5 and 6 pass

```
Bluetooth: hci0: QCA FW build version: BTFW.HSP.2.1.0-00660-USB_UART_PATCHZ-6
Bluetooth: hci0: QCA setup on UART is completed
```

Clean boot, no manual `modprobe`: the patch downloads at 4.2 s and the NVM at
5.1 s.

## …but hci0 came up RAW, and that is the real remaining failure

```
hci0:	BD Address: 00:00:00:00:5A:AD  ACL MTU: 0:0  SCO MTU: 0:0
	DOWN RAW
```

`btmgmt info` reported `Index list with 0 items`, although `hci0` existed in
sysfs and `bluetoothd` had initialised MGMT 1.23.

### Cause, from the driver's own logic

Three facts line up:

1. `btqca.c:1013` calls `qca_check_bdaddr()` at the very end of `qca_uart_setup()`
   — i.e. **only once firmware has loaded**. This is why the ROM-only state
   earlier looked healthier: the firmware load returned `-2` and the function
   returned before the check.
2. `qca_check_bdaddr()` reads the controller's address and, if it **equals** the
   address in the NVM's `EDL_TAG_ID_BD_ADDR` tag, sets
   `HCI_QUIRK_USE_BDADDR_PROPERTY`. Parsing the staged NVM with the driver's own
   `struct tlv_type_nvm` layout (12-byte header) gives exactly that:

   ```
   tag 2 BD_ADDR: ad5a00000000   -> 00:00:00:00:5A:AD   (bdaddr_t is byte-reversed)
   controller reports               00:00:00:00:5A:AD
   ```

   The upstream NVM carries a placeholder, not this unit's address.
3. With that quirk set and no address supplied, `hci_sync` marks the controller
   `HCI_UNCONFIGURED` and closes it, so only an *unconfigured* index event is
   sent — which is why `btmgmt info` lists nothing while sysfs shows `hci0`.

So the upstream NVM is genuinely generic, and the per-unit address has to come
from the device.

## Where this unit's real address is

`/efs/bluetooth/bt_addr` — Samsung's own provisioning file, found on the X710 and
read only:

```
$ mount -t ext4 -o ro,noload /dev/disk/by-partlabel/efs /mnt/ro-efs
$ cat /mnt/ro-efs/bluetooth/bt_addr
38:8A:06:59:04:E7
$ sha256sum ...
a3e01a6deb0aa2a89b3e18f50637fbeb71bd94ddac823add9cdb3c677049125a
```

17 bytes of ASCII, `XX:XX:XX:XX:XX:XX` plus no trailing newline. `38:8A:06` is a
Samsung Electronics OUI (checked against the IEEE registry). The efs partition
was unmounted again immediately; nothing was written.

The `btd` partition (2 MiB) was also inspected and holds only a metadata trailer
(`SM-X710`, `CUSTOM`) — no address.

## Proof the diagnosis is right

Setting that address through the standard BlueZ management interface makes the
controller work, with the real address and the loaded patch:

```
$ btmgmt public-addr 38:8A:06:59:04:E7
hci0 Set Public Address complete, options:

$ hciconfig hci0
hci0:	BD Address: 38:8A:06:59:04:E7  ACL MTU: 1024:7  SCO MTU: 240:4
	UP RUNNING

$ btmgmt find
hci0 dev_found: ED:68:88:8E:60:2A type LE Public rssi -111 flags 0x0000 name DEPRTS888E
hci0 dev_found: 00:A4:1C:37:72:C3 type LE Public rssi -93 flags 0x0004
```

The address is the device's own, not a generated one; `btmgmt` advertises
`public-address` as a supported option precisely because the controller came up
unconfigured, so this is the interface's designed path rather than a workaround.

## Files

| file | what |
|---|---|
| `firmware-result.txt` | the QCA trace and the controller state across three loads |
| `state.txt` | the failing `DOWN RAW` state and the absent DT property |
