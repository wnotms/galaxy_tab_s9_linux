# The AF_VSOCK warning from systemd-ssh-generator, and why a physical tablet hit it

## SYMPTOM

Every boot printed this on the panel, between the tty1 login prompt lines:

```
systemd-ssh-generator: Failed to query local AF_VSOCK CID: Cannot assign requested address
```

It is not fatal and nothing was broken by it — `ssh.service` was listening and
both management paths worked throughout — but it is noise on the console of a
device whose console is a user-facing screen, and it names a subsystem this
tablet does not use.

Reproduced deterministically, outside of a boot, by running the generator by hand:

```
# /usr/lib/systemd/system-generators/systemd-ssh-generator /tmp/g /tmp/g /tmp/g
Failed to query local AF_VSOCK CID: Cannot assign requested address
```

Also visible with `--help`, which is the same code path and is a convenient
one-liner to re-check:

```
# /usr/lib/systemd/system-generators/systemd-ssh-generator --help
Failed to query local AF_VSOCK CID: Cannot assign requested address
```

## SYSTEM STATE

Measured on the tablet on 2026-09-26.

| | value |
|---|---|
| device | Samsung Galaxy Tab S9 Wi-Fi, SM-X710 / `gts9wifi`, Qualcomm SM8550 |
| userland | Debian GNU/Linux 13 (trixie) |
| systemd | **257 (257.13-1~deb13u1)** |
| USB serial | **none** — `/dev/ttyGS*` does not exist |
| USB gadget functions | `ncm.usb0` only |
| management channel | TCP SSH (`ssh.service`, port 22) over USB NCM and Wi-Fi |
| `/dev/vsock` | exists as a device node (`10,257`) but no transport is loaded |
| vsock modules loaded | `vsock` only; no `vsock_loopback`, no virtio/hyperv/vmw transport |
| `/proc/net/vsock` | does not exist — the socket family is registered, no transport backs it |

## ROOT CAUSE

Established by reading systemd v257's sources and by measuring this board, not by
interpreting the message.

**1. `systemd-detect-virt` reports this tablet as a VM.**

```
# systemd-detect-virt
vm-other
# systemd-detect-virt --vm
vm-other
# systemd-detect-virt --container
none
```

**2. Why:** `src/basic/virt.c`, `detect_vm_device_tree()`, reads
`/proc/device-tree/hypervisor/compatible` and returns `VIRTUALIZATION_VM_OTHER`
for any value it does not specifically recognise:

```c
r = read_one_line_file("/proc/device-tree/hypervisor/compatible", &hvtype);
...
if (streq(hvtype, "linux,kvm"))
        return VIRTUALIZATION_KVM;
else if (strstr(hvtype, "xen"))
        return VIRTUALIZATION_XEN;
else if (strstr(hvtype, "vmware"))
        return VIRTUALIZATION_VMWARE;
else
        return VIRTUALIZATION_VM_OTHER;      /* <-- this board lands here */
```

This board's device tree has that node, and Samsung's boot chain supplies it:

```
# cat /proc/device-tree/hypervisor/compatible
qcom,gunyah-hypervisor-1.0
qcom,gunyah-hypervisor
simple-bus
```

**3. `systemd-ssh-generator` acts on that.** From
`src/ssh-generator/ssh-generator.c` (v257). `arg_auto` defaults to true, and:

```c
static int add_vsock_socket(...) {
        Virtualization v = detect_virtualization();
        if (!VIRTUALIZATION_IS_VM(v)) {
                log_debug("Not running in a VM, not listening on AF_VSOCK.");
                return 0;
        }
        ...
        r = vsock_get_local_cid(&local_cid);
        if (r < 0) {
                if (ERRNO_IS_DEVICE_ABSENT(r)) { ... return 0; }
                return log_error_errno(r, "Failed to query local AF_VSOCK CID: %m");
        }
```

So the chain is: DT node → `vm-other` → `VIRTUALIZATION_IS_VM()` is true →
`socket(AF_VSOCK)` **succeeds** (the family is registered) → `/dev/vsock` **exists**
so the device-absent escape does not apply → `vsock_get_local_cid()` fails with
`EADDRNOTAVAIL` → error, exit 1.

**4. The CID ioctl really does fail here**, which is what the message says and is
worth confirming rather than assuming:

```
$ python3 -c 'import socket,fcntl,struct
fd=socket.socket(socket.AF_VSOCK,socket.SOCK_STREAM)
print(struct.unpack("I",fcntl.ioctl(fd,0x7b9,struct.pack("I",0)))[0])'
ioctl failed: [Errno 25] Inappropriate ioctl for device
```

### This is not a systemd bug and not a kernel bug

Both are behaving correctly for what they can see:

* **Qualcomm's Gunyah hypervisor is genuinely present.** This tablet boots through
  Samsung's Android-derived chain, and Gunyah is running underneath Linux — the
  device tree says so, and the `qcom,gunyah-vm` and `qcom,gh-watchdog` nodes are
  there with it. systemd correctly concludes "there is a hypervisor here".
* **The kernel has no vsock transport, by design.** `CONFIG_VSOCKETS=y` is set
  (it comes from the 5.15 Samsung seed and is what makes `AF_VSOCK` and
  `/dev/vsock` exist), but `CONFIG_VIRTIO_VSOCKETS` is **not** set and no
  transport module is loaded. So a CID query cannot succeed.

The wrong step is not the detection; it is the *conclusion drawn from it* — that a
**physical tablet** should offer a host/guest AF_VSOCK SSH transport. Two distinct
statements must not be conflated:

| statement | true here? |
|---|---|
| a hypervisor exists under this Linux instance | **yes** — Gunyah, per the DT |
| this instance is a VM guest that should expose SSH over AF_VSOCK to a host | **no** — it is a standalone tablet whose management path is TCP/IP |

systemd's own `detect_vm_device_tree()` cannot distinguish those from the DT node
alone. So the right fix is not to make the detection lie — that would be a patch to
`systemd-detect-virt`, which this change deliberately does not do — but to turn off
the automatic transport that the false positive triggers.

## FIX

`systemd.ssh_auto=no` on the kernel command line of every profile that reaches
Debian's systemd.

`systemd-ssh-generator` has supported this since **v256**; the tablet runs **257**,
and its own binary contains the option name:

```
# grep -ao 'systemd\.ssh_[a-z]*' /usr/lib/systemd/system-generators/systemd-ssh-generator | sort -u
systemd.ssh_auto
systemd.ssh_listen
```

It is the documented switch for exactly this case — `man systemd-ssh-generator`:

> **systemd.ssh_auto=** — This option takes an optional boolean argument, and
> defaults to yes. If enabled, the automatic binding to the AF_VSOCK and AF_UNIX
> sockets listed above is done. If disable, this is not done, except for those
> explicitly requested via `systemd.ssh_listen=` on the kernel command line or via
> the `ssh.listen` system credential.

And in the source, the early return is the first thing `run()` does after parsing:

```c
if (!arg_auto && strv_isempty(arg_listen_extra)) {
        log_debug("Disabling SSH generator logic, because as it has been turned off explicitly.");
        return 0;
}
```

`arg_listen_extra` is empty on this tablet — there is no `systemd.ssh_listen=`
token and no `ssh.listen` credential — so the generator returns before
`add_vsock_socket()` can be reached, and therefore before
`vsock_get_local_cid()` can fail.

### A/B control, run on the tablet

Both arms exercised the real generator under a mount namespace with a substitute
`/proc/cmdline`, so the comparison is a controlled measurement and not an
inference:

```
===== systemd.ssh_auto=yes =====
  generator exit=1
  stderr: [Failed to query local AF_VSOCK CID: Cannot assign requested address]
  generated files:
    /tmp/genc-yes/sockets.target.wants/sshd-unix-local.socket
    /tmp/genc-yes/sshd-unix-local.socket
    /tmp/genc-yes/sshd-unix-local@.service
===== systemd.ssh_auto=no =====
  generator exit=0
  stderr: []
  generated files:
```

`yes` reproduces the error and exit status; `no` produces no output, no error and
no units.

### Why the cmdline switch rather than masking the generator

Masking (`/etc/systemd/system-generators/systemd-ssh-generator -> /dev/null`) would
also silence the message, and it is kept as the documented fallback. It was not
used because the switch is better on every axis that matters here:

| | `systemd.ssh_auto=no` | generator mask |
|---|---|---|
| expresses the intent | yes — "do not auto-bind transports" | it says "this generator must not run" |
| modifies a Debian package file | no | no (an `/etc` override), but it disables the whole program |
| depends on generator search-path override semantics | no | yes |
| meaning across systemd upgrades | documented, stable | the unit simply never runs |
| leaves `systemd.ssh_listen=` / `ssh.listen` usable | **yes** | no — everything the generator offers is gone |
| misleading to a later maintainer | no | yes — looks like the generator is broken |

The mask remains appropriate only if a future systemd drops or breaks the switch;
that has not happened here (257 ≥ 256, and the option name is present in the
installed binary).

## WHY SAFE

`systemd.ssh_auto=` governs **only** the transports `systemd-ssh-generator`
creates automatically:

* the AF_VSOCK listener (`sshd-vsock.socket`, `ListenStream=vsock::22`),
* the local AF_UNIX listener (`/run/ssh-unix-local/socket`),
* the container export listener (`/run/host/unix-export/ssh`).

It does **not** touch the conventional OpenSSH service. `ssh.service` is a normal
Debian unit running `/usr/sbin/sshd`, listening on TCP port 22; the generator never
owned it and its socket units are separate. Nothing in this change disables,
masks, reconfigures or restarts `ssh.service`, and no firewall or `sshd_config`
setting was altered.

Verified explicitly, because "should not" is not "did not":

```
# systemctl is-active ssh.service
active
# ss -lntp | grep ':22'
LISTEN 0 128 0.0.0.0:22 0.0.0.0:* users:(("sshd",pid=898,fd=6))
LISTEN 0 128    [::]:22    [::]:* users:(("sshd",pid=898,fd=7))
```

The only thing lost is `sshd-unix-local.socket`, which is the generator's
"SSH to this machine over a local AF_UNIX socket" facility. It has no user on this
tablet: nothing connects to `/run/ssh-unix-local/socket`, and the device is managed
over TCP from a host. If it were ever wanted, `systemd.ssh_listen=` re-adds a
socket explicitly without re-enabling the automatic set.

## VERIFICATION

| check | before | after |
|---|---|---|
| `AF_VSOCK` error occurrences per boot | 2 (generator + a `daemon-reload`) | **0** |
| generator exit status | 1 | 0 |
| generated `sshd-*` units | `sshd-unix-local.{socket,@.service}` | **none** |
| `ssh.service` | active | **active** |
| TCP `:22` listening | yes | **yes** |
| ssh over USB NCM (169.254.42.1) | works | **works** |
| `/dev/ttyGS*` | absent | **absent** |
| gadget functions | `ncm.usb0` | **`ncm.usb0`** |
| `systemctl --failed` | 0 | **0** |
| kernel cmdline | no `systemd.ssh_auto=` | `systemd.ssh_auto=no` on every profile |

The full report with the commands and their output is in
[test-212](../reference/boot-tests/test-212-ssh-generator-vsock/README.md).

## WHAT WAS NOT DONE

Every one of these was considered and rejected; they are listed because each is a
plausible-looking shortcut that would have been worse than the problem.

* **No VSOCK kernel driver was added.** `CONFIG_VSOCKETS` was already on from the
  Samsung seed; `CONFIG_VIRTIO_VSOCKETS`, `CONFIG_VMW_VSOCKETS` and
  `CONFIG_HYPERV_VSOCKETS` remain off. Adding one would be building a transport for
  a hypervisor guest this tablet is not, to satisfy a generator that should not be
  running. `tests/test_systemd_ssh_generator.py` asserts none of them appear.
* **No fake or hardcoded AF_VSOCK CID.** A CID is assigned by the hypervisor to a
  guest; inventing one would make `vsock_get_local_cid()` succeed and have the
  generator bind `vsock::22` to a transport where nothing can connect. It would
  convert a harmless warning into a listener that silently fails.
* **No virtual vsock device was created.**
* **systemd was not patched, rebuilt or downgraded.** The switch is the upstream
  interface for this; patching `detect_vm_device_tree()` to ignore Gunyah would
  have made `systemd-detect-virt` report wrong answers for every other consumer
  and would have been lost on the next upgrade.
* **`ssh.service` was not disabled, and `openssh-server` was not removed.** Those
  are the tablet's management channel; silencing a warning by removing the service
  would be exactly backwards.
* **The warning was not hidden.** No change to `printk` log level,
  `systemd.show_status=`, `quiet`, `getty@tty1`, or journal filtering. The
  generator's useless AF_VSOCK path was removed; the message stopping is a
  consequence, not the method.
* **No USB serial port was recreated** and **no COM port was used as a recovery
  channel.** The no-serial architecture is the result of the previous rounds and
  is unrelated to this warning; it is left exactly as it was, and the tests assert
  that.
