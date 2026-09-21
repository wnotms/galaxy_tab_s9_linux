# Rebooting into recovery from mainline

The owner's question was whether the tablet can be told to come back up in TWRP
instead of being power-cycled by hand.  It can, and the mechanism was already
half-present in the device tree.

## How Qualcomm and Samsung select a boot mode

`pmk8550.dtsi` (mainline, included by this board) declares:

```dts
reboot-mode {
	compatible = "nvmem-reboot-mode";
	nvmem-cells = <&reboot_reason>;
	nvmem-cell-names = "reboot-mode";
	mode-recovery = <0x01>;
	mode-bootloader = <0x02>;
};
```

`reboot_reason` is a one-byte cell in the PMK8550's SPMI SDAM.  The kernel's
`nvmem-reboot-mode` driver registers a reboot handler that maps the *string*
passed to `reboot(2)` with `LINUX_REBOOT_CMD_RESTART2` to one of those values and
writes it into the cell; ABL reads the cell early and picks the boot mode.  So
`reboot recovery` from Linux is a bootloader-visible request, not a hint.

Two things were missing on this board and are now built in
(`kernel/config/gts9wifi-mainline.fragment`):

- `CONFIG_NVMEM_SPMI_SDAM=y` - the SDAM provider; without it the cell does not
  exist at all and the reboot-mode driver has nothing to write to;
- `CONFIG_NVMEM_REBOOT_MODE=y` - the driver itself.

## Telling the kernel the mode

busybox's `reboot` applet can only ask for a plain restart, and the string is the
whole point, so the initramfs carries a 1.6 KB freestanding helper
(`boot/gts9-reboot-mode.c`, built by `scripts/build-bringup-initramfs.sh` as
`/bin/gts9-reboot-<mode>`) that issues the syscall directly.

`/init` uses it when the command line asks for it:

```
gts9_proof_action=recovery
```

instead of the default `poweroff`.  If the helper fails or ABL ignores the cell,
the script records that and falls back to a plain reset - which lands back in
mainline, so a failed experiment looks like a boot loop rather than a dead
tablet, and holding Volume Up still gets TWRP.

## Status

Not yet observed on hardware: test 024 is the first run with
`gts9_proof_action=recovery`.  Until it is confirmed, the default stays
`poweroff` and the workflow keeps asking the owner to boot recovery by hand.
