# Debian login-screen `aux_bridge` message

The login screen's
`auxiliary aux_bridge.aux_bridge.0: deferred probe pending: ... failed to acquire drm_bridge`
comes from `drivers/gpu/drm/bridge/aux-bridge.c`: its probe requests the next
DRM bridge on graph port 0 and defers when that provider is unavailable. The
USB3/DisplayPort QMP PHY registers this auxiliary bridge. On the X710 device
tree, PHY port 0 connects to the PS5169 Type-C redriver at I2C address `0x28`,
but the pinned kernel has no driver for `parade,ps5169`. The board's
`mdss_dp0` controller is deliberately disabled pending DisplayPort bring-up.
The built-in DSI panel, framebuffer and Debian tty login work despite this
warning. It also occurs in independently successful boots, before and after
the DCC CPU-lockup repair.

A functional fix needs a separate PS5169/Type-C bridge-chain bring-up and
USB-C orientation/USB3/DisplayPort regression tests. A local X910 PS5169
Type-C redriver implementation exists in
`.work/x910/ubuntu-galaxy-tab-s9-ultra/kernel/drivers/ps5169.c`, but it does
not register a DRM bridge and has not been validated on X710. An alternative
warning-cleanup change would conditionally omit the auxiliary DRM bridge when
the board's DisplayPort pipeline is disabled, while retaining the USB QMP PHY;
that must be tested as its own change. Deleting the PHY/retimer graph or
silencing this printk without resolving the consumer would risk USB-C behavior.

The adjacent `regulator: Not disabling unused regulators` line corresponds to
the deliberate `regulator_ignore_unused` production kernel command line. It
is informational and unrelated to the display bridge or CPU fault.
