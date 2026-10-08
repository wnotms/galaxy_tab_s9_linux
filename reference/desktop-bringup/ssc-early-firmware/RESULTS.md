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

## Bundle assembly and exact input pairing

An offline candidate `boot.img` plus `vendor_boot.img` was assembled using the
existing pinned AOSP tools. The old vendor header was unpacked into arguments;
only its single type1 platform ramdisk path was replaced. Reopened candidate
images prove exact new kernel+unchanged appended DTB, exact55-file firmware
ramdisk, unchanged absolute load addresses/cmdline/board/DTB/bootconfig and
valid AVB footers/100663296-byte partition sizing. No new init_boot/dtbo/vbmeta
was built. Actual ABL ramdisk delivery is still a physical acceptance question.
`BUNDLE.json` records hashes and all commands. This is not a deployment pass.

New candidate-specific pen/palm loader copies were generated from the accepted
loader templates. AST comparison proves only PROFILE hash values changed;
logic, safety limits, one-load behavior and charging-experiment rejection are
identical. Original templates/device loaders remain unchanged. New identities
are bound to newly rebuilt modules/notes/config; 10 mock checks pass: both
exact identities ready, old331 config/wrong notes/charging flags rejected and
altered module an error. Generated Python sources and STAGED_LOADERS.json are
saved here for reproducibility; they are not installed.

No repeated kernel/full test run for this pure artifact assembly; the native
build/41 affected tests, SSC125 pass, CRCs and original loader qualifications
remain separate. Full regression remains NOTPASS as recorded. Next concrete
step is controlled-boot registration and offline runtime installation/rollback
recipe before device mutation, then signed ADSP/native identity/FastRPC/SSC and
bounded GNOME rotation acceptance. No additional charging attempt or cap change.
