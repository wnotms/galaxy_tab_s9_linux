# Fedora kernel vs this repository's kernel — a file-by-file comparison

Repo A = `/home/ms/Samsung/galaxy_tab_s9_linux` (pinned Linux v7.2-rc3,
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`). Repo B =
`/home/ms/Samsung/gts9wifi-fedora-linux` (`prepare.sh` runs against the `linux-7.2`
tarball; README: "stable 7.2 plus a small patch set"). Every claim below comes from
a file read in full or in the quoted region; unread files are listed at the end.
Repo A's `pending/` and `diagnostic/` queues are covered where they change a
"does Repo A have this" answer.

| | Repo A | Repo B |
|---|---|---|
| base | v7.2-rc3 pinned commit, `git apply` queue | `linux-7.2` tarball, `patch -p1 --forward` |
| patches | 9 default + 8 `pending/` + 4 `diagnostic/` | 19 flat files in `kernel/patches/` |
| DTS | 2048 lines | 1823 lines |
| out-of-tree src | 3 `.c` in `kernel/drivers/` + reference-only vendor pogo | 13 `.c`/`.h` + `snvm/` (19 files) + `spu/` (11 files) |
| config seed | byte-verified **stock Samsung 5.15.153 Android** | mainline pmOS **`config-mainline.aarch64`** |
| release | `7.2.0-rc3-gts9wifi` | `7.2.0-gts9wifi` |
| modules | built and staged (`BUILD_MODULES=1`) | none by design ("does not install or autoload the generic kernel module tree") |

---

## 1. Patch-by-patch

Repo B applies all 19 files in one batch, lexical order
(`prepare.sh:16-18`: `patch -p1 --forward < "$p"`).

### 1.1 `add-gts9wifi-dtb.patch`
Adds to `arch/arm64/boot/dts/qcom/Makefile`:
`dtb-$(CONFIG_ARCH_QCOM) += sm8550-samsung-gts9wifi.dtb` and
`DTC_FLAGS_sm8550-samsung-gts9wifi := -@` (overlay symbols for ABL's DTBO flow).
**Repo A: equivalent, not a patch.** `scripts/prepare-kernel.sh:123-129` appends the
same two lines. `kernel/patches/README.md` records that the script owns this file.

### 1.2 `add-samsung-sec-log-console.patch`
Adds `config SAMSUNG_GTS9WIFI_SEC_LOG` to `drivers/soc/qcom/Kconfig`, the
`obj-$(CONFIG_SAMSUNG_GTS9WIFI_SEC_LOG) += samsung-gts9wifi-sec-log.o` line to
`drivers/soc/qcom/Makefile`, and the **whole 139-line driver inline** as
`drivers/soc/qcom/samsung-gts9wifi-sec-log.c`. The driver registers a `struct
console` that copies printk text into Samsung's `sec_log_buf` reserved-memory ring
behind `struct sec_log_header { u32 boot_count; u32 magic; u32 index; u32
previous_index; u8 data[]; }` with `SEC_LOG_MAGIC 0x4d474f4c` ("LOGM"); probe is
`of_parse_phandle(dev->of_node,"memory-region",0)` → `of_reserved_mem_lookup()` →
`devm_memremap(...,MEMREMAP_WB)` → `register_console()`, matching
`compatible = "samsung,gts9wifi-sec-kernel-log"`. Purpose: a console that survives
a warm reset before any rootfs exists, readable as `/proc/last_kmsg` from TWRP.
**Repo A: equivalent by name and symbol.**
`0002-soc-qcom-hook-x710-sec-log-into-kbuild.patch` adds the *same* Kconfig block
and Makefile line, but the driver body is `kernel/drivers/samsung-gts9wifi-sec-log.c`
(492 lines) installed by `prepare-kernel.sh`. Repo A's version additionally has
`early_param("gts9_sec_log", ...)` with a cmdline base/size override, three
`early_memremap()` proof-of-life markers (`GTS9-HEAD`, `GTS9-SETUPARCH`,
`GTS9-EARLY-MARKER`), an `early_initcall` registration path, a cache flush after
every write (`gts9wifi_sec_log_flush`, because the ring is write-back and "a reset
does not flush our caches"), and a protected tail window Repo B has none of.

### 1.3 `build-wcn-pcie-providers-in.patch`
Two Kconfig default changes: `default y if ARCH_QCOM` on `PCI_PWRCTRL_PWRSEQ`
(`drivers/pci/pwrctrl/Kconfig`) and on `QCOM_QMI_HELPERS`
(`drivers/soc/qcom/Kconfig`). Makes the WCN pwrseq providers built-in on Qualcomm
so `ath11k_pci`'s `select PCI_PWRCTRL_PWRSEQ` is satisfied without module autoload.
**Repo A: nothing, and not needed.** Resolved config keeps
`CONFIG_PCI_PWRCTRL_PWRSEQ=m` and `CONFIG_POWER_SEQUENCING_QCOM_WCN=m`
(`out/kernel-gts9wifi/config`) because Repo A ships modules. Repo B has no module
tree, so it must force `=y`.

### 1.4 `configure-nxp-ptn3222-from-dt.patch`
`drivers/phy/phy-nxp-ptn3222.c`: adds `regmap_config` (8/8 bits,
`max_register = 0xff`), `u32 init_seq[PTN3222_MAX_INIT_CELLS]` (16), a
probe-time `of_property_count_u32_elems()`/`of_property_read_u32_array()` read of
`qcom,param-override-seq`, and in `ptn3222_init()` after
`gpiod_set_value_cansleep(reset_gpio, 0)` a `usleep_range(4000, 5000)` then
`regmap_write(regmap, init_seq[i+1], init_seq[i])` per pair. Without it the board's
"physical link unusable and the DWC3 core unable to complete its soft reset".
**Repo A: same change, different name** —
`nxp-ptn3222-apply-dt-register-overrides.patch` in the default queue. Same
`PTN3222_MAX_INIT_CELLS 16`, same `usleep_range(4000, 5000)`, same value/register
order. Only substantive delta: Repo A adds an unconditional probe log
`dev_info(dev, "repeater %pOFn: %d override cells\n", dev->of_node, count);`.
Both DTS files carry identical values:
`qcom,param-override-seq = <0x20 0x06 0x21 0x07 0x63 0x08 0x03 0x09 0x01 0x0a>`.

### 1.5 `expose-separate-gpu-kms-resources.patch`
`drivers/gpu/drm/msm/msm_drv.c`: makes the render-only Adreno DRM instance
created by `msm.separate_gpu_kms=1` advertise `DRIVER_MODESET` —
`.driver_features = DRIVER_FEATURES_GPU | DRIVER_MODESET`, adds
`.dumb_create = msm_gem_dumb_create` and `.dumb_map_offset = drm_gem_dumb_map_offset`,
and initialises an empty managed mode_config (`min_width/height = 1`,
`max_width/height = 16384`, `.fb_create = msm_framebuffer_create`). Message: "Xorg's
modesetting driver rejects the GPU before it can create a PRIME source provider:
`DRM_IOCTL_MODE_GETRESOURCES` fails instead of returning an empty resource list";
Xorg needs a temporary 32-bpp dumb framebuffer before switching to glamor.
**Repo A: nothing at all** in any of the three queues. Repo A *does* run
`msm.separate_gpu_kms=1` on every example cmdline, but drives the native panel
through the separate DPU card, so it has never needed GPU-side modeset.

### 1.6 `ignore-console-null.patch`
`kernel/printk/printk.c`: `static bool __initdata ignore_console_null`,
`early_param("ignore_console_null", ...)`, and in `console_setup()` before the
`console=null` handling:
```c
	if (ignore_console_null && (str[0] == 0 || strcmp(str, "null") == 0))
		return 1;
```
Stops Samsung ABL's appended `console=null` from removing the framebuffer console.
**Repo A: byte-identical.** `0003-printk-allow-ignoring-samsung-console-null.patch`.
`diff` of the two hunks (everything from `diff --git`) is empty, including context
and the `index 95fcb42f2132..81db2a0d684d` line. Repo A names the SM-X910 port as
origin, Repo B names SM-X710.

### 1.7 `keep-sec-log-previous-index-current.patch`
Follow-up to 1.2, editing only the new `drivers/soc/qcom/samsung-gts9wifi-sec-log.c`:
```c
-	/* Match the downstream ring: index is monotonically increasing. */
-	WRITE_ONCE(log->header->index, index + count);
+	index += count;
+	WRITE_ONCE(log->header->index, index);
+	WRITE_ONCE(log->header->previous_index, index);
```
So `previous_index` tracks `index` on every write; recovery uses `previous_index` as
the length of `/proc/last_kmsg`, and a manual key reboot from a mainline panic
bypasses the firmware step that normally snapshots it.
**Repo A: same change, already inside its driver source** —
`kernel/drivers/samsung-gts9wifi-sec-log.c:183-193` carries the same comment and the
same three writes. Repo A has no separate patch for it, because its snapshot
derives from the already-fixed X910 tree and Repo B's from the pre-fix one.

### 1.8 `match-samsung-sm8550-eusb2-phy-init.patch`
`drivers/phy/phy-snps-eusb2.c`, `qcom_snps_eusb2_hsphy_init()`: a
`usleep_range(10, 20)` after `snps_eusb2_hsphy_write_mask(phy->base,
QCOM_USB_PHY_UTMI_CTRL5, POR, POR)`, and
`FIELD_PREP(PHY_CFG_PLL_CPBIAS_CNTRL_MASK, 0x1)` instead of `0x0` on
`QCOM_USB_PHY_CFG_CTRL_1`. Message claims the host "cannot read its USB
descriptor" with upstream sequencing.
**Repo A: has it and REJECTED it.** `kernel/patches/pending/snps-eusb2-match-samsung-sm8550-init.patch`,
disposition `REJECTED ON X710`. `pending/README.md`: "tried in test 021 and broke
this board. With it the kernel never reached userspace and no gadget appeared on
the host at all, where test 020 with the same kernel minus this patch produced a
host-visible `VID_0525&PID_A4A7`. Samsung's CPBIAS=1 plus the post-POR delay is the
right sequence for the X910's PHY configuration and wrong for this one." Followed by
"Do not re-apply it." This is the sharpest direct conflict between the trees.

### 1.9 `msm-dp-allow-unresolved-usbc-bridge.patch`
`drivers/gpu/drm/msm/dp/dp_display.c`, `msm_dp_display_probe_tail()`:
```c
-		if (dp->is_edp || ret != -ENODEV)
+		if (dp->is_edp ||
+		    (ret != -ENODEV && ret != -EPROBE_DEFER))
 			return ret;
```
Turns an unresolved optional downstream DRM bridge on external DP into "no
downstream bridge" rather than a defer; eDP stays strict. Stated consequence:
deferring the DP component "also prevents the shared MSM DRM component master and
the unrelated internal DSI panel from binding".
**Repo A: nothing at all.** Repo A instead keeps
`&mdss_dp0 { status = "disabled"; }` with the comment "on mainline the DisplayPort
controller is one of the components the msm DRM master waits for, and here it never
finishes probing, so no DRM card, framebuffer or console is created". The two trees
solve the same problem in opposite ways.

### 1.10 `msm-dp-associate-bridge-of-node.patch`
One line in `drivers/gpu/drm/msm/dp/dp_drm.c`, `msm_dp_bridge_init()`:
`bridge->of_node = msm_dp_display->pdev->dev.of_node;`. The comment says the
controller's firmware node is kept on the terminal bridge "so the bridge connector
then exposes the same fwnode to out-of-band Type-C HPD notifications on systems
where HPD is carried only by USB-PD". **Repo A: nothing equivalent** — no DP fwnode
work.

### 1.11 `msm-dp-defer-oob-hpd-until-resume.patch`
The largest DP patch. `dp_drm.h`: `struct msm_dp_bridge` grows
`struct notifier_block pm_notifier`, `struct delayed_work deferred_hpd_work`,
`enum drm_connector_status deferred_hpd_status`, `bool defer_hpd_until_resume`,
`bool deferred_hpd_pending`. `dp_drm.c`: adds
`msm_dp_bridge_deferred_hpd_work()`, `msm_dp_bridge_pm_notifier()` (on
`PM_POST_SUSPEND`, reschedules the work after `msecs_to_jiffies(3000)`), an
unregister action, and a probe-time branch gated on the DT property
`qcom,defer-hpd-until-first-resume` (the hunk header is corrupted in the file:
`static void msm_dp_bridge_u	      "qcom,defer-hpd-until-first-resume")) {`).
`dp_display.c`: `msm_dp_bridge_hpd_notify()` records the status and returns early
while deferral is armed. **Repo A: nothing at all** — no
`qcom,defer-hpd-until-first-resume` anywhere, no DP HPD work, `mdss_dp0` disabled.

### 1.12 `qcomtee-add-spss-shared-heap.patch`
Adds `TEE_DMA_HEAP_SPSS_SHARED` to `enum tee_dma_heap_id`
(`include/linux/tee_core.h`), maps it to `"qcom,secure-sp-tz"` in
`drivers/tee/tee_heap.c`, adds `spu_tz_base/size/assigned` to `struct qcomtee`
(`drivers/tee/qcomtee/qcomtee.h`), and in `drivers/tee/qcomtee/call.c` adds
`qcomtee_register_spu_heap()`: `of_find_node_by_name(NULL,
"spu-tz-shared-region")` → `of_address_to_resource()` →
`qcom_scm_assign_mem(base, size, BIT_ULL(QCOM_SCM_VMID_HLOS),
{QCOM_SCM_VMID_CP_SPSS_SP_SHARED, QCOM_SCM_PERM_RW}, 1)` →
`tee_protmem_static_pool_alloc()` → `tee_device_register_dma_heap()`, called at the
end of `qcomtee_probe()` with `-ENODEV` tolerated silently. Gives the fingerprint
stack a TrustZone-shared heap with the SPSS VMID. **Repo A: nothing** —
`out/kernel-gts9wifi/config: # CONFIG_TEE is not set`, no `*qcomtee*` patch.

### 1.13 `qcomtee-use-tzmem-pool.patch`
`drivers/tee/qcomtee/shm.c`: replaces `tee_dyn_shm_alloc_helper()` with Qualcomm's
TZMEM allocator. `struct qcomtee_shm_pool { struct tee_shm_pool base; struct
qcom_tzmem_pool *tzmem; }`; `pool_op_alloc()` keeps the page-backed path below
`QCOMTEE_TZMEM_OBJECT_MIN_SIZE (SZ_2M)` and above it uses
`qcom_tzmem_alloc(qpool->tzmem, size, GFP_KERNEL | GFP_DMA32)` plus an explicit
32-bit check (`!paddr || paddr > U32_MAX || size - 1 > U32_MAX - paddr` →
`-EOVERFLOW`); `qcomtee_shm_pool_alloc()` gains
`QCOM_TZMEM_POLICY_ON_DEMAND` / `QCOMTEE_SHM_POOL_MAX_SIZE (SZ_32M)`. Reason given:
Samsung's QSEECom compatibility layer gives dualfp "two contiguous 0x2a4000-byte
objects in addition to its large signed image", and `qcom_tzmem_to_phys()` is the
address the SHM bridge and the secure-world memory-object callback expect; the
EL721 ABI uses 32-bit physical addresses. **Repo A: nothing** — no TEE/QCOMTEE work.

### 1.14 `quiet-adsp-handover-already-happened.patch`
One line in `drivers/remoteproc/qcom_q6v5.c`, `q6v5_handover_interrupt()`:
`dev_err(...)` → `dev_dbg(q6v5->dev, "Handover signaled, but it already happened\n")`
on the `if (q6v5->handover_issued)` path. Repo B's `docs/Known-Issues.md` issue 19
quantifies: "repeated at roughly **5.4 times per second** — 99.98 % of the `dmesg`
ring (37,402 of 37,411 lines)". **Repo A: nothing equivalent.** Highest
value-per-line item in either tree, and exactly the class of problem Repo A writes
whole documents about (`docs/BOOT_CONSOLE_BLOCK.md`).

### 1.15 `set-mi2s-codec-dai-format.patch`
`sound/soc/qcom/sc8280xp.c`: adds `#define MI2S_BCLK_RATE 1536000`,
`sc8280xp_is_mi2s()` (true for `PRIMARY_MI2S_RX ... QUATERNARY_MI2S_TX` and
`QUINARY_MI2S_RX ... QUINARY_MI2S_TX`), a new `sc8280xp_snd_startup()` that per
codec DAI calls `snd_soc_dai_set_fmt(codec_dai, SND_SOC_DAIFMT_CBC_CFC |
SND_SOC_DAIFMT_I2S | SND_SOC_DAIFMT_NB_NF)` then `snd_soc_dai_set_sysclk(codec_dai,
0, MI2S_BCLK_RATE, SND_SOC_CLOCK_IN)` (tolerating `-ENOTSUPP`) and finally
delegates to `qcom_snd_sdw_startup()`; rewires `sc8280xp_be_ops.startup`. Reason:
"the codec side was never told anything: an I2S codec kept its reset default
format, and — more importantly — was never given the bit clock rate it has to lock
its PLL to, so it produced no audio at all." **Repo A: nothing equivalent**, but the
defect is reachable: Repo A's DTS uses the same `qcom,sm8550-sndcard` /
`qcom,sm8450-sndcard` and a CS35L45 `PRIMARY_MI2S_RX` link, and its fragment does
not set `CONFIG_SND_SOC_SC8280XP`.

### 1.16 `tcpm-adopt-retained-source-ufp.patch`
Adds `bool adopt_retained_source_ufp` to `struct tcpc_dev`
(`include/linux/usb/tcpm.h`) and in `tcpm_pd_rx_handler()`
(`drivers/usb/typec/tcpm/tcpm.c`) a branch before the data-role-mismatch error
recovery: if the TCPC opted in, the port is `TYPEC_SINK`/`TYPEC_DEVICE`, and the SOP
header has `PD_HEADER_PWR_ROLE` and not `PD_HEADER_DATA_ROLE`, it calls
`tcpm_set_roles(port, true, TYPEC_STATE_USB, TYPEC_SINK, TYPEC_HOST)` and jumps to a
new `process_message:` label instead of `ERROR_RECOVERY`. Fixes an externally
powered charge-through dock that keeps Source/UFP across a host reboot. **Repo A:
nothing at all** — no such member, no `process_message:` label, no tcpm.c patch in
any queue. Repo A runs TCPM but has no sm5714 USB-PD driver, so the path is inert.

### 1.17 `tcpm-use-retained-sink-data-role.patch`
Companion to 1.16. Adds `bool (*consume_retained_sink_dfp)(struct tcpc_dev *dev)`
to `struct tcpc_dev`; uses it in `tcpm_snk_attach()` (computes `bool retained_dfp`,
then passes `TYPEC_HOST` instead of `tcpm_data_role_for_sink(port)` to
`tcpm_set_roles()`) and in `run_state_machine()`'s SRC→SNK hard-reset transition
(`port->tcpc->adopt_retained_source_ufp && port->data_role == TYPEC_HOST ?
TYPEC_HOST : tcpm_data_role_for_sink(port)`). **Repo A: nothing at all.**

### 1.18 `unpark-pcie0-pipe-mux.patch`
`drivers/phy/qualcomm/phy-qcom-qmp-pcie.c`, `qmp_pcie_power_on()`, between the
existing `if (ret) return ret;` and `ret = reset_control_deassert(qmp->nocsr_reset);`:
```c
+	clk_set_rate(qmp->pipe_clks[0].clk, ULONG_MAX);
```
`ULONG_MAX` is the clk-regmap-phy-mux "select the PHY source" sentinel. Reason:
"Samsung's X710 boot chain parks PCIe0's mux on the XO reference (the register reads
PHY_MUX_REF_SRC, 19.2 MHz). With the mux parked the MAC-PHY PIPE interface is dead
and the LTSSM never performs receiver detection."
**Repo A: same change, different name** —
`0009-phy-qcom-qmp-pcie-select-phy-source-on-pipe-mux.patch`, whose provenance says
it is "adapted from kernel/patches/unpark-pcie0-pipe-mux.patch in the
gts9wifi-fedora-linux port for this same device (commit ab123e7)". Code hunk
identical; Repo A's header adds the measured values
(`pcie0_pipe_clk 125000000` vs `gcc_pcie_0_pipe_clk_src 19200000`).

### 1.19 `wcn7850-pwrseq-cold-reset-aop.patch`
`drivers/power/sequencing/pwrseq-qcom-wcn.c`: adds
`#include <linux/soc/qcom/qcom_aoss.h>`; a `bool cold_reset_wlan` field in
`pwrseq_qcom_wcn_pdata` set `true` for both `pwrseq_wcn6855_of_data` and
`pwrseq_wcn7850_of_data`; a new `pwrseq_qcom_wcn_program_wlan_pdc()` that
`qmp_get()`s the device when `qcom,qmp` is present and iterates
`of_property_for_each_string(dev->of_node, "qcom,wlan-pdc-init", prop, msg)` calling
`qmp_send(qmp, "%s", msg)`, invoked from probe; and changes the `wlan-enable` GPIO
to `ctx->pdata->cold_reset_wlan ? GPIOD_OUT_LOW : GPIOD_ASIS` with
`usleep_range(5000, 10000)` replacing the
`gpiod_direction_output(..., gpiod_get_value_cansleep(...))` re-assert.
**Repo A: same change** —
`0008-power-sequencing-qcom-wcn-send-aop-wlan-pdc-votes.patch`, whose header names
Repo B's file as the source. I diffed both: the code hunks are the same change;
differences are only hunk headers (Repo A carries function context in `@@` lines,
Repo B has bare offsets) and Repo B's file having no `diff --git`/`index` lines at
all. Repo A adds "Not verified on hardware at the time of writing."

### 1.20 Repo A queue items Repo B lacks
`0001-arm64-dts-qcom-sm8550-add-samsung-abl-labels.patch` (adds `qcom_tzlog: chosen`,
`qcom_scm: scm: scm`, `arch_timer: timer` labels to
`arch/arm64/boot/dts/qcom/sm8550.dtsi`; I confirmed pristine v7.2-rc3 has only
`scm: scm` at line 389, `/chosen { }` unlabelled and `timer {` unlabelled, so the
patch is still required by its own stated criterion);
`0004-drm-panel-add-samsung-ana38407.patch` (Kconfig/Makefile hook — Repo B does the
same wiring with `sed`/`echo` in `prepare.sh:42-50`);
`0006-input-add-samsung-pogo-keyboard.patch` (Kconfig/Makefile hook for a driver Repo
B does not have at all).

---

## 2. Board DTS, subsystem by subsystem

I diffed both raw and with comments stripped, so the items below are real
property/status differences. **With comments removed the entire functional delta
is:** `/chosen`'s cell properties; `ramoops` vs `sec-pmsg`; `wakeup-source` on the
`gpio-keys` parent; `&scm`'s interrupt cells; the duplicate `&pon_pwrkey`; `&usb_1`'s
`dr_mode`; `&mdss_dp0`'s status; and Repo A's entire pogo section. Everything else
is character-identical apart from comments.

### 2.1 Display (mdss, mdss_dp0, panel)
Both files: `&mdss { status = "okay"; }`; `&mdss_dsi0 { vdda-supply =
<&vreg_l3e_1p2>; status = "okay"; }` with an identical `panel@0` node —
`compatible = "samsung,ana38407-amsa10fa01"`, `vddio-supply = <&vreg_l12b_1p8>`,
`vdd-supply = <&vreg_l11b_1p1>`, `vci-supply = <&vreg_l13b_3p0>`, `avdd-supply =
<&display_avdd>`, `reset-gpios = <&tlmm 125 GPIO_ACTIVE_HIGH>`, `te-gpios =
<&tlmm 86 GPIO_ACTIVE_HIGH>`, `pinctrl-0 = <&sde_te>`; identical
`&mdss_dsi0_out { data-lanes = <0 1 2 3>; }` and `&mdss_dsi0_phy { vdds-supply =
<&vreg_l1e_0p88>; status = "okay"; }`. Neither `/chosen` has a
`simple-framebuffer`. The only display difference is DP:
```
 &mdss_dp0 {
-	status = "disabled";          <- Repo A
+	qcom,defer-hpd-until-first-resume;   <- Repo B
+	status = "okay";
 };
```
Repo A's comment: DP "never finishes probing, so no DRM card, framebuffer or console
is created". Repo B's: "The ANA38407 needs one platform suspend/resume after a cold
boot. Activating the external DPU encoder before that cycle makes the platform
suspend reset the board." **Verdict: Repo B is more functional, Repo A more
self-consistent.** Repo B has DP *and* the three DP patches (1.9–1.11) that make the
MSM component master tolerate the unresolved Type-C bridge; Repo A's queue has none
of them, so enabling `mdss_dp0` on Repo A would break the internal panel exactly as
its comment says. Repo A's `mdss_dsi0_phy` is `okay` in both.

### 2.2 USB (`usb_1`/dwc3 `dr_mode`, ptn3222, ps5169, tcpm)
Identical in both: `&usb_1_hsphy { vdd-supply = <&vreg_l1e_0p88>; vdda12-supply =
<&vreg_l3e_1p2>; phys = <&eusb2_repeater>; status = "okay"; }`;
`&usb_1_dwc3_hs { remote-endpoint = <&sm5714_hs_in>; }`; `&usb_dp_qmpphy
{ vdda-phy-supply = <&vreg_l3e_1p2>; vdda-pll-supply = <&vreg_l3f_0p88>; status =
"okay"; }`; `&usb_dp_qmpphy_out { remote-endpoint = <&ps5169_ss_in>; }`; the PTN3222
node on `&i2c6` (`redriver@4f`, `compatible = "nxp,ptn3222"`, `reset-gpios =
<&pm8550vs_d_gpios 4 GPIO_ACTIVE_LOW>`, the override sequence, `pinctrl-0 =
<&eusb2_reset_default>`); the PS5169 node on `&i2c12` (`redriver@28`,
`parade,reg50 = <0x10>`, `parade,reg51 = <0x70>`, `parade,reg54 = <0x02>`,
`parade,reg5d = <0x40>`, `usb-role-switch = <&usb_1>`, `retimer-switch`,
`orientation-switch`, two ports); the whole `sm5714_usbpd` connector block.
The one delta:
```
 &usb_1 {
-	dr_mode = "peripheral";   <- Repo A
 	status = "okay";
 };
```
Repo A's comment: "Force the peripheral role. The Type-C port is managed by an
SM5714 PD controller that has no mainline driver, so there is no role switch and no
extcon to move dwc3 out of its OTG default: the core probes, exposes a UDC, and
never enables the port." **Verdict: Repo B is more complete.** It has the SM5714
`tcpc_dev` driver, the PS5169 mux driver, `TYPEC_SM5714`/`TYPEC_MUX_PS5169`/
`TYPEC_DP_ALTMODE`/`TYPEC_MUX_GPIO_SBU` and the two retained-role TCPM patches, so
the OTG default is actually driven. Repo A's DTS binds the same nodes to drivers
that do not exist (`docs/DT_PROVIDER_AUDIT.md`: "`parade,ps5169` | *(none)* |
Type-C redriver; no driver source declares it in this tree at all"), which is why it
pins `dr_mode`. Repo A's arrangement is what its `ttyGS0`/`ttyGS1` console
methodology depends on.

### 2.3 Power (`pon_pwrkey`, regulators)
`&pon_pwrkey` is `okay` in both, but Repo A sets it **twice** — line 811
(`&pon_pwrkey { status = "okay"; }`, no comment) and line 1099 with the comment
"Mainline ships this disabled. Enabling it gives the tablet a working power button
(input event, and a wakeup source); without it a suspend on this board has no way
back." Same value, so redundant but harmless. Repo B has it once (line 748).
The `&apps_rsc` regulator blocks (`regulators-0` PM8550B and PM8550VS-C/E/F/G) are
functionally identical; the diff there is comments only. Both carry the same
`vreg_l1b_1p8`, `vreg_l4b_1p8`, `vreg_l11b_1p1`, `vreg_l12b_1p8`, `vreg_l13b_3p0`,
`vreg_l15b_1p8`, `vreg_s2g_1p012`, `vreg_s4e_0p952`, `vreg_s4g_1p352`,
`vreg_s5g_0p966`, `vreg_s6g_1p904` rails the WCN/panel/camera nodes consume, the
same `display_avdd` (`5500000`, `gpio = <&pm8550_gpios 11 GPIO_ACTIVE_HIGH>`,
`enable-active-high`, `regulator-boot-on`), the same `panel_ldo` (`1800000`,
`gpio = <&tlmm 187 GPIO_ACTIVE_HIGH>`, `regulator-boot-on`, `regulator-always-on`)
and the same `&pm8550vs_d { status = "okay"; }`.
**Delta:** Repo A adds a container-level `wakeup-source` to the `gpio-keys` node
(line 382) — "The volume keys are on TLMM lines and need wakeup-source to bring the
tablet back from a suspend; the power key below is a PMIC input and is a wakeup
source on its own" — in *addition* to the per-key `wakeup-source` both files already
carry on `key-volume-up` (`gpios = <&pm8550_gpios 6 GPIO_ACTIVE_LOW>`,
`debounce-interval = <15>`, `linux,can-disable`) and `switch-lid`
(`gpios = <&tlmm 107 GPIO_ACTIVE_LOW>`, `<50>`, `EV_SW`/`SW_LID`). **Verdict:
effectively equal.** Repo A's container-level property is broader (every child
becomes a wake source) and is deliberate for this board's suspend problem; Repo B's
per-key form is narrower and more precise. Repo A's duplicate `&pon_pwrkey` is
untidy but not incorrect.

### 2.4 Wi-Fi/BT (`pcie0`, wcn pwrseq, AOP PDC table)
Character-identical in both files: `&pcie0 { wake-gpios = <&tlmm 96
GPIO_ACTIVE_HIGH>; perst-gpios = <&tlmm 94 GPIO_ACTIVE_LOW>; pinctrl-0 =
<&pcie0_default_state>; pinctrl-names = "default"; status = "okay"; }`; the whole
`wcn6855_pmu` root node — `compatible = "qcom,wcn6855-pmu"`, `pinctrl-0 = <&wlan_en>,
<&bt_default>, <&pmk8550_sleep_clk>`, `wlan-enable-gpios = <&tlmm 80
GPIO_ACTIVE_HIGH>`, `bt-enable-gpios = <&tlmm 81 ...>`, `swctrl-gpios = <&tlmm 82
...>`, `xo-clk-gpios = <&tlmm 204 ...>`, `qcom,qmp = <&aoss_qmp>`, the **11-string
`qcom,wlan-pdc-init` list** (identical values: `s4e.v` 966/615, `s4g.v` 1350/945,
`s6g.v` 1900/1825, `s2g.m enable 1`, `s2g.v enable 1/1012/800`, `bb pdc enable 0`),
ten `vdd*`-supply properties and nine `vreg_pmu_*` child regulators;
`&pcieport0 { wifi@0 { compatible = "pci17cb,1103"; ... ten supplies ... } }`;
`&uart14 { status = "okay"; bluetooth { compatible = "qcom,wcn6855-bt"; ... eight
vdd* supplies ... max-speed = <3200000>; }; }`. Only the comments differ — Repo B's
records that "The pmOS port dropped these votes (c49bd79) ... after a full poweroff
(cold handoff) the PMU never completes power-up without these votes ... (reproduced
on device, 2026-09-04)". **Verdict: DT content equivalent; the difference is kernel
support.** Repo A has both drivers for these properties (patches 0008 and 0009) and
per `docs/WIFI_QCA6490_BRINGUP.md` has reached every level
(`PCI_ONLY`, `DRIVER_BOUND`, `FIRMWARE_LOADED`, `WLAN_INTERFACE`, `SCAN_WORKS`,
`ASSOCIATION_WORKS` on 5 GHz, `NETWORK_STABLE`, and real HTTP traffic; boot
`3cba35b7`, test-210). Repo B has the
*same two patches* but its `docs/Known-Issues.md` issue 20 records Wi-Fi dead on
every 7.2.1–7.2.6 stable kernel (`did not load image over BHI, -5` / `did not enter
READY state, -110`), which is why it is pinned to 7.2.0. Repo B additionally has
`build-wcn-pcie-providers-in.patch` (§1.3); Repo A does not need it.

### 2.5 ADSP/LPASS
Functionally identical. Both: `&lpass_ag_noc { status = "disabled"; }` and the same
for `&lpass_lpiaon_noc` / `&lpass_lpicx_noc`; `&remoteproc_adsp` with
`firmware-name = "qcom/sm8550/adsp.mdt", "qcom/sm8550/adsp_dtb.mdt"` and
`/delete-property/ interconnects;` (Repo A: `of_icc_get()` never resolves because
the LPASS sub-graph does not connect to `mc_virt` so the driver stays in
`-EPROBE_DEFER`; Repo B spells out the same phandles and that
`lpass_ag_noc@7e40000 is disabled upstream`); identical `&lpass_tlmm`
`dmic45_default`/`dmic67_default` states; identical `&lpass_vamacro`; identical
`sound` card (`compatible = "qcom,sm8550-sndcard", "qcom,sm8450-sndcard"`, a
CS35L45 `PRIMARY_MI2S_RX` playback link, a VA-macro `VA_CODEC_DMA_TX_0` capture
link). **Verdict: DTS equal; Repo B is far ahead in kernel support** — it builds
`QCOM_Q6V5_PAS`, `SND_SOC_QDSP6`, `SND_SOC_SC8280XP`, `SND_SOC_CS35L45_I2C`,
`SND_SOC_LPASS_VA_MACRO`, `PINCTRL_SM8550_LPASS_LPI`, `GPIO_SHARED_PROXY` all `=y`
and carries `set-mi2s-codec-dai-format.patch`. Repo A sets none of those
`SND_SOC_*` symbols.

### 2.6 Cameras
Identical four nodes and properties in both: `&cci0_i2c1 { hi1337_rear: camera@21
{ compatible = "hynix,hi1337-gts9u-rear"; ... rotation = <0>; lens-focus =
<&rear_focus>; } }`, `&cci1_i2c0 { rear_focus: lens@c { compatible =
"dongwoon,dw9808-vcm"; } }`, `&cci1_i2c1 { hi1337_front: camera@21 { compatible =
"hynix,hi1337-gts9u-front"; ... rotation = <0>; } }`, plus the `&camss` block, same
supplies/clocks (`CAM_CC_MCLK*`)/resets/pinctrl. Comment-only deltas, and both are
evidence comments: Repo A "Do not declare `<90>`: the value is applied as-is" vs
Repo B "Declaring `<90>` made libcamera report the wrong rotation and GNOME Camera's
viewfinder rotate by 90°"; Repo B's front node adds "a full 0x08..0x77 address sweep
on the front bus with the sensor powered and MCLK4 running, where only 0x21 returned
model 0x1337 / vendor 0x2000". **Verdict: Repo B, decisively** — it has
`hi1337_gts9u.c` (+ tables) and `dw9808_vcm.c` and sets `VIDEO_HI1337_GTS9U=y`,
`VIDEO_DW9808_VCM=y`, `VIDEO_QCOM_CAMSS=y`, `I2C_QCOM_CCI=y`, `SM_CAMCC_8550=y`,
`MEDIA_SUPPORT=y`, `VIDEO_DEV=y`. Repo A's DTS binds four nodes to four compatibles
with **no driver in the tree** (`docs/DT_PROVIDER_AUDIT.md` lists
`hynix,hi1337-gts9u-{rear,front}` and `dongwoon,dw9808-vcm` as parked) and sets none
of those symbols.

### 2.7 Pogo keyboard
**Repo A has a complete section** (lines 1899-2048): `vreg_pogo` fixed regulator
(`gpio = <&tlmm 10 GPIO_ACTIVE_HIGH>`, `enable-active-high`, `pinctrl-0 =
<&pogo_supply>`); `&i2c15 { status = "okay"; clock-frequency = <400000>;
keyboard@2a { compatible = "samsung,x710-pogo-keyboard"; reg = <0x2a>;
interrupt-parent = <&tlmm>; interrupts = <75 IRQ_TYPE_LEVEL_LOW>; connect-gpios =
<&tlmm 62 GPIO_ACTIVE_HIGH>; announce-gpios = <&tlmm 75 GPIO_ACTIVE_LOW>;
swclk-gpios = <&tlmm 12 ...>; nrst-gpios = <&tlmm 13 ...>; sda-gpios = <&tlmm 72
...>; scl-gpios = <&tlmm 106 ...>; vdd-supply = <&vreg_pogo>; ... } }`;
`&qup_i2c15_data_clk { drive-strength = <2>; bias-pull-up; }`; and five pinctrl
states (`pogo_supply` with deliberate `output-high`, `pogo_bus_gpio`, `pogo_irq`
with `bias-pull-up`, `pogo_swclk` `output-low`, `pogo_nrst` `output-high`), each
with its reasoning. The node also carries Samsung's downstream property names
(`stm32,irq_type = <0x2008>`, `stm32,irq_conn_type = <0x2003>`,
`stm32,model_name = "EF-DX715", "EF-DX710"`, `stm32,fw_name`,
`support_open_close`, `samsung,stop-after-trans`, a "recovery" pinctrl) so the
vendor driver can bind the same node. **Repo B has nothing** — no `vreg_pogo`, no
`keyboard@2a`, no `&i2c15`, no `pogo_*` states, no `EF-DX710` string anywhere in the
file; its DTS ends after the camera section and `i2c15` stays at the SoC default.
**Verdict: Repo A, completely** — board description plus driver
(`keyboard-samsung-pogo.c`, 64 KB, `CONFIG_KEYBOARD_SAMSUNG_POGO=y`) plus the vendor
import for a manual A/B.

### 2.8 ramoops / sec-pmsg
Repo A: `ramoops_mem: ramoops@880900000 { compatible = "ramoops"; reg = <0x8
0x80900000 0x0 0x200000>; record-size = <0x20000>; console-size = <0xe0000>;
pmsg-size = <0x100000>; no-map; }` plus a 45-line comment recording the stock
evidence (`sec_pmsg_region@880900000 { compatible = "samsung,carve-out"; }`,
`samsung,pstore_pmsg { memory-region = <0x583>; }`), the measured outcome ("the
backend registers and the console attaches ... but records do NOT survive a reboot
on this device. A userspace pmsg record written to /dev/pmsg0 and a real sysrq panic
both left /sys/fs/pstore empty on the next boot, the latter after `pstore:
zlib_inflate() failed, ret = -3!`") and the instruction "Do not treat
`/sys/fs/pstore` as an evidence source yet."
Repo B replaces it with the vendor shape:
```
-		ramoops_mem: ramoops@880900000 {
-			compatible = "ramoops";
+		sec_pmsg_mem: sec-pmsg@880900000 {
 			reg = <0x8 0x80900000 0x0 0x200000>;
-			record-size = <0x20000>;
-			console-size = <0xe0000>;
-			pmsg-size = <0x100000>;
 			no-map;
 		};
```
i.e. an unnamed, driverless reservation with no `compatible`. Both files carry the
identical `sec_log_buf_mem: sec-log@880200000` (deliberately not `no-map` in both)
and the identical `sec-kernel-log { compatible =
"samsung,gts9wifi-sec-kernel-log"; memory-region = <&sec_log_buf_mem>; }`.
**Verdict: Repo A** — it binds the mainline driver and documents the negative result;
Repo B does not even reach the "registers but does not persist" state. Neither gives
working post-reboot persistence, and Repo A's own test 007 recorded the bootloader
filling 2,096,187 of 2,097,136 ring bytes, so an empty ring is not evidence.

### 2.9 Volume-key `wakeup-source`
Covered in §2.3. Repo A adds a container-level `wakeup-source` to `gpio-keys`; Repo
B has only the per-key properties. Both files carry per-key `wakeup-source` on
`key-volume-up` and `switch-lid`. For the volume key itself the two are equivalent.

### 2.10 `scm` interrupt cells
```
 &scm {
-	interrupts = <GIC_SPI 930 IRQ_TYPE_EDGE_RISING 0>;   <- Repo A
+	interrupts = <GIC_SPI 930 IRQ_TYPE_EDGE_RISING>;     <- Repo B
 };
```
Repo A's comment: "SM8550's GIC is `#interrupt-cells = <4>` (the fourth cell selects
the PPI partition and is 0 for an SPI), so a three-cell specifier is malformed: dtc
reports it and `of_irq_parse_one()` fails with `-ENODATA`, which makes
`qcom_scm_probe()` fall back to probing without the SCM waitqueue interrupt." I
verified the premise: `.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550.dtsi`
`intc: interrupt-controller@17100000` has `#interrupt-cells = <4>`.
**Verdict: Repo A.** Repo B's three-cell specifier is malformed for this SoC and
silently drops the SCM waitqueue interrupt.

### 2.11 Other deltas
`/chosen` has `#address-cells = <2>; #size-cells = <2>;` in Repo A only (superfluous
without a child node; neither has a `simple-framebuffer`). Everything else is
identical: `&tlmm { gpio-reserved-ranges = <36 4>; ... }` with the same
TrustZone comment, `&hwfence_shbuf { reg = <0x0 0xe6440000 0x0 0x2dd000>; }`, and all
fourteen reserved-memory carve-outs (`kaslr@b01ff000`, `uh-heap@b0200000`,
`uh-guest@b1000000`, `chipinfo@81cf4000`, `sec-xbl-ramdump@a7d00000`,
`adspslpi@9ea00000`, `llcc-lpi@ff800000`, `splash_region`, `sec-debug-pool@880100000`,
`sec-reset-info@8801ff000`, `sec-debug-bl@880400000`, `google-debug-kinfo@880b00000`,
`hdm@880b01000`, `sec-qcom-rdx@880c00000`) — as are `&dispcc`, `&gpu` (with
`zap-shader/firmware-name = "qcom/a740_zap.mdt"`), `&iris`
(`firmware-name = "qcom/vpu/vpu30_4v.mbn"`), `&ufs_mem_hc`, `&ufs_mem_phy`,
`&sdhc_2`, `&i2c3` digitizer (`wacom,w90xx`), `&i2c4` touchscreen (`st,fts1ba90a`),
the four `cs35l45` amplifiers on `&i2c_hub_6`, `&i2c_hub_3/8/9`, `&gpi_dma1/2`,
`&sleep_clk` and `&xo_board`.

---

## 3. Kernel config fragments

Repo A `kernel/config/gts9wifi-mainline.fragment` (348 lines, ~150 `CONFIG_*`);
Repo B `kernel/files/config-gts9wifi.fragment` (318 lines, ~170). "A only" / "B only"
mean the line appears in that fragment and not the other. Several "A only" symbols
are already `=y` in **Repo B's seed** (`config-mainline.aarch64`, 12664 lines, header
`Linux/arm64 7.2.0-rc3`), so Repo B's fragment does not repeat them; where I checked
the seed that is noted. Repo A's seed is the byte-verified stock Samsung 5.15.153
Android config materialised by `scripts/materialize-stock-config.sh`.

### 3.1 Repo A sets, Repo B's fragment does not

**Boot plumbing / providers** — `ARCH_QCOM`, `QCOM_SMEM`, `QCOM_SMP2P`, `QCOM_RPMH`,
`QCOM_COMMAND_DB`, `QCOM_SCM`, `QCOM_CLK_RPMH`, `QCOM_RPMHPD`, `SPMI_MSM_PMIC_ARB`,
`MFD_SPMI_PMIC`, `PINCTRL_MSM`, `PINCTRL_SM8550`, `PINCTRL_QCOM_SPMI_PMIC`,
`REGULATOR`, `REGULATOR_QCOM_RPMH`, `COMMON_CLK_QCOM`, `SM_GCC_8550`,
`SM_TCSRCC_8550`, `ARM_SMMU`, `NVMEM_QCOM_QFPROM`, `QCOM_TSENS`, `RTC_DRV_PM8XXX`,
`QCOM_SPMI_ADC5`, `QCOM_WDT`, `ARM_QCOM_CPUFREQ_HW`. **All present in Repo B's seed
already** (`=y`, except `QCOM_WDT=m`, `RTC_DRV_PM8XXX=m`, `QCOM_SPMI_ADC5=m` — the
three `=m` ones matter on a port with no module autoload).

**Interconnect / CPU path** — `INTERCONNECT`, `INTERCONNECT_QCOM`,
`INTERCONNECT_QCOM_SM8550`, `INTERCONNECT_QCOM_OSM_L3`. In Repo B's seed the first
three are `=y` but **`INTERCONNECT_QCOM_OSM_L3=m`**, and Repo B's fragment does **not**
override it. Repo A's fragment carries a 20-line derivation of the `=m` trap:
`17d90000.interconnect` (`qcom,sm8550-epss-l3`, driven only by
`INTERCONNECT_QCOM_OSM_L3`) is `cpu0`'s third `interconnects` phandle;
`dev_err_probe()` logs `-EPROBE_DEFER` at debug level so only the outer "Failed to
find icc paths" appears; result "no cpufreq policy on any cluster, no schedutil, a
fixed firmware-left OPP on all eight cores, and gcc's `sync_state()` blocked for the
life of the boot". On this reasoning the defect is live in Repo B too.

**QCOM PDC** — `QCOM_PDC=y` (Repo A, with the SPMI-arbiter derivation). Present `=y`
in Repo B's seed, not repeated.

**AOSS QMP / IPCC / HWSPINLOCK** — `QCOM_AOSS_QMP`, `QCOM_IPCC`, `HWSPINLOCK`,
`HWSPINLOCK_QCOM`. All four already `=y` in Repo B's seed.

**Kernel-log / persistence profile** — `PRINTK_TIME`, `MAGIC_SYSRQ`, `PANIC_TIMEOUT=0`,
`PM_DEBUG`, the `PSTORE*` set, `RD_LZ4` (both trees set all of these);
`CMDLINE=""`, `LOCALVERSION="-gts9wifi"`, `# LOCALVERSION_AUTO is not set` (Repo A
only; Repo B writes `-gts9wifi` into `localversion-gts9wifi` from the workflow).

**Console / VT** — `VT=y`, `VT_CONSOLE=y` (both already `=y` in Repo B's seed);
`FONTS=y` and **`FONT_TER16X32=y`** (Repo A only — "the 8x16 default is unreadable on
a 2560x1600 panel"). Repo B's seed has `# CONFIG_FONTS is not set`, `FONT_TER16X32`
absent, and Repo B's fragment sets neither.

**USB console** — **`U_SERIAL_CONSOLE=y`** (Repo A only). Repo B's seed has
`# CONFIG_U_SERIAL_CONSOLE is not set` and its fragment does not set it. This is the
symbol whose `gserial_alloc_line` → `gs_console_init` path creates the `ttyGS*` kernel
console Repo A's whole console methodology uses.

**Toolchain profile** — `LTO_NONE=y` plus explicit `is not set` for
`LTO_CLANG_FULL`, `LTO_CLANG_THIN`, `CFI`, `KASAN`, `UBSAN`, `WERROR`. Repo B's seed
already has `LTO_NONE=y`, `WERROR`/`KASAN` unset — but **`CONFIG_CFI=y`**, which
Repo B's fragment does not turn off.

**Radio module profile** — Repo A: `CFG80211=m`, `MAC80211=m`, `ATH_COMMON=m`,
`ATH11K=m`, `ATH11K_PCI=m`, `BT=m`, `BT_HCIUART=m`, `BT_QCA=m`. Repo B forces the
cfg80211/mac80211/ath stack to `=y` and keeps BT `=m` with a 10-line comment
explaining that a built-in `hci_uart` binds `serial0-0` during initcalls, "~14ms
before init runs and about 2.7s before local-fs.target, so `request_firmware()` only
sees the initramfs — which carries no qca firmware — and QCA setup dies on ENOENT
for `hpbtfw21.tlv`. `hci_qca` does not retry, so hci0 is left DOWN with a zero BD
address and the DT `local-bd-address` never gets applied."

**Others A only** — `KEYBOARD_SAMSUNG_POGO=y` and
`# KEYBOARD_SAMSUNG_POGO_VENDOR_PORT is not set` (Repo B has no pogo);
`WLAN_VENDOR_ATH=y`, `INPUT_KEYBOARD=y` (both already `=y` in Repo B's seed);
`PHY_QCOM_QMP_USB=y`; `RPMSG=y`, `SCSI=y`, `SCSI_UFSHCD=y` (already `=y` in the seed).

### 3.2 Repo B sets, Repo A's fragment does not

**Boot / early framebuffer** — `SYSFB=y`, `SYSFB_SIMPLEFB=y` (Repo A resolved:
`# CONFIG_SYSFB_SIMPLEFB is not set`). At the top of the fragment Repo B also
**relaxes module-signature lockdown**: `# CONFIG_LOCK_DOWN_KERNEL_FORCE_INTEGRITY is
not set` and `CONFIG_LOCK_DOWN_KERNEL_FORCE_NONE=y`, with a 7-line comment: the
Fedora base config "only accepts modules carrying the signing key embedded in the
at-build-time kernel. Republishing a rebuilt kernel yields a fresh key, so the
modules shipped in the rootfs (signed for the original build) get rejected - killing
WiFi/BT." Repo A's resolved config has no `LOCK_DOWN` line; its seed is the Android
config.

**USB gadget / network (SSH)** — `USB_LIBCOMPOSITE=y`, `USB_U_ETHER=y`, `USB_F_NCM=y`,
`USB_F_RNDIS=y`, `USB_CONFIGFS_RNDIS=y`, `USB_NET_CDCETHER=y`, `USB_NET_AX8817X=y`,
`USB_NET_AX88179_178A=y`, `USB_RTL8152=y`, `HID_GENERIC=y`, `HID_LOGITECH=y` (+`_DJ`,
`_HIDPP`), `LEDS_CLASS_MULTICOLOR=y`, `SND_USB_AUDIO=y`. Repo A's fragment sets none
of them; its resolved config has `USB_CONFIGFS=y`, `USB_F_ECM=y`,
`USB_CONFIGFS_ECM=y` from the seed but no `USB_F_RNDIS`.

**Wi-Fi / pwrseq** — `PCI_PWRCTRL=y`, `PCI_PWRCTRL_PWRSEQ=y`, `POWER_SEQUENCING=y`,
`POWER_SEQUENCING_QCOM_WCN=y`, `QCOM_QMI_HELPERS=y`, `CRYPTO_LIB_ARC4=y`,
`QRTR_MHI=y`, `CFG80211=y`, `MAC80211=y`, `ATH_COMMON=y`. Repo A's resolved config
has `PCI_PWRCTRL_PWRSEQ=m`, `POWER_SEQUENCING_QCOM_WCN=m`, `QRTR_MHI` unset, and the
cfg80211/ath stack `=m`. Repo A's own `docs/WIFI_QCA6490_BRINGUP.md` records that
its Wi-Fi blocker was originally "the **missing modules** (`BUILD_MODULES=0`, so
every `=m` symbol was satisfied on paper only)" — the exact failure mode Repo B's
all-`=y` fragment makes impossible.

**Bluetooth** — `BT=y` plus `BT_BREDR`, `BT_RFCOMM`, `BT_RFCOMM_TTY`, `BT_BNEP`,
`BT_BNEP_MC_FILTER`, `BT_BNEP_PROTO_FILTER`, `BT_HIDP` (all `=y`). Repo A has
`BT=m` and none of the profile symbols.

**Touch / input / HID** — `INPUT_TOUCHSCREEN=y`, `TOUCHSCREEN_FTS1BA90A=y`,
`TOUCHSCREEN_WACOM_WEZ01=y`, `INPUT_UINPUT=y`, `UHID=y`, `QCOM_SPMI_ADC5_GEN3=y`.

**Display / GPU** — `QCOM_LLCC=y`, `# QCOM_OCMEM is not set`, `SM_GPUCC_8550=y`,
`DRM_MSM=y`, `SM_DISPCC_8550=y`, `BACKLIGHT_CLASS_DEVICE=y`,
`DRM_PANEL_SAMSUNG_ANA38407=y`, `DRM_DISPLAY_HELPER=y`, `DRM_DISPLAY_DP_HELPER=y`,
`DRM_DISPLAY_DSC_HELPER=y`. Repo A's resolved config also has `QCOM_LLCC=y`,
`SM_GPUCC_8550=y`, `SM_DISPCC_8550=y`, `DRM_MSM=y`,
`DRM_PANEL_SAMSUNG_ANA38407=y` by another route. Repo B's comment states the real
Kconfig constraint — `DRM_MSM` "depends on QCOM_LLCC/OCMEM || =n", so both must
leave `=m` or msm is capped at `=m`, and "`SM_GPUCC_8550` (not `GPUCC_SM8550`)
defaults to `=m`: this port never autoloads modules, so as a module it simply never
bound, `3d90000.clock-controller` stayed driverless and the GPU SMMU and GMU timed
out waiting for their clocks (the -110)".

**Audio** — the whole `SOUND`/`SND`/`SND_SOC`/`SOUNDWIRE`/`QCOM_APR`/`SND_SOC_QCOM`/
`SND_SOC_QDSP6`/`SND_SOC_SC8280XP`/`SND_SOC_CS35L45_I2C`/`SND_SOC_LPASS_VA_MACRO`/
`PINCTRL_LPASS_LPI`/`PINCTRL_SM8550_LPASS_LPI` block (all `=y`), plus
`GPIO_SHARED_PROXY=y` with the note that Linux 7.2 routes the four CS35L45 instances'
shared physical reset (TLMM GPIO42) through the GPIO shared-proxy driver, whose
default `=m` gives every codec `-EPROBE_DEFER`.

**Remoteproc / ADSP / FastRPC** — `QCOM_PDR_HELPERS=y`, `QCOM_PDR_MSG=y`,
`RPMSG_QCOM_GLINK_SMEM=y`, `QRTR_SMD=y`, `QCOM_FASTRPC=y`. Repo A sets `FASTRPC=y`,
`GLINK_SMEM=y` and `QRTR_SMD=y` too; Repo B additionally forces the two PDR symbols
built-in.

**Battery / charger / Type-C** — `BATTERY_SM5714=y`, `CHARGER_SM5440_DIRECT=y`,
`TYPEC=y`, `TYPEC_TCPM=y`, `TYPEC_SM5714=y`, `TYPEC_DP_ALTMODE=y`,
`TYPEC_MUX_GPIO_SBU=y`, `TYPEC_MUX_PS5169=y`. Repo A's resolved config has
`TYPEC=y`/`TYPEC_TCPM=y` from its seed but **none** of the other six — because it has
no sources for them.

**Media / VPU** — `MEDIA_SUPPORT=y`, `VIDEO_DEV=y`, `SM_VIDEOCC_8550=y`,
`VIDEO_QCOM_IRIS=y`. Repo A's DTS enables `&iris` with a firmware name but its
resolved config has `# CONFIG_SM_VIDEOCC_8550 is not set` and
`# CONFIG_VIDEO_QCOM_IRIS is not set`, so the node has no driver.

**Cameras** — `VIDEO_QCOM_CAMSS=y`, `I2C_QCOM_CCI=y`, `SM_CAMCC_8550=y`,
`VIDEO_HI1337_GTS9U=y`, `VIDEO_DW9808_VCM=y`. Repo A has none.

**Other** — `NETFILTER_NETLINK_QUEUE=m`, `NETFILTER_XT_TARGET_NFQUEUE=m`,
`NFT_QUEUE=m` (zapret's nfqws DPI bypass), `FINGERPRINT_EL721=m`,
`STAR_K250A_LEGO=m`, `QCOM_SPSS=m`, `QCOM_GLINK_SPSS=m`, `QCOM_SPCOM=m`,
`QCOM_SPSS_UTILS=m`, `QCOM_SPSS_IRQ=m`, `DMABUF_HEAPS_SP_HLOS=m`,
`# CONFIG_RUST is not set`. Repo A has `# CONFIG_RUST is not set` and
`DMABUF_HEAPS=y` and nothing else in this list.

### 3.3 Which ones plausibly matter, by the six questions asked

**(a) Boot reaching userspace.** Decisive Repo A-only block: the SM8550 provider set
its fragment documents at length — `PINCTRL_SM8550`, `MFD_SPMI_PMIC`,
`SPMI_MSM_PMIC_ARB` + `QCOM_PDC` (no PMIC at all without it: no SD card detect on
PM8550 GPIO12, no RTC, no ADC, no `usb@a600000` phy interrupts), `HWSPINLOCK_QCOM`
(SMEM defers forever → `smp2p-*` → ADSP), `SM_TCSRCC_8550` (the USB ref clocks),
`NVMEM_SPMI_SDAM` + `NVMEM_REBOOT_MODE`, `INTERCONNECT_QCOM_OSM_L3=y` (cpufreq and
gcc `sync_state()`), `QCOM_AOSS_QMP` + `QCOM_IPCC` (the GPU/GMU ACD path). Repo B
does not need to state most of these (its mainline seed has them); the one it does
**not** force, and that Repo A's documentation flags as a live defect, is
`INTERCONNECT_QCOM_OSM_L3` (`=m` in the seed, unoverridden). Repo B's extra
`SYSFB`/`SYSFB_SIMPLEFB` neither helps nor hurts boot.

**(b) Shutdown/poweroff completing.** Neither fragment contains a symbol that
plausibly causes or fixes Repo A's documented delay — that root cause is a systemd
unit waiting out the default `TimeoutStopSec=90s` (§4.2), i.e. userspace. The
kernel-side candidates on either tree are `QCOM_WDT` (A `=y`, B `=m`) and
`PANIC_TIMEOUT` (A `=0` explicitly; B's seed `=0`). Repo B's cmdline adds
`panic=10 ... watchdog.stop_on_reboot=0 softdog.soft_panic=1 ... nowatchdog`, but its
seed has `# CONFIG_SOFT_WATCHDOG is not set`, so `softdog.soft_panic=1` is **inert on
Repo B too** — the same observation Repo A's `docs/STALL_FAILURE_SHAPE.md` §4 makes
about its own tree.

**(c) Kernel log being flooded.** Repo A-only: nothing that reduces flooding
(`PRINTK_TIME` and `MAGIC_SYSRQ` are set by both). Repo B's relevant mitigation is
**not in the fragment** — it is `quiet-adsp-handover-already-happened.patch`
(§1.14) plus the cmdline's `loglevel=7 log_buf_len=4M`. Repo A's `log_buf_len` is
unset in its fragments and its example cmdlines use `loglevel=4`.

**(d) USB gadget/network (SSH).** Repo B's strongest area. It builds
`USB_LIBCOMPOSITE`, `USB_U_ETHER`, `USB_F_NCM`, `USB_F_RNDIS`, `USB_CONFIGFS_RNDIS`,
`USB_NET_CDCETHER`, three USB Ethernet drivers and `USB_RTL8152` **built-in**, so the
initramfs brings up an RNDIS gadget (`boot/dracut/90gts9wifi-usbnet/usbnet.sh`
creates `rndis.usb0` and configures `172.16.42.1/24` on `usb0`) and the rootfs then
runs `rootfs/overlay/usr/libexec/gts9wifi-usb-gadget` to switch to ECM (issue 6:
"USB debug link flaky — fixed — RNDIS gadget converted to ECM"). Repo A's fragment
sets `USB_GADGET`, `USB_CONFIGFS`, `USB_CONFIGFS_NCM`, `USB_F_NCM`, `USB_USBNET`,
`USB_NET_CDC_NCM`, `USB_STORAGE`, `USB_UAS` but **not** the ECM/RNDIS/libcomposite
set, and crucially sets `U_SERIAL_CONSOLE=y`, which Repo B has off. The two trees
chose different USB-debug transports: Repo A = ACM serial (`ttyGS0` shell + `ttyGS1`
kernel console), Repo B = ECM/RNDIS network.

**(e) Wi-Fi.** Repo A-only: `WLAN_VENDOR_ATH=y`, `PHY_QCOM_QMP_USB=y` and the whole
modules-based ath11k/`CFG80211=m` arrangement. Repo B-only: `PCI_PWRCTRL=y`,
`PCI_PWRCTRL_PWRSEQ=y`, `POWER_SEQUENCING=y`, `POWER_SEQUENCING_QCOM_WCN=y`,
`QCOM_QMI_HELPERS=y`, `CRYPTO_LIB_ARC4=y`, `QRTR_MHI=y` and the cfg80211/mac80211/
ath11k stack `=y`. Repo B's arrangement is safer for a port with no module autoload;
Repo B's remaining risk is the stable-kernel delta (issue 20), not the config. Repo A
has verified end-to-end Wi-Fi on `7.2.0-rc3` with modules.

**(f) Display.** Repo A-only: `FONTS=y` + `FONT_TER16X32=y` (for readability on the
2560x1600 panel), `LTO_NONE`, and the `DRM`/`DRM_MSM`/`DRM_SIMPLEDRM`/
`DRM_FBDEV_EMULATION`/`FB`/`FRAMEBUFFER_CONSOLE` block. Repo B-only: `SYSFB=y`,
`SYSFB_SIMPLEFB=y` (Repo A has `SYSFB_SIMPLEFB` off — relevant because neither
`/chosen` has a simple-framebuffer and Repo B relies on the bootloader splash until
the DPU comes up), `DRM_DISPLAY_DP_HELPER=y`, `DRM_DISPLAY_DSC_HELPER=y`,
`BACKLIGHT_CLASS_DEVICE=y`, `SM_DISPCC_8550=y`. Both set
`DRM_PANEL_SAMSUNG_ANA38407=y`, `DRM_MSM=y`, `DRM_FBDEV_EMULATION=y`, `FB=y`,
`FRAMEBUFFER_CONSOLE=y`. Repo B's `SM_DISPCC_8550=y` is justified in its comment
("defaults to =m ... this port never autoloads modules, so force it built-in or the
mdss/dsi never get their clocks"); Repo A reaches `=y` by another route.

---

## 4. This repository's open problems, and what the Fedora port does about them

### 4.1 `docs/BOOT_CONSOLE_BLOCK.md`
**Open.** (i) After a reboot the panel sits on the boot log for tens of seconds to
minutes; `getty@tty1` accepts keystrokes before login, then input freezes and the
power key stops blanking; the screen clears to a lone cursor; the SoC gets warm;
opening COM19 recovers it immediately. (ii) Measured cause: a **userspace**
`write()` to `/dev/console` blocking in `n_tty_write()` → `gs_write()` on
`tty->write_wait` when the gadget's OUT requests are full; `printk` itself is lossy
by design (0.048 s for 5000 lines with COM19 closed) and never blocks. (iii)
`/dev/console` resolves to `ttyGS1` (COM19) because the kernel gives it to the last
`console=` that registers and `ignore_console_null` drops the trailing
`console=null`. (iv) The fix has three parts and the third is an **explicitly
undecided trade-off**: keep the PID 1 fallback shell off `/dev/console`; drop
`journal+console` from `gts9-prev-boot-evidence.service` (done); and decide whether to
keep `console=ttyGS1` or drop it so `gts9-kmsg-console` can mirror `/dev/kmsg` from
userspace with error handling. Recorded workaround: keep COM19 open across the boot.

**Repo B.** Nothing addresses the blocking mechanism, but **avoids the trigger**:
its `boot/cmdline.txt` is `console=tty0 console=ttyMSM0,115200n8 ignore_console_null
earlycon ... console=null` — **no `console=ttyGS*`** — and its config has
`# CONFIG_U_SERIAL_CONSOLE is not set` where Repo A sets `=y`. Repo B's debug channel
is a network gadget (`USB_F_RNDIS`/`USB_U_ETHER`/`USB_NET_CDCETHER` +
`gts9wifi-usb-gadget` switching to ECM), so no `/dev/console` maps onto a gadget
serial port. I grepped Repo B `rootfs/` and `boot/` for `ttyGS` and `getty`: **no
matches**. So Repo B sidesteps (iii)/(iv) rather than solving them, and the decision
Repo A records as open is already made in Repo B's favour — at the cost of the
kernel-log-over-USB path.

### 4.2 `docs/SHUTDOWN_DELAY.md`
**Open.** `poweroff` prints "The system will power off now!" then sits with a blinking
cursor for up to ~90 s before the rails drop. Cause: `gts9-acm-getty.service` runs
`agetty --autologin root ... ttyGS0`; `--autologin` spawns a login shell that is not
reaped on `SIGTERM`, the unit's cgroup stays populated, systemd waits out the default
`TimeoutStopSec=90 s` then escalates (`State 'stop-sigterm' timed out. Killing.` /
`Killing process 1456 (login) with signal SIGKILL.`). Intermittent; correlates with
having recently used the serial console. Fix `TimeoutStopSec=3` in `[Service]` (not
`[Unit]`, which systemd silently ignores), applied to `rootfs-overlay/` and pushed to
`/etc/` after the two copies had diverged. Explicitly **not investigated**: whether
`Restart=always` also contributes.

**Repo B.** Nothing equivalent, and nothing needed: Repo B has **no
`gts9-acm-getty.service`** and no `ttyGS` getty at all (same grep). Its console is
`tty0` + `ttyMSM0` and its debug channel is the ECM/RNDIS network gadget, so the unit
that causes the 90 s wait does not exist. Another avoid-rather-than-fix.

### 4.3 `docs/GPU_GMU_RPMH_STALL_PLAN.md` (summary/status)
**Open.** (i) The GPU init chain was broken at a known point: `a6xx_gmu_acd_probe()`
needs `gmu->qmp` from `aoss_qmp`; without `CONFIG_QCOM_AOSS_QMP` **and**
`CONFIG_QCOM_IPCC` `qmp_get()` returns `-EPROBE_DEFER` forever, the ACD probe returns
`-EINVAL`, and `a6xx_gmu_init()`'s error path calls `device_link_del()` on a *managed*
link → `WARN(1, "Unable to drop a managed device link reference")` in
`drivers/base/core.c:1020`. Fixed on Repo A by config. (ii) A **live upstream bug on
the vote path**: `a6xx_rpmh_stop()` has an inverted
`test_and_clear_bit(GMU_STATUS_FW_START)` in the pinned tree, so every GPU runtime
suspend skips the RSCC power-off handshake, PDC sleep is never armed, and stale RPMh
(BCM) votes remain. Carried as a **candidate, not applied**, in
`kernel/patches/pending/0008-drm-msm-a6xx-fix-stale-rpmh-votes-after-suspend.patch`
("one variable per experiment"). (iii) §11b: the watchdog recovery guarantee is
**falsified** — one instance panicked and restarted at ~45 s, a second never fired
and wedged indefinitely, so unattended A/B series are no longer acceptable.

**Repo B.** For (i): its seed already has `QCOM_AOSS_QMP=y` and `QCOM_IPCC=y` (and
its fragment does not repeat `QCOM_AOSS_QMP`), so the permanent-defer corner is not
reachable by that route. Repo B has **no** equivalent of Repo A's
`0007-drm-msm-adreno-a6xx-mark-cxpd-device-link-stateless.patch` (the upstream
`DL_FLAG_STATELESS` backport) — no `a6xx_gmu.c` change anywhere in its patches — so
if it ever reached that error path it would still emit the warning pair. For (ii):
**nothing** — no `a6xx_rpmh_stop` change in `kernel/patches/`, and its
`docs/Hardware-Notes.md` does not mention GMU RPMh votes (grep for `rpmh`/`gmu`/
`stall`/`wedge` across Repo B `docs/` found only a GPU-firmware `install_items`
note). For (iii): `docs/Known-Issues.md` has no stall or wedge entry, and its
cmdline's `softdog.soft_panic=1` is inert because its config has
`# CONFIG_SOFT_WATCHDOG is not set` — so Repo B has neither a watchdog guarantee nor
a documented falsification of one.

### 4.4 `docs/CPU_WEDGE_EVIDENCE.md` (summary)
**Open.** (i) The stall is a **CPU-level wedge**, evidenced by four messages
(`After 10 seconds, these CPUS still haven't responded to the NMI`,
`rcu: INFO: rcu_preempt detected stalls`, `BUG: workqueue lockup`,
`watchdog: BUG: soft lockup`) on 11 boots of 88 retained. (ii) The rate: pre-fix
10/46 (21.7 %, CI 12.3–35.6 %) vs post-fix 1/29 (3.4 %, CI 0.6–17.2 %), two-sided
Fisher exact **p = 0.043** — explicitly *not* proof of attribution, because the fix
and the era boundary coincide by construction and the user declined putting a pre-fix
kernel back. (iii) The "10 seconds" wording overstates the timeout:
`CONFIG_ARM64_PSEUDO_NMI` is unset on this build, so it is a **regular IPI**
backtrace, which is a *stronger* statement than "NMI broken". (iv) Not window-bound:
wedges at 7 s, 50 s and later (`last` 36.7–496.8 s); the "13–14 s window" was an
artefact of when a host was watching. (v) **What it does not establish**: why a CPU
stops. The arm64 short list is a CPU parked with interrupts masked, an SError, or a
PSCI `CPU_SUSPEND` that never returns; the platform evidence (`cpuidle` driver
`psci_idle`, `state1 cpu-sleep-0-0` `usage=91839 time=1196 s`, ~92 % of CPU time in
rail power collapse at ~70 entries/s, no failed suspends reported) points at the last
but cannot confirm it. (vi) **Two X710-only config leads inherited from the stock
seed rather than chosen**: `CONFIG_CPU_IDLE_THERMAL=y` and
`CONFIG_CPU_IDLE_GOV_TEO=y`, neither in Repo A's fragment; the cheap experiment is
disabling `cpuidle/state1` at runtime or `cpuidle.off=1`. (vii) Round-21 caution:
"the journal stops at ~7 s" ≠ "the system froze" — one live capture showed the kernel
still printing 19 s after its journal and serial console went quiet because the
rootfs `mmc1` controller stopped answering (`Int stat: 0x00000000`,
`Resp[0..3] = 0`); the freeze-fingerprint set (10 boots) and the
unanswered-backtrace set (11 boots) have never been intersected.

**Repo B.** Nothing for the wedge itself: `docs/Known-Issues.md` has no wedge entry,
`docs/Hardware-Notes.md` mentions no stall, and no patch touches cpuidle, PSCI, RCU
or the scheduler. Three visible but non-answering differences: (a) Repo B's seed has
`# CONFIG_CPU_IDLE_GOV_TEO is not set` (Repo A resolved: `CONFIG_CPU_IDLE_GOV_TEO=y`),
so the "teo is X710-only" lead does **not** reproduce on Repo B as a symbol — and
`CPU_IDLE_THERMAL` is absent from Repo B's seed and fragment too, so that half of the
lead is also absent; (b) Repo B boots from **internal UFS** (`README.md`: "a Fedora
root on the internal UFS storage"; `boot/bootconfig.txt:
androidboot.boot_devices=soc/1d84000.ufshc`) whereas Repo A boots from the microSD
(`aliases { mmc1 = &sdhc_2; }`), so the `mmc1`-controller observation in (vii)
describes a path Repo B does not use — though Repo B's fragment does set
`SCSI_UFS_QCOM=y`/`PHY_QCOM_QMP_UFS=y` built-in for exactly that reason; (c) Repo B
forces no `CPU_IDLE` symbols either way. So Repo B has no diagnosis, no mitigation
and no shared evidence.

### 4.5 `docs/STALL_FAILURE_SHAPE.md` (summary)
**Open.** (i) A live second-resolution host capture of a confirmed failure existed
since test-184 unrecognised: a shutdown ran **23 lines in 0.828 s** then went silent
for **28.903 s**, with **31.174 s** from the first `Stopping` to the device leaving
the bus, **zero** `systemd-shutdown` lines and no panic/lockup banner; the kernel was
alive (the `usb0525:a4a7` gadget stayed enumerated throughout), userspace had
stopped, then something reset the machine. (ii) Refutes "orderly fast shutdown" and
"`reboot -f`"; confirms "a genuine hang whose journal simply stops". (iii) **Nothing
in mainline reset it**: Repo A's `sm8550.dtsi` has no `wdt`/`watchdog` node at all (I
confirmed this at v7.2-rc3), `CONFIG_SOFTDOG` is unset so the ABL-injected
`softdog.soft_panic=1` is inert, `CONFIG_ARM_SMC_WATCHDOG`/`CONFIG_PMIC_WATCHDOG`
are unset and systemd's runtime watchdog is not armable. Leading unnamed candidate:
**`qcom,gh-watchdog`** (the Gunyah hypervisor watchdog stock firmware uses), which
nothing measures and which is out of scope. (iv) The other episode ends at
`enc35 frame done timeout` (`DPU_ERROR_ENC_RATELIMITED("frame done timeout")`) with a
known trigger (a full modeset); the association is 2-for-2 but small — "the A-5
failure proves the message is **not necessary** for the failure". (v) Why it was
missed for five rounds: the classifier grepped for banners (`soft lockup|hung_task|
workqueue: stall|Kernel panic|rpmh_write_batch|frame done timeout`) and the failure
emits none — "the absence of a line is the signal". (vi) Archive-name trap: the
collector names each directory after the boot that *creates* it, so `…-8d7db274/`
describes the boot *before* `8d7db274`; older documents cite the survivor as the
failure. Both fixes recorded (collector now writes `previous_boot_id=`; harnesses
select by boot id, because `date -u` is frozen and all eight retained directories
share an mtime within one second). (vii) Still open: whether the Gunyah hypervisor
watchdog resets the machine ~29 s in; whether this failure is the one the current
kernel no longer produces; whether the shutdown-time and while-running episodes are
one phenomenon; whether the two archived failures are the same phenomenon.

**Repo B.** Nothing mechanical. No watchdog driver, no `qcom,gh-watchdog` node (its
DTS derives from the same upstream `sm8550.dtsi`, which has no `wdt`/`watchdog` node
at v7.2-rc3), no `CONFIG_SOFTDOG`, no stall/shutdown-hang documentation. Its only
related artefact is the cmdline `watchdog.stop_on_reboot=0 softdog.soft_panic=1 ...
nowatchdog`, and `softdog.soft_panic=1` is inert there too
(`config-mainline.aarch64:5305` is `# CONFIG_SOFT_WATCHDOG is not set`). Its
`docs/Known-Issues.md` "Also outstanding" list has the closest thing: "the
`gts9wifi-adsp-boot.service` ships disabled: starting the ADSP late can hang or reset
the SoC, and it needs root-causing" — an ADSP-related hang, not the same failure.
Repo B's `docs/Hardware-Notes.md` was grepped for `stall`, `wedge`, `soft lockup`,
`frame done`, `hung task`, `rpmh`, `gmu`, `watchdog`, `poweroff`, `shutdown`: none
present.

---

## 5. Out-of-tree drivers

`kernel/files/` is copied into the tree by `prepare.sh`, which appends a Kconfig
block and a Makefile line per driver if the symbol is absent.

| File | Purpose | Repo A |
|---|---|---|
| `config-gts9wifi.fragment` | board Kconfig fragment (§3) | `kernel/config/gts9wifi-mainline.fragment`, different content |
| `config-mainline.aarch64` | pmOS mainline seed → `.config` | **different implementation**: Repo A merges over the byte-verified stock Samsung 5.15.153 Android config; it has no mainline seed file |
| `sm8550-samsung-gts9wifi.dts` | board DTS (§2) | `kernel/dts/sm8550-samsung-gts9wifi.dts`, same board |
| `panel-samsung-ana38407.c` (32 KB) | ANA38407 AMSA10FA01 2560x1600 command-mode DSI panel, DSC 1.1, FOD HBM sequence, cell id | **same driver, divergent revision**: Repo A's 31 KB copy adds 60 Hz and 30 Hz modes ("All three timing modes from the stock DTBO"; Repo B has 120 Hz only), keeps the panel-id log at `dev_info` as an interface ("boot/bringup-init.sh greps dmesg for `ana38407 panel id: 00 00 00`"), guards `ctx->prepared`/`ctx->enabled` on regulator errors, keeps `ctx->dsi->dsc` rather than `ctx->dsc`, and uses named `ana38407_slew_boost()`/`ana38407_set_120hz()` helpers where Repo B inlines. Neither is a superset |
| `fts1ba90a.c` (19 KB) | STM FTS1BA90A touchscreen (`st,fts1ba90a`) | **nothing** — Repo A's DTS binds the node to a driver absent from the tree |
| `wacom-wez01.c` + `wacom_wez01.h` | Wacom WEZ01 EMR digitizer (`wacom,w90xx`) + shared pen-proximity/palm-rejection header | **nothing** |
| `sm5714_battery.c` (37 KB) | SM5714 charger + fuel gauge (`siliconmitus,sm5714`); fixed issue 1 (float voltage → 96 % cap) | **nothing** — node present, driver absent |
| `sm5714_usbpd.c` (26 KB) | SM5714 Type-C/PD transport (`siliconmitus,sm5714-usbpd`), a TCPM `tcpc_dev`; Linux TCPM owns policy | **nothing** — Repo A's `dr_mode` comment says outright "there is no mainline driver" |
| `sm5440_direct.c` (28 KB) | SM5440 2:1 direct charger (`siliconmitus,sm5440`), asks TCPM for PPS | **nothing** |
| `ps5169.c` (9 KB) | Parade PS5169 USB3/DP Type-C redriver (`parade,ps5169`), mux + retimer + orientation switch | **nothing** — `docs/DT_PROVIDER_AUDIT.md`: "`parade,ps5169` \| *(none)* \| ... no driver source declares it in this tree at all" |
| `hi1337_gts9u.c` + `hi1337_gts9u_tables.h` (38+38 KB) | Hynix HI1337 sensor, `hynix,hi1337-gts9u-{rear,front,front-uw}` | **nothing** |
| `dw9808_vcm.c` (8 KB) | Dongwoon DW9808 V4L2 lens VCM (`dongwoon,dw9808-vcm`) | **nothing** |
| `egis_el721.c` (26 KB) | EgisTec EL721 under-display fingerprint: only the power/reset/metadata half in Linux plus Samsung's non-data ioctl ABI on `/dev/esfp0`; registers its own platform device because "Samsung's ABL does not tolerate the GPIO description in the DTB" | **nothing** |
| `snvm/` (19 files: `Kconfig`, `Makefile`, `sec_k250a.c`, `sec_star.c/.h`, `snvm_wakelock.h`, `hal/ese_{hal,i2c,spi}.c/.h`, `protocol/ese_{data,iso7816_t1,memory}.c/.h`, `protocol/ese_{error,log,protocol}.h`) | Samsung K250A secure element (`STAR_K250A_LEGO`): self-contained eSE stack, ISO7816 T=1 protocol layer + i2c/spi HAL, creates its own i2c client (`i2c@888000` via `of_changeset`) and votes PM8550VS LDO G2 (`ldog2`) over public RPMh; `/dev/k250a` | **nothing** |
| `spu/qcom_spss.c`, `qcom_glink_spss.c`, `spcom.c`, `spss_utils.c`, `qcom_spss_irq.c`, `qcom_sp_hlos_heap.c` | SPSS/SPU stack: PAS remoteproc booting `spss1p.mdt` (PAS id 14), GLINK transport, `/dev/spcom`, `/dev/spss_utils`, `/dev/qsee_ipc_irq_spss`, and the DMA-buf heap the SPU shares buffers through | **nothing** |
| `spu/include/linux/remoteproc/qcom_spss.h`, `spu/include/uapi/linux/spcom.h`, `spu/include/uapi/linux/spss_utils.h` | headers for the above (uapi installed into `include/uapi/linux/`) | **nothing** |
| `spu/spss-irq/Makefile`, `spu/spss-irq/README.md` | standalone build recipe for the experimental `qsee_ipc_irq_spss` bridge plus design notes (IPCC client 16, signal 1, rising edge; root-only single reader; `poll()` acknowledges; no `POLLRDHUP`; validated on Ubuntu `7.2.0-rc3-dirty` under lockdown) | **nothing** |

Also part of Repo B's out-of-tree set but carried as patches, not files here: the
three `drivers/tee/qcomtee/` changes (§1.12/§1.13).

**Reverse direction — Repo A's own out-of-tree sources.** `kernel/drivers/` holds
`keyboard-samsung-pogo.c` (64 KB, STM32 pogo keyboard, `samsung,x710-pogo-keyboard`,
`CONFIG_KEYBOARD_SAMSUNG_POGO`), `panel-samsung-ana38407.c` (above),
`samsung-gts9wifi-sec-log.c` (49 KB, much larger than Repo B's inline 139-line copy),
and `input/samsung-pogo/` (13 files: `stm32_pogo_{cmd,core,fn,fw,i2c,interrupt}_v3.c`,
`stm32_pogo_v3.h`, `pogo_notifier_v3.h`, `samsung_pogo_{compat.h,stubs.c}`,
`Kconfig`, `Makefile`, `README.md`), installed **only** when
`GTS9_INSTALL_VENDOR_POGO=1` as a reference-only manual A/B. **None has any
counterpart in Repo B.**

---

## 6. Build systems

### 6.1 `kernel/prepare.sh` (268 lines)
1. `set -euo pipefail`; takes the tree as `$1`, resolves `$here`, `cd`s in.
2. **Patches**: `for p in "$here"/patches/*.patch; do patch -p1 --forward < "$p"; done`
   — one batch, lexical order, no `--check` pass first, no already-applied detection
   beyond `--forward`.
3. **Board DTS**: `cp files/sm8550-samsung-gts9wifi.dts
   arch/arm64/boot/dts/qcom/`, then appends the `dtb-` line only if the Makefile does
   not already mention `gts9wifi` ("`add-gts9wifi-dtb.patch` normally handles this").
4. **Out-of-tree drivers**, each the same shape (`cp`, `grep -q` the symbol then
   `sed -i` or append a Kconfig block, `grep -q` the object then append a Makefile
   line). A local `register_driver()` helper is defined but never called; every
   driver is spelled out. In order: `panel-samsung-ana38407.c` →
   `drivers/gpu/drm/panel/` (Kconfig inserted before `^endmenu$`, `depends on OF /
   DRM_MIPI_DSI / BACKLIGHT_CLASS_DEVICE`); `fts1ba90a.c` → `drivers/input/touchscreen/`
   (`select INPUT_MT`); `wacom-wez01.c` → same dir; `wacom_wez01.h` →
   `include/linux/`; `sm5714_battery.c` and `sm5440_direct.c` →
   `drivers/power/supply/`; `sm5714_usbpd.c` → `drivers/usb/typec/tcpm/`
   (`depends on TYPEC_TCPM`, `BATTERY_SM5714`); `ps5169.c` →
   `drivers/usb/typec/mux/`; `hi1337_gts9u.c` + tables and `dw9808_vcm.c` →
   `drivers/media/i2c/`; `egis_el721.c` → `drivers/misc/`; `snvm/` →
   `drivers/misc/snvm/` with a two-symbol Kconfig block (`STAR_K250A_LEGO`,
   `SEC_SNVM_WAKELOCK_METHOD`); the six `spu/` sources → `drivers/remoteproc/`,
   `drivers/rpmsg/`, `drivers/soc/qcom/`, `drivers/dma-buf/heaps/` with four Kconfig
   blocks (`QCOM_SPSS`, `QCOM_GLINK_SPSS`, `QCOM_SPCOM` + `QCOM_SPSS_UTILS` +
   `QCOM_SPSS_IRQ`, and `DMABUF_HEAPS_SP_HLOS` **appended** because
   `drivers/dma-buf/heaps/Kconfig` is a fragment with no `endmenu`) and three
   Makefile lines; three headers into `include/linux/remoteproc/` and
   `include/uapi/linux/`.
5. **localversion**: `echo "-gts9wifi" > localversion-gts9wifi`.
6. **Config**: `cp files/config-mainline.aarch64 .config`; `merge_config.sh -m .config
   files/config-gts9wifi.fragment`; `unset LDFLAGS; make ARCH=arm64 LLVM=1
   olddefconfig`.
7. Prints `make ARCH=arm64 kernelrelease`.

### 6.2 `kernel/kernel.spec` (68 lines)
`%define flavor gts9wifi`, `%define debug_package %{nil}`, `%define kversion 7.2.0`;
`Name: linux-gts9wifi`, `Version: 7.2.0`, `Release: 0.1%{?dist}`,
`BuildArch`/`ExclusiveArch: aarch64`, `Provides: kernel-uname-r`, `AutoReqProv: no`;
`Source0: linux-prepared.tar.gz` — `prepare.sh` has **already run** when rpmbuild
sees the tree (the workflow does it); `%prep` is `%setup -q -n linux-prepared`.
`%build`: `unset LDFLAGS` then one
`make ARCH=arm64 LLVM=1 %{?_smp_mflags} KBUILD_BUILD_VERSION="%{release}.%{flavor}"`
— no explicit target, so the default `all` (built-ins only).
`%install`: `krel=$(make ARCH=arm64 kernelrelease)`, then `make ARCH=arm64 LLVM=1
modules_install dtbs_install INSTALL_MOD_PATH=%{buildroot}/usr
INSTALL_DTBS_PATH=%{buildroot}/boot/dtbs-%{kversion}-%{flavor} INSTALL_MOD_STRIP=1`,
then `install -Dm0644 arch/arm64/boot/vmlinuz.efi %{buildroot}/boot/vmlinuz-$krel`
and `System.map`. The comment explains **why not `make zinstall`**: "zinstall routes
through the build host's installkernel/kernel-install hooks, and the rolling Fedora
44 CI container grew a 50-dracut.install that fails hard inside rpmbuild (no
/lib/modules at the container root). The hook chain produced nothing beyond these two
files anyway." Then `depmod -b %{buildroot}/usr -a %{kversion}-%{flavor}` and
`rm -f %{buildroot}/usr/lib/modules/*/build .../source`; `%files` is `%license
COPYING`, `/boot/*`, `/usr/lib/modules/*`. The `%changelog` records the pin:
"Rebase onto the 7.2 stable release. The 7.2.6 kernel loses the WCN6855 MHI power-up
deterministically (BHI load fails) with no delta in the port itself; 7.2 is the base
while that regression is chased separately."

### 6.3 ccache
**Repo B installs ccache and does not use it.** `.github/workflows/kernel.yml:54`
(`dnf -y install ... ccache ...`) but the only build invocations are
`bash /work/kernel/prepare.sh .` and `rpmbuild -bb ... /work/kernel/kernel.spec`, and
`kernel.spec` uses plain `make ARCH=arm64 LLVM=1`. I grepped the whole repo for
`ccache`, `CC=`, `LLVM=1`, `CROSS_COMPILE`: four hits only — the `dnf install` line
and the three `LLVM=1` make lines; nothing sets `CC="ccache clang"`. The workflow's
only caching is `mkdir -p /tmp/kcache` around the kernel tarball download inside the
same container run, which starts fresh each time, so a rebuild recompiles from
scratch.
**Repo A uses ccache deliberately** (`scripts/build-kernel.sh:19-42`):
`USE_CCACHE=auto` default, `CCACHE_DIR` kept **outside** the build tree
(`$workdir/ccache`) so `KERNEL_CLEAN=1` does not delete it, `CCACHE_BASEDIR`,
`CCACHE_SLOPPINESS=include_file_ctime,include_file_mtime` with an explicit note that
`time_macros` is **deliberately not set** because it "made the same source produce a
different `Image.gz` than a non-ccache build", and
`ccache_args=(CC="ccache clang")` passed to `make`. `USE_CCACHE=1` without ccache is
a hard error, not a silent fallback.

### 6.4 Config seed, fragment merge, forced symbols
| step | Repo B | Repo A |
|---|---|---|
| seed | `cp config-mainline.aarch64 .config` | `materialize-stock-config.sh` base64-decodes five `reference/stock/config/…partNN`, verifies a gzip sha256 **and** a raw sha256 → `SM-X710-stock-5.15.153.config` |
| merge | `merge_config.sh -m .config fragment` | `merge_config.sh -m -O "$build_dir" "$stock_cfg" "$fragment"` |
| resolve | `unset LDFLAGS; make ARCH=arm64 LLVM=1 olddefconfig` | `make -C "$tree" O="$build_dir" ARCH=arm64 LLVM=1 olddefconfig` |
| post-merge checks | **none** | 40+ `required=()` must be `=y`, 7 `required_m=()` must be `=m`, `KEYBOARD_SAMSUNG_POGO=y` set, `KEYBOARD_SAMSUNG_POGO_VENDOR_PORT=y` **not** set, `PANIC_TIMEOUT=0` — each failure exits 1 |
| release string | `echo "-gts9wifi" > localversion-gts9wifi` | `CONFIG_LOCALVERSION="-gts9wifi"` + `# CONFIG_LOCALVERSION_AUTO is not set`, plus `printf '0\n' > "$build_dir/.version"` |
| fixed inputs | none | `KBUILD_BUILD_USER`, `KBUILD_BUILD_HOST`, `SOURCE_DATE_EPOCH` from the pinned commit, `KBUILD_BUILD_TIMESTAMP` |
| targets | `make ARCH=arm64 LLVM=1` (default `all`) | `make -C "$tree" O="$build_dir" ARCH=arm64 LLVM=1 Image.gz qcom/sm8550-samsung-gts9wifi.dtb [modules]` |

Repo A does not *force* symbols; it **verifies** them after `olddefconfig` and aborts
if one was dropped — the same failure class its fragment documents ("olddefconfig
silently dropped symbols requested above (AGENT.md rule 7)"). **Repo B has no
post-`olddefconfig` verification anywhere**, so a silently dropped symbol would go
unnoticed until a device failed to appear at runtime.

### 6.5 What Repo A's build does that Repo B's does not
* **Idempotent re-preparation**: `prepare-kernel.sh` starts with `git checkout -- .`
  + `git clean -fdq -- arch drivers include`, detects already-applied patches with
  `git apply --reverse --check`, and distinguishes "already applied" from "failed".
* **A worktree-integrity gate**: it enumerates `git diff --name-only` and refuses to
  build if any modified tracked file is not claimed by a queued patch ("refusing to
  build: the worktree carries changes no queued patch claims"), because "a patch that
  is dropped from the queue is *not* reverted by `git apply`, so a reused worktree
  silently keeps building it."
* **Opt-in diagnostic patching**: `GTS9_POWEROFF_TRACE=1` and `GTS9_RPMH_DEBUG=1`
  apply `diagnostic/0020-*` and `0021-*` on top of the default queue;
  `GTS9_INSTALL_VENDOR_POGO=1` installs the vendor import and inserts a `source` line
  into `drivers/input/keyboard/Kconfig` with a Python snippet.
* **Pinned-source verification**: `fetch-mainline.sh` clones `v7.2-rc3` and **fails**
  unless `HEAD == a13c140cc289c0b7b3770bce5b3ad42ab35074aa`.
* **ccache, as above.**
* **Reproducibility and provenance guards**: `SOURCE_DATE_EPOCH` from the pinned
  commit, `printf '0\n' > .version`, a `SHA256SUMS` over
  `Image.gz`/DTB/`config`/`kernel.release`, and the flashed-image guard that refuses
  to overwrite an `Image.gz` whose sha256 appears in an
  `out/boot-bundle-*/BUNDLE_INFO` (`GTS9_ALLOW_IMAGE_REPLACE=1` opts out; otherwise
  it keeps an `Image.gz.flashed-<timestamp>` copy).
* **Out-of-tree build directory**: Repo A uses `O="$build_dir"` and keeps the source
  worktree free of generated Kconfig state; Repo B builds in-tree.

### 6.6 What Repo B's build does that Repo A's does not
* **Produces an RPM** with `modules_install`, `dtbs_install`, `INSTALL_MOD_STRIP=1`
  and `depmod -b`, explicitly avoiding `make zinstall` for the reason quoted above.
* **Builds the whole deliverable chain in one workflow run**: downloads and
  sha256-verifies a firmware payload, installs the RPM into the container, copies in
  a dracut module (`90gts9wifi-usbnet`) and `dracut.conf.d/gts9wifi.conf`, runs
  `dracut --kver "$KVER" --force`, builds the Android boot-image-v4 bundle with
  `boot/build-bundle.sh --vmlinuz --dtb --initramfs --cmdline --bootconfig`, packs a
  TWRP zip with `tools/make-twrp-zip.py`, and publishes to a GitHub release. Repo A
  has separate scripts (`build-boot-bundle.sh`, `build-bringup-initramfs.sh`,
  `make-initramfs.sh`, `validate-boot-bundle.sh`, `flash-boot.sh`) and no RPM.
* **Builds on native arm64** (`runs-on: ubuntu-24.04-arm`, `timeout-minutes: 120`)
  inside a pinned `quay.io/fedora/fedora:44` container, matching the target
  userland's toolchain.

---

## 7. What is worth taking, and what is not

### 7.1 Worth taking
1. **`quiet-adsp-handover-already-happened.patch`** (§1.14). One line, `dev_err` →
   `dev_dbg`, against a measured 99.98 % log-ring occupancy at 5.4 Hz. Repo A has no
   equivalent, and its own `docs/BOOT_CONSOLE_BLOCK.md` shows how much time this
   project loses to log-volume problems. Highest value per line in either tree.
2. **The `&scm` interrupt-cells correction** (§2.10) — the *reverse* direction, i.e.
   worth telling Repo B. Repo A's
   `interrupts = <GIC_SPI 930 IRQ_TYPE_EDGE_RISING 0>` is correct for SM8550's
   `#interrupt-cells = <4>`; Repo B's three-cell form makes `of_irq_parse_one()` fail
   with `-ENODATA` and silently drops the SCM waitqueue interrupt. Verified against
   `.work/linux-mainline/arch/arm64/boot/dts/qcom/sm8550.dtsi`.
3. **The `drivers/tee/qcomtee` SPSS heap work** (§1.12/§1.13) **only if** Repo A ever
   wants the fingerprint/secure-element path — it currently has `# CONFIG_TEE is not
   set`, so none of it is reachable. The reusable facts are the
   `TEE_DMA_HEAP_SPSS_SHARED` / `"qcom,secure-sp-tz"` mapping and the
   `qcom_scm_assign_mem(..., HLOS, {VMID_CP_SPSS_SP_SHARED, RW})` sequence; the
   `qcom_tzmem` pool rework is specific to a dualfp workload Repo A does not run.
4. **Repo B's driver sources for the nodes Repo A's DTS already describes but cannot
   bind**: `fts1ba90a.c`, `wacom-wez01.c` + header, `sm5714_battery.c`,
   `sm5714_usbpd.c`, `sm5440_direct.c`, `ps5169.c`, `hi1337_gts9u.c` + tables,
   `dw9808_vcm.c`, and the `snvm/` and `spu/` trees. `docs/DT_PROVIDER_AUDIT.md`
   lists every one of these compatibles as parked or out of scope; taking them is the
   difference between a DTS that describes the board and a board that works.
5. **`set-mi2s-codec-dai-format.patch`** (§1.15). Repo A has the same
   `qcom,sm8450-sndcard` + CS35L45 `PRIMARY_MI2S_RX` wiring and no
   `SND_SOC_SC8280XP` in its fragment, so "the codec produced no audio at all" is
   reachable and undiagnosed on Repo A.
6. **Repo B's BT-firmware-timing rationale** (§3.2). Repo A builds
   `BT_HCIUART=m`/`BT_QCA=m` for compatible reasons but has not recorded the
   measurement (built-in `hci_uart` binds `serial0-0` ~2.7 s before
   `local-fs.target`, so `request_firmware()` sees only the initramfs and `hci_qca`
   dies on `ENOENT` for `hpbtfw21.tlv` without retrying). Worth adopting verbatim as
   documentation.
7. **Repo B's all-`=y` discipline and Repo A's `required`/`required_m` assertion
   list** — each tree should take the other's half. Repo B forces the visible roots
   built-in because it has no module tree; Repo A verifies its symbols after
   `olddefconfig`. Repo A's own Wi-Fi post-mortem ("the Wi-Fi blocker is a
   missing-module problem", `scripts/stage-wifi-modules.sh`) and Repo B's (issue 20
   preamble: the flashed image was correct, the modules were not staged) are the same
   lesson learned independently.
8. **Repo B's `docs/Known-Issues.md`** — a numbered, stable issue register with
   fixed/planned/open status per item. Repo A's documentation is far richer per topic
   but has no single index of what is actually open.

### 7.2 Not worth taking
1. **`match-samsung-sm8550-eusb2-phy-init.patch`** (§1.8). Repo A tested and
   **rejected** it: `kernel/patches/pending/snps-eusb2-match-samsung-sm8550-init.patch`,
   disposition `REJECTED ON X710`, with the measured result that with it "the kernel
   never reached userspace and no gadget appeared on the host at all" versus a
   host-visible `VID_0525&PID_A4A7` without it, and the note that the sequence "is the
   right sequence for the X910's PHY configuration and wrong for this one". Repo A
   fixed its equivalent symptom with the PTN3222 register overrides, which both trees
   now carry. **This is a regression risk for Repo B, not a gain for Repo A.**
2. **`expose-separate-gpu-kms-resources.patch`** (§1.5). It exists to satisfy Xorg's
   modesetting driver against a render-only GPU node. Repo A drives a native
   command-mode panel through the separate DPU card and its display recovery is built
   around the DPU/DSI card and the panel-id log, so adding `DRIVER_MODESET` to the GPU
   instance would create a second modeset-capable DRM device with no CRTCs and risk
   changing which node fbcon/`/dev/fb0` binds to — the exact interaction Repo A's
   `/chosen` comment warns about.
3. **Repo B's `sec-pmsg@880900000` region with no `compatible`** (§2.8). Repo A's
   `ramoops` node is the correct mainline binding for the same carve-out and carries
   the measured negative result plus the instruction not to treat `/sys/fs/pstore` as
   evidence. Replacing it with an inert anonymous reservation would lose information
   and gain nothing.
4. **`build-wcn-pcie-providers-in.patch` as a Kconfig change** (§1.3). Repo A
   deliberately ships modules and its resolved config keeps
   `PCI_PWRCTRL_PWRSEQ=m`/`POWER_SEQUENCING_QCOM_WCN=m`; forcing them `=y` via Kconfig
   defaults would change behaviour for every Qualcomm board in the tree to solve a
   problem Repo A solves in its fragment.
5. **Repo B's no-module-tree publishing model** — not kernel-side, but it shapes the
   tree (it is why so much of its fragment is `=y`). Repo A's
   `stage-wifi-modules.sh` installs modules onto the running tablet with a release
   **and** vermagic check, which is the safer loop for a board whose Wi-Fi was once
   disabled by `BUILD_MODULES=0`.
6. **Repo B's `msm-dp-*` patches taken individually.** They are correct together and
   are why Repo B can enable `mdss_dp0` at all, but taking only
   `msm-dp-allow-unresolved-usbc-bridge.patch` without the HPD-deferral patch and the
   DT property would enable DP on Repo A with the cold-boot encoder problem Repo B
   documents ("Activating the external DPU encoder before that cycle makes the
   platform suspend reset the board"). Repo A's current `status = "disabled"` is the
   safe state; the DP set is worth taking only as a unit and with a suspend/resume
   test plan.
7. **`keep-sec-log-previous-index-current.patch` as a patch** — Repo A already has the
   change inside its driver source; the patch would duplicate it and fail to apply.

### 7.3 What this comparison could not settle
* Whether Repo B's `INTERCONNECT_QCOM_OSM_L3=m` (seed) reproduces Repo A's "no cpufreq
  policy at all" defect. Repo B's *resolved* config is produced inside the container
  and is not in the repository; I read the seed and the fragment, so this is inference
  from Repo A's documented mechanism, not a measurement.
* Whether Repo B's `CONFIG_CFI=y` (seed, not overridden) interacts with its `LLVM=1`
  build; Repo A explicitly disables CFI.
* Whether `msm-dp-defer-oob-hpd-until-resume.patch`'s corrupted hunk header
  (`static void msm_dp_bridge_u	      "qcom,defer-hpd-until-first-resume")) {`) still
  applies. I did not run `patch` against a tree to confirm; the workflow suggests it
  does.
* I did not read Repo B's `docs/Hardware-Notes.md`, `docs/PORT-KIT.md`,
  `docs/Device-Controls.md`, `INSTALL.md`, or any `specs/`, `tools/`, `rootfs/` file
  except `boot/dracut/dracut.conf.d/gts9wifi.conf`,
  `boot/dracut/90gts9wifi-usbnet/{module-setup.sh,usbnet.sh}`,
  `rootfs/overlay/usr/libexec/gts9wifi-usb-gadget`, `boot/cmdline.txt`,
  `boot/bootconfig.txt` and `.github/workflows/kernel.yml`. Any kernel-relevant claim
  in the unread files is outside this report.
* I did not read Repo A's `AGENT.md` in full, nor any `docs/` file other than the
  five named in the task plus `docs/WIFI_QCA6490_BRINGUP.md`,
  `docs/DT_PROVIDER_AUDIT.md`, and the three `kernel/patches/*/README.md`.
