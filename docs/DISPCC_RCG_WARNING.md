# `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration`

An early-boot warning the round-1 brief listed as unexplained. It is now explained,
and it is a **known upstream issue class** rather than an X710 quirk — but it is not
the stall.

## What fires, measured on the current fixed image

```
[    0.374079] disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration.
[    0.374094] WARNING: drivers/clk/qcom/clk-rcg2.c:136 at update_config+0xdc/0xf0,
              CPU#4: kworker/u32:1/13
[    0.374114] Workqueue: events_unbound deferred_probe_work_func
[    0.374158] Call trace:
[    0.374164]  clk_rcg2_shared_init+0x58/0x90
[    0.374170]  __clk_register+0x418/0xacc
[    0.374177]  devm_clk_hw_register+0x7c/0xc8
[    0.374181]  devm_clk_register_regmap+0x58/0x6c
[    0.374183]  qcom_cc_really_probe+0x334/0x3dc
[    0.374187]  platform_probe+0x60/0xa4
```

The warning is the `WARN(1, ...)` at `clk-rcg2.c:136`, reached when `update_config()`
polls `CMD_UPDATE` 500 times at 1 µs and the bit never clears:

```c
for (count = 500; count > 0; count--) {
        ret = regmap_read(rcg->clkr.regmap, rcg->cmd_rcgr + CMD_REG, &cmd);
        if (!(cmd & CMD_UPDATE))
                return 0;
        udelay(1);
}
WARN(1, "%s: rcg didn't update its configuration.", name);
return -EBUSY;
```

It is reached from `clk_rcg2_shared_init()` — i.e. while the shared RCG is being
**parked at registration**, not during any use of the display.

## This is a known upstream issue

The same warning on the same clock was reported and fixed upstream for the `eliza`
platform. The posted fix's own analysis:

> Having DISPCC enabled without DSI PHYs causes clock reparenting issues and warning
> on Eliza EVK: `disp_cc_mdss_mdp_clk_src: rcg didn't update its configuration.`
> WARNING: drivers/clk/qcom/clk-rcg2.c:136 at update_config+0xd4/0xe4

with this stack (from the commit message):

```
update_config (drivers/clk/qcom/clk-rcg2.c:136 (discriminator 2)) (P)
clk_rcg2_shared_disable (drivers/clk/qcom/clk-rcg2.c:1471)
clk_rcg2_shared_init (drivers/clk/qcom/clk-rcg2.c:1540)
__clk_register (drivers/clk/clk.c:3959 ...)
devm_clk_hw_register
devm_clk_register_regmap
qcom_cc_really_probe
disp_cc_eliza_probe
platform_probe
```

Sources:
* patch posting — <https://lkml.iu.edu/hypermail/linux/kernel/2606.2/11163.html>
* a CVE was assigned for the Eliza fix — <https://lists.openwall.net/linux-cve-announce/2026/09/03/27>
* a related SM8450 dispcc clock fix series —
  <https://patchew.org/linux/20260622-sm8450-qol-v1-0-37e2ee8df9da@proton.me/>

**Status of those references, stated precisely:** they are list postings, read as
postings rather than confirmed from `git log` of a mainline tree. Whether the eliza
fix is merged, and its commit SHA, was **not** verified here. The claim this document
supports is only that the warning and its mechanism are known upstream and have a
proposed fix for at least one platform — not that X710 needs that particular patch.

## The stack is structurally identical to the fixed case

Both traces are `update_config ← clk_rcg2_shared_init ← __clk_register ←
devm_clk_hw_register ← devm_clk_register_regmap ← qcom_cc_really_probe ←
platform_probe`. The only difference is the context: eliza runs it from `udevd`
(module load), X710 from `deferred_probe_work_func` (built-in, deferred).

That establishes the mechanism applies to X710 too: the shared RCG cannot be parked
because its parent is not usable at that moment.

**Why X710's case differs from eliza's, and why the eliza fix does not transfer:**
eliza's fix was to stop enabling `dispcc` on a board with no display. X710 *has* a
display and its DSI PHYs, so disabling `dispcc` is exactly wrong here — it would take
out the panel. The general statement from the eliza analysis is what transfers: *"a
device whose base DTSI resources are not all available should not be enabled"*. For
X710 the resources are available, so the parked-parent failure must have a different
proximate cause, which is **not identified here**.

## Why it is not the stall

* It fires at **0.374 s**, roughly 13 s before the 13-14 s stall window, and is
  complete by then.
* It fires on **every** boot, including all 16 observed clean shutdown cycles and all
  8 clean boot records — so it does not discriminate failures from successes.
* Display works afterwards on this port (`docs/DISPLAY_X710_OFFICIAL_V1.md`), so the
  `-EBUSY` return does not prevent the panel from coming up.

Its presence in some historical logs and not others is a **logging-visibility
artifact, not a behavioural difference**: it appears in boot-test logs that captured
early kernel console output (test-020 … test-047, test-183) and not in test-184's
rounds or test-181/182, which captured through other channels. Absence from a log is
not evidence the warning did not fire.

## What would settle it

The warning is `WARN(1, ...)`, so it taints the kernel and is visible in `dmesg` on
any boot. If a future round wants to know whether it is harmless, the cheapest test is
to check whether `disp_cc_mdss_mdp_clk_src`'s rate and parent are correct after
`clk_rcg2_shared_init()` has failed — i.e. read the clock's state in debugfs once the
display is up. If the clock is where the display needs it, the `-EBUSY` was
inconsequential and this can be recorded as benign. That was **not** done here.

## Summary

| question | answer |
|---|---|
| what is it? | `clk_rcg2_shared_init()` failing to park `disp_cc_mdss_mdp_clk_src`; `CMD_UPDATE` never clears within 500 µs |
| known upstream? | yes — same clock, same warning, same stack shape; fix posted for `eliza` |
| is eliza's fix applicable? | **no** — it disables `dispcc` on a board without display; X710 needs its display |
| is it the stall? | no — fires at 0.374 s, present on every boot including all clean ones |
| is it harmful? | **not established.** The `-EBUSY` does not stop the panel from working, but the clock's post-failure state was not checked |
