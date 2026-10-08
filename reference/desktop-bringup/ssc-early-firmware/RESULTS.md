# Early signed ADSP payload — offline size and content verification

The native SoCinfo kernel/pair is compiled offline. Samsung SSC assets/debs
remain host-only. A firmware-only newc/LZ4 overlay was generated from the
previously hash-verified owner stock archive; no runtime scripts, services,
registry or DSP daemon files. All 55 firmware/PD-map files match original
hashes, CPIO ownership is root:root, with no links/special files. Full ADSP and
ADSP-DTB segment structural validation is reused; PAS authentication/runtime
acceptance is still unverified. Firmware bytes remain private in ignored out.

The compressed payload is **19,885,531 bytes**. The X710 init_boot partition
is only **8,388,608 bytes**. It cannot fit there even without the ordinary root
initramfs. Do not overwrite init_boot with this oversized payload or quietly
remove firmware segments. The first host report command had a st_size property
call typo after the archive was generated; the report-only correction reused
and independently reopened the same archive, rather than claiming that failed
command passed.

Next controlled-boot preparation should qualify an ADSP-only **platform vendor
ramdisk** (vendor_boot has100663296-byte allocation), while retaining the exact
accepted generic init_boot, kernel cmdline, board DTB and root handoff. Before
any deployment, unpack/repack and prove only the approved ramdisk bytes and
candidate kernel differ; verify sizes/AVB footers/bootloader ramdisk delivery.
The current production platform ramdisk is empty, so delivery/ADSP firmware
availability is a new boot hypothesis, not an existing hardware pass. Do not
patch TCPM/charging, add a delayed live ADSP start, or embed unrelated CDSP/audio
changes. Keep GDM/input inactive for initial ADSP authentication/identity/rescue
checks; standard daemon one-attempt overrides are already staged.

A subsequent registration must also package exact new-identity desktop loaders,
provision the FastRPC account before permissions, install only verified runtime
dependencies with activation inhibited, map **actual** native SMEM identity,
use the copied registry, capture ADSP/FastRPC/SSC/D-Bus evidence and then test
rotation/input. Never invent soc0 values from host fixtures. Restore Test331
and newly owned userspace files on failure; final endpoint may be Debian under
the owner's updated instruction. No device operation/flash/reboot/remoteproc
start/package install/new charging attempt was performed here.

Tests/build: no new kernel/full regression for this host artifact preparation;
actual payload byte/ownership verification executed. Native kernel/input build
and affected host coverage are separately recorded; the full3032 result remains
NOTPASS. Sensor bring-up and full port remain incomplete. Charging follows
sensor acceptance per owner; limits remain unchanged in the interim.
