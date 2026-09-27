# DCC repair candidate built and packaged

NOT yet flashed. Kernel and all modules build in71.1 s using ccache.
Relative to the observed-failing247 config, only HVC_DCC and its sole-selected
HVC_DRIVER change fromy ton. The new production fragment overrides the immutable
Android seed; the build's existing off-symbol gate now rejects HVC_DCC=y.
DTB and release are identical. The exact image has no hvc_dcc* or hvc_write
symbol; PNMI/CSD/LA/ECC/BBM diagnostics remain for attributable validation.

The15 selected build/console/USB-invariant checks pass. Exact config comparison,
167-module import/CRC audit, depmod against saved Module.symvers,181-file archive
hashes, four offline module-install/rollback cases and boot-bundle validation
pass. The same three modules retain PNMI-related differences from originals;
all modules will be installed as a matched set. Exact kernel symbols and notes
are saved under out/test248. Original tar/partition backups and the complete
fresh live original module manifest match before staging. Windows staged images,
module archive and helpers have verified hashes. No USB/SSH setting was edited.

The physical target will additionally require embedded config HVC_DCC=n,
no /dev/hvc0 or /sys/class/tty/hvc0, inactive serial-getty@hvc0, exact kernel
notes/six anchors, pseudo-NMI and unchanged runtime detector parameters. This
initial120 s startup tests the directly diagnosed path removal; it does not
prove every historical fault had the same cause or replace final production
validation. Fresh TWRP partition/mount gates still precede writes.
