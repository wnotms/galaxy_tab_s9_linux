# Test 167 — install Debian boot and power-off stage markers

**Result: PASS for installation and unit validation.** The five diagnostic
helper/unit files from the repository were copied over the live COM17 session
to the running Debian root filesystem. All three units are enabled,
`systemd-analyze verify` returned success, and the device's file hashes match
the repository files.

The files were installed through the running Debian root filesystem. No raw
partition-flash, `poweroff`, or reboot command was issued. The device was left
running Debian. This test only prepares the next boot/shutdown observation; it
does not test the kernel's power-off handler or battery-only cold boot.

## Evidence inventory

- `install-result.txt`: enabled-unit state, shutdown dependency, and matching
  file hashes from the read-only COM17 verification.
- `SHA256SUMS`: hashes of the evidence files, excluding itself.
- The full serial login transcript is not archived, so credentials and login
  prompts remain outside the repository.
