# test-213: the production initramfs boots Debian, and the failure test found two gaps

Boot `9db5d567-0c71-43e2-bee7-3d5138831521` for the successful production handoff.
The failure test that follows is described at the end, including what it cost.

## What was flashed

Only `init_boot.img` changed. `vendor_boot` (command line), `boot` (kernel) and
`dtbo` were already correct from the previous round and were byte-identical
before and after.

| partition | sha256 | changed? |
|---|---|---|
| `init_boot` | `7884eeadab8350b2ff4c46f27ecc5a5aad9efa03b66d7cc9f7b01f92e6bc6b92` | **yes** — production initramfs |
| `vendor_boot` | `86088a80a14b205baac1aa708c5a02017badce1abce97c7cc668b0432dd43aec` | no (`systemd.ssh_auto=no` from the previous round) |
| `boot` | `943b086b38cc96f2eb0cd96d1bade9789a6c2711bf0d3b4981fb77f4cf9e8e0f` | no |
| `dtbo` | `c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3` | no |

Rollback to the previous (single, bring-up) initramfs:
`/home/ms/Samsung/gts9-flash-tests/pre-production-initramfs/`.

## It booted, and the handoff is fast

SSH over USB NCM was back **45 s** after `systemctl reboot`, which is the same as
the baseline measured before this change.

The stage record on the Debian root, written by the production handoff:

```
boot_id=9db5d567-0c71-43e2-bee7-3d5138831521
kernel_release=7.2.0-rc3-gts9wifi-dirty
root_device=/dev/mmcblk1p1
stage=switch-root-synced
stage_history=kernel-userspace,waiting-root,root-found,mounting-root,root-mounted,init-found,switch-root,switch-root-synced
failure=none
debian_stage=multi-user
debian_stage_history=systemd-entered,local-fs,basic,panel-recovered,tty1-getty-active,usb-acm-ready,multi-user
```

The whole initramfs handoff occupies **~100 µs** of monotonic time, because it is
now only the handoff:

| stage | monotonic |
|---|---|
| `kernel-userspace` | 1.699145 |
| `waiting-root` | 1.699154 |
| `root-found` | 1.699162 |
| `mounting-root` | 1.699170 |
| `root-mounted` | 1.699211 |
| `init-found` | 1.699243 |
| `systemd-entered` (Debian) | 2.857963 |
| `basic` | 3.089916 |
| `panel-recovered` | 3.728131 |
| `tty1-getty-active` | 4.152085 |
| `ssh.service` started | 3.967177 |
| `multi-user` | 6.511737 |

`/init` entered and the root filesystem mounted within 66 µs of each other. There
is nothing left in the path to be slow.

## Acceptance checks

| # | check | result |
|---|---|---|
| 1 | Debian boots | **yes** |
| 2 | tty1 login prompt | yes (`tty1-getty-active` at 4.15 s) |
| 3 | no USB serial device | **0** `/dev/ttyGS*` |
| 4 | gadget is `ncm.usb0` only | **yes** |
| 5 | ssh over `usb0` | **yes** (`169.254.42.1/16`) |
| 6 | Wi-Fi driver intact | verified in test-212 (18-27 BSS scanned) |
| 7 | `ssh.service` active | **yes** |
| 8 | AF_VSOCK warnings | **0** |
| 9 | `systemctl --failed` | **0** |
| 10 | reboot works | **yes** (45 s) |
| 12 | rootfs stage record exists | **yes**, 9 fields incl. `debian_stage_history` |
| 13 | no initramfs gadget / re-enumeration | **yes** — see below |

### Item 13 in detail

The gadget was created **exactly once**, by Debian, well after `switch_root`:

```
[3.072162] systemd[1]: Starting gts9-usb-acm.service - X710 USB debug link (NCM network for ssh; no serial port)...
[4.505862] gts9-usb-acm[530]: ncm.usb0 linked into the configuration
[4.535170] gts9-usb-acm[530]: bound to a600000.usb
[4.547725] gts9-usb-acm[530]: usb0 up with 169.254.42.1/16
```

One bind, one enumeration, at 4.5 s. Under the old architecture the initramfs
built a gadget first and Debian tore it down and rebuilt it, so this is the USB
re-enumeration the split was meant to remove.

## The failure test: it worked, and it found two things

The brief asked for a deliberate failure: boot with
`gts9_rootfs=/dev/does-not-exist` and confirm the handoff reaches a tty1 rescue
shell after ~30 s without PID 1 exiting or panicking. A one-off `vendor_boot.img`
carrying that command line was built and flashed
(`5a25ff3ea795abbcd746af82037e4c3fef208cf3594f8a3c04dc41b4ff2e791c`).

**The rescue path itself behaved exactly as designed.** Debian did not boot, no
network came up, and PID 1 stayed alive - it was observed for 120 s with no reboot
loop and no panic. The root wait, the failure record and the rescue banner all
fired.

**Finding 1: the rescue was not escapable, and this cost a recovery trip.** The
production initramfs has no USB gadget and no Wi-Fi, so no network; there is no
serial port; and the applet list had no `reboot` or `poweroff`. Nothing inside the
shell could leave it, so recovering the tablet needed a physical key combination.
A rescue shell that cannot be left is a trap, not a rescue.

Fixed in the same round: `reboot` and `poweroff` are now in the applet list (in
`/sbin`, already on the handoff's `PATH`), and the banner says what the options
are. This does not make *this* failure reversible - it makes the next one
reversible. The tablet still needed physical recovery.

**Finding 2: the rescue banner may not be visible.** `gts9-panel-recover.service`
is a **Debian** service, and it is what cycles the framebuffer when the panel's
cold-boot enable reads a dead DDIC (`ana38407 panel id: 00 00 00`). It runs at
3.7 s on a successful boot - but in the rescue path Debian never starts, so that
recovery never runs. Display recovery was removed from the production initramfs
deliberately (it is a diagnostic capability and it delays the handoff), so on a
cold boot where the panel hits the zero-ID case there may be a rescue shell that
cannot be seen.

This is a real tradeoff rather than an oversight, and it is recorded here rather
than papered over. The options, none of them taken yet because each is a decision
rather than a cleanup:

* accept it - the panel usually works, the stage record is readable from TWRP, and
  a visible-early-panel recovery would put the DPU modeset back in the boot path,
  where test 178 caught an intermittent DPU hang;
* gate it on failure only: do the framebuffer cycle **after** the root mount has
  already failed, so it costs nothing on a healthy boot and only runs when the
  rescue shell is about to be needed. That is the option most consistent with this
  round's "nothing debug-only on the critical path" rule, and it is the one worth
  doing next.

## Not proven here

* **The panel was not read with eyes.** The successful boot's `tty1-getty-active`
  stage and the owner's earlier screenshot of the login prompt are the evidence
  that the panel works on a healthy boot; nobody has looked at the screen in the
  rescue case, which is exactly Finding 2.
* **The escape hatch has not been used on a device.** The `reboot`/`poweroff`
  applets were added after this test, so the image on the tablet during the test
  did not have them.
* **Poweroff timing was not re-measured**, because the tablet could not be reached
  to run it. The previous rounds measured 0.38-0.82 s with zero stop timeouts and
  nothing in this change touches that path.
