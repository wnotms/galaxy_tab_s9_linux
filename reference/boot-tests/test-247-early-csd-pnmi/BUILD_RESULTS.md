# Test247 build and rollback preparation complete

NOT flashed at this checkpoint. CPU repair remains OPEN. Full kernel/modules
build completed in1123.0 s with ccache and12 workers. The two-option
CSD config change required broad recompilation; no full host regression was
run.19 selected CSD source/build/fragment tests pass in0.475 s. The automatic
changed-path selector conservatively selected984 for these new unclassified
paths; the scoped validation here instead checks the actual new build,
configuration, module imports, byte manifests and rollback operation. No test
routing rule was weakened or tests deleted.

Relative to246, final config adds only CSD_LOCK_WAIT_DEBUG and its DEFAULT.
DTB/release are identical. Patches0022+0024+0026 retained; pseudo-NMI enabled,
calibration helper absent, hardlockup detector still unset. Image.gz SHA-256:
`2bd55d6b70248d3ceee2ae63d3a6d7901a735ef1177b3d0b85d7b3413e47ce7a`.
Exact symbols/module versions/notes saved under out/test247. Build provenance
records base807bc59 and hashes of the new config/cmdline subsequently committed
in171bca8. Existing seed conversion warnings are retained in build.txt.

Disassembly of this exact vmlinux confirms the synchronous wait calls
__csd_lock_wait, whose+0x29c calls dump_cpu_task, which calls the arm64 backtrace
path and nmi_trigger_cpumask_backtrace. ELF initial values independently show
CSD timeout5000, panic_on_ipistall0 and the default static key count1. These
are compiled-path/default evidence, not proof of a natural target response.
Runtime notes/relocation/GIC/CSD-parameter gates remain necessary.

All167 module import sets and named CRC mappings match the original backup.
Compared with originals, only bluetooth/mac80211/ath11k allocated sections
differ and their priority-mask alternatives add62/19/8 sites. Compared with246,
all167 have equal allocated section contents; this does not assert identical
metadata/relocations or historical in-memory bytes. Install the complete new
181-file directory anyway. depmod against the exact Module.symvers returns0
with no diagnostics. The new archive's181 hashes are checked against the
build files after packaging; expected runtime module build-id notes are saved.

Fresh read-only preflight confirms original production boot
f231faf9-fd13-468d-b6ec-58b8ade46d8e, correct rootfs UUID/machine ID, no failed
units at that sample, and all181 installed hashes match the existing original
backup. Local and Windows original tar hashes agree with the verified246
backup. The reviewed swap helper uses distinct247 temporary names. Offline
rehearsal passes bad-manifest refusal, install, restore and recovery after the
first rename. Images and module files are staged on Windows with hashes checked.

Package validator passes. init_boot and dtbo match246/originals; vbmeta is
excluded from installation. Only boot/vendor_boot and the named module
directory may change. Whole original partition hashes and mounted-root
identity must pass fresh TWRP checks before installation. Both image and module
verification records are required before reboot. After the one120 s target,
restore both originals and check production120 s. SSH/USB configuration stays
under the existing coexistence setup.
