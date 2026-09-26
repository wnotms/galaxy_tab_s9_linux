# test-212: the tty1 AF_VSOCK warning is gone, and TCP SSH is unaffected

Boot `65958aa0-bc46-4e99-9337-37cdad52020f`. Raw evidence in `EVIDENCE.txt`; the
controlled A/B measurement of the generator itself is in `AB-CONTROL.txt`.

## The symptom, and where it was

The owner's screenshot showed this on the panel, between the tty1 login prompt
lines:

```
systemd-ssh-generator:
Failed to query local AF_VSOCK CID:
Cannot assign requested address
```

## Root cause: the device tree says "VM", and the generator believes it

The full chain, verified against systemd v257's sources and measured on this
board rather than inferred from the message:

| step | evidence |
|---|---|
| `systemd-detect-virt` reports a VM | `vm-other` (and `--vm` = `vm-other`, `--container` = `none`) |
| because the DT has a hypervisor node | `/proc/device-tree/hypervisor/compatible` = `qcom,gunyah-hypervisor-1.0` |
| `detect_vm_device_tree()` maps any unknown string to `VIRTUALIZATION_VM_OTHER` | `src/basic/virt.c` |
| `systemd-ssh-generator` takes the VM path by default (`arg_auto = true`) | `src/ssh-generator/ssh-generator.c` |
| `VIRTUALIZATION_IS_VM()` is therefore true, so it calls `vsock_get_local_cid()` | same |
| the CID ioctl fails, so it logs and exits 1 | `ioctl` → `ENOTTY`; measured with a 6-line python probe |

**`/dev/vsock` existing is why the "device absent" escape does not apply.**
`CONFIG_VSOCKETS=y` comes from the 5.15 Samsung seed, so `AF_VSOCK` is registered
and the character device exists — but `CONFIG_VIRTIO_VSOCKETS` is *not* set and no
transport is loaded, so no CID can be assigned:

```
socket(AF_VSOCK)          -> succeeds   (family registered)
/dev/vsock                -> exists     (so ERRNO_IS_DEVICE_ABSENT() is false)
vsock_get_local_cid()     -> EADDRNOTAVAIL / ENOTTY  -> log_error_errno, exit 1
```

### Not a systemd bug, and not a kernel bug

Both behave correctly for what they can see. Qualcomm's Gunyah hypervisor really
is running under this Android-derived boot chain — the DT says so, and
`qcom,gunyah-vm` and `qcom,gh-watchdog` are there with it. The kernel really has no
vsock transport, by design.

What is wrong is the step from *"a hypervisor exists underneath"* to *"this
instance wants a host/guest AF_VSOCK SSH transport"*. Those are different claims,
and only the first is true. systemd's device-tree detection cannot tell them
apart, so the fix is to stop the automatic transport, not to make the detection
lie — patching `detect-virt` would corrupt its answer for every other consumer.

## The fix

`systemd.ssh_auto=no`, added to the kernel command line of **all 11 profiles** that
reach Debian's systemd. This is systemd's own switch for this, supported since
**v256** (the tablet runs **257.13**), and its binary carries the option name:

```
# grep -ao 'systemd\.ssh_[a-z]*' /usr/lib/systemd/system-generators/systemd-ssh-generator | sort -u
systemd.ssh_auto
systemd.ssh_listen
```

In `run()`, the early return is the first check after parsing:

```c
if (!arg_auto && strv_isempty(arg_listen_extra)) {
        log_debug("Disabling SSH generator logic, because as it has been turned off explicitly.");
        return 0;
}
```

`arg_listen_extra` is empty here (no `systemd.ssh_listen=`, no `ssh.listen`
credential), so `add_vsock_socket()` is never reached and `vsock_get_local_cid()`
is never called.

### Controlled A/B, measured on the tablet

The real generator, run under a mount namespace with a substitute `/proc/cmdline`
so only the token differs:

```
===== systemd.ssh_auto=yes =====
  generator exit=1
  stderr: [Failed to query local AF_VSOCK CID: Cannot assign requested address]
  generated: sshd-unix-local.socket, sshd-unix-local@.service
===== systemd.ssh_auto=no =====
  generator exit=0
  stderr: []
  generated: (nothing)
```

## Results

| measurement | before | after |
|---|---|---|
| `AF_VSOCK` occurrences per boot | **2** | **0** |
| `systemd-ssh-generator` lines per boot | 2 | **0** |
| generator exit status | 1 | **0** |
| generated `sshd-*` units | `sshd-unix-local.{socket,@.service}` | **none** |
| kernel cmdline | no token | `systemd.ssh_auto=no` |
| `ssh.service` | active | **active** |
| TCP `:22` listeners | 2 | **2** |
| ssh over USB NCM | works | **works** (this session) |
| `/dev/ttyGS*` count | 0 | **0** |
| gadget functions | `ncm.usb0` | **`ncm.usb0`** |
| `systemctl --failed` | 0 | **0** |
| reboot → ssh | — | **46 s** |

`sshd-unix-local.socket` is now `inactive` rather than active. That is the
generator's "SSH to this machine over a local AF_UNIX socket" facility, which
nothing on this tablet uses: the device is managed over TCP from a host. If it
were ever wanted, `systemd.ssh_listen=` re-adds a socket explicitly without
re-enabling the automatic set — which is a reason to prefer this switch over
masking the generator, since a mask would remove that option too.

## How this was verified without hiding the message

The warning was **not** suppressed. No change was made to the printk log level,
`systemd.show_status=`, `quiet`, the tty1 getty, or journal filtering. The
generator's useless AF_VSOCK path was removed, and the message stopping is a
consequence of that: `journalctl -b | grep -c AF_VSOCK` is 0 because the code that
printed it no longer runs, not because anything was silenced.

## Not done, deliberately

* **No VSOCK kernel driver added.** `CONFIG_VIRTIO_VSOCKETS`, `CONFIG_VMW_VSOCKETS`
  and `CONFIG_HYPERV_VSOCKETS` remain off; `CONFIG_VSOCKETS` was already on from the
  Samsung seed and is untouched.
* **No fake or hardcoded CID.** Inventing one would make the query succeed and bind
  `vsock::22` to a transport nothing can reach — converting a harmless warning into
  a listener that silently fails.
* **No virtual vsock device; systemd not patched, rebuilt or downgraded.**
* **`ssh.service` not disabled, `openssh-server` not removed.** That is the
  management channel; silencing a warning by removing the service would be
  backwards.
* **No USB serial port recreated, no COM port used.** The no-serial architecture is
  unchanged and asserted by the tests.

## Still not proven here

* **Wi-Fi SSH.** `wlp1s0` is up and scans **18 BSS**, so the driver and firmware
  are intact, but this tablet has **no saved Wi-Fi credentials** —
  `/etc/network/interfaces` is empty except for the `interfaces.d` source, there is
  no `wpa_supplicant` config and no NetworkManager profile. Earlier Wi-Fi tests
  (208-210) associated with an ad-hoc `wpa_supplicant`, deliberately not the
  distro's unit, so nothing persisted. Association was therefore not repeated here;
  the USB NCM path is the one exercised end to end.
* **The panel itself.** The evidence that the two lines are gone is the journal
  (`AF_VSOCK` count 0, `systemd-ssh-generator` count 0), which is the same channel
  the message was emitted on. Nobody has re-read the tty1 screen with their eyes
  after this change.
