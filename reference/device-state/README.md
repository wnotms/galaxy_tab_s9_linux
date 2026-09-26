# On-device state: what is recorded, and why

Some of what this project needs cannot be expressed as a file in the repository.
Two categories exist, and neither is visible to `git status` on the host or to
`git log` on the tablet:

1. **Flashed boot-chain partitions** — `boot`, `init_boot`, `vendor_boot` are
   images written to UFS. `uname -r` cannot tell two builds of the same release
   apart, and the release string has not changed across several of them.
2. **Configuration written on the device** — files under `/etc/systemd/system/`,
   the configfs gadget, the address on `usb0`. An earlier install left a stale
   unit file and a stale autologin drop-in there, and both were live problems
   rather than history: the drop-in was still injected an `agetty --autologin`
   override on `ttyGS0`.

`rootfs-overlay/usr/libexec/gts9-device-changes` produces the record. It is
read-only unless asked to write, so it can be run before and after any deployment
and the two outputs diffed.

```sh
# on the tablet
gts9-device-changes              # print
gts9-device-changes --write      # also write /var/log/gts9-device-state
```

The output is `key=value` lines, the same shape as
`/var/log/gts9-minimal-last-boot`, so two records diff with plain `diff`.

## What it records, and which line answers which question

| question | keys |
|---|---|
| Which kernel and command line is actually running? | `kernel_release`, `kernel_build`, `cmdline`, `boot_id`, `uptime_seconds` |
| Is any serial console back? | `console_active`, `console_cmdline_tokens`, `console_ttygs_in_cmdline`, `console_ttymsm_in_cmdline`, `earlycon_in_cmdline` |
| Can anything block on a serial port? | `ttygs_open_fds`, `unit_serial_getty_*_enabled/active` |
| What does the host enumerate? | `gadget_present`, `gadget_udc`, `gadget_functions`, `gadget_config_links`, `gadget_idvendor/product` |
| How is the ssh transport configured? | `usb_net_conf`, `usb0_addr` |
| What has been overridden by hand? | `etc_*` (one line per entry, with a content hash or symlink target), `autologin_files` |
| Does the deployed userspace match the repository? | `helper_*` (mode + content hash) |
| Which images are flashed? | `part_boot_sha256`, `part_init_boot_sha256`, `part_vendor_boot_sha256`, `part_dtbo_sha256` |
| Is the system healthy? | `failed_units`, `mmc_root`, `wifi_ifaces`, `pci_wifi` |

`autologin_files` and `etc_*` are the two that earned their place immediately:
run against the tablet on 2026-09-26 they reported, in one line each, the stale
autologin drop-in and the stale unit file that a reviewer would otherwise have had
to know to look for.

## Records kept here

| file | what it is |
|---|---|
| `2026-09-26-before-single-serial-port.txt` | the tablet before the second serial port was retired: `gadget_functions=acm.usb0 acm.usb1 ncm.usb0`, `autologin_files=/etc/systemd/system/serial-getty@ttyGS0.service.d/autologin.conf` |
| `2026-09-26-single-serial-port.txt` | the same tablet after: `gadget_functions=acm.usb0 ncm.usb0`, `autologin_files=none`, `failed_units=0` |

The pair is kept because the difference between them *is* the deployment: it shows
what was on the device, what changed, and that the change is the one intended.

## How to reproduce the change on a device

The repository-provided userspace is deployed as one overlay, so there is a single
ordered procedure rather than a set of manual edits:

```sh
# 1. host: build the overlay (kernel modules + firmware + userspace)
./scripts/install-debian-rootfs.sh --tar out/gts9-debian-overlay.tar

# 2. device: record the state first, so the change can be reviewed afterwards
gts9-device-changes --write

# 3. device: deploy and let the helper reconcile the enablement links and masks
cd / && tar -xpf /tmp/gts9-debian-overlay.tar && sync
sh /usr/libexec/gts9-enable-units /

# 4. device: the gadget is built by a service, and an already-bound gadget from
#    the previous layout is migrated on restart (see retire_second_serial)
systemctl daemon-reload && systemctl restart gts9-usb-acm.service

# 5. device: confirm, and keep the record
gts9-device-changes --write
systemctl --failed --plain --no-legend --no-pager
```

Two details matter for reproducibility:

* **`gts9-enable-units` is what makes the removal stick on an upgraded rootfs.**
  `/etc/systemd/system/` wins over `/usr/lib/`, so deleting a unit from the
  overlay is not enough - the name has to be masked. The helper now does that with
  `ln -sfn /dev/null` for all three serial getty names, and removes the stale
  autologin drop-in.
* **The gadget migration needs a service restart.** `configfs` cannot change a
  bound gadget's function set, so `gts9-usb-acm` unbinds, removes `acm.usb1` and
  rebuilds. It is a no-op when the port is already absent, which is why the
  service log shows the migration only on the first boot after the upgrade.

## Flashing, and the rollback point

The boot-chain images are flashed separately from the overlay, and that is a
manual step by design - nothing in `scripts/` writes to a device. The exact images
that were on the tablet before this work are preserved with hashes in
`../../gts9-flash-tests/pre-no-serial-backup/` (outside this repository, since
they are 220 MB of binaries), together with the `dd` commands to restore them.
