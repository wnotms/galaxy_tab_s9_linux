# Twenty-minute duration follow-up — READY_OFFLINE_DEFAULT_OFF

Kernel source0b731b4ac7721429202a747a4ccae82ce9624c0b adds only1200000ms to the
immutable exclusive one-shot allowlist. DefaultOFF/30000ms and300000ms remain.
Current, register programming, voltage, thermal, fault, PM, epoch, lease,
park/refresh,500ms gap and final2000ms reserve are unchanged. No active deadline
extension, repeat activation, higher-current or automatic charging is introduced.

167 affected tests passed:85 actual-C (including complete modeled1200s and late
sensor/source/detach/PM/gap/PPS/fixed-return failures),11 duration-parser and71
retained lifecycle/safety tests. The initial two historical live-parser-equality
failures were corrected with manifest-verified historical Git objects; raw failures
and rationale retained. Old guardians still reject1200s. Real Test345/347 PASS
and Test344 STOP replayed at their proper duration. No skipped/deleted tests,
full suite or CI. Test routing unchanged.

Incremental8-job/ccache ARM64/modules build PASS84.982s. Changed-driver W=1/sparse
PASS13.493s, no warnings, original qualified object restored, no formal relink.
Four inherited config warnings exactly match previous qualification. Embedded
config extracted from Image matches resolved config. Exact Test331 config/DTB/
release unchanged; config.diff and dtb.diff empty. HVC_DCC=n, USER_NS/container,
SM5714/ADC5 Gen3, fixed5V<=1.8A /9V<=1.5A /float4.44V/thermal retained.
108 protected sources and9 retained canonical artifacts preserved.181 modules
match Test347 file set and runtime code; metadata/BTF/build identity differ,
so use the new paired archive rather than old modules.

Formal Image.gz/DTB/config/kernel notes/release/modules and a verified defaultOFF
boot are in out/kernel-x710-twenty-minute and out/boot-bundle-x710-twenty-minute-off.
PACKAGE.json/SHA256.json identify exact files and accepted Test331 rollback.
The existing build/source cache was reused; no new full build tree or Windows
transfer stage was created. Historical Test347 and current331 artifacts were
not overwritten. The kernel's additional duration is not enabled in this boot.

The device remains TWRP with restored Test331 per owner request. **No device
command, flash, reboot, rootfs change, PPS request or pump run in this phase.**
There is no Test348 physical registration/guardian or1200s authorization yet.
Next implement that independent confirmed-C1 workflow with explicit1200s native
binding, lower entry-SOC margin, unchanged safety/fault timeouts, outer observation
limits sized for1200s, sole activation and final exact331 restoration to TWRP.
Prepare/qualify/register before requesting the new physical scope. Do not reuse
or restart Test347, whose one300s grant is consumed. Full port **NOT_READY**:
physical20min, higher-current, calibration and vendor-equivalent policy remain.
