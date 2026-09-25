# test-193: five baseline rounds, and the harness defect that would have voided them

Run 2026-09-25T08:15–08:31Z on the flashed test-191 kernel. **Nothing was
flashed for this test.** Profile A (`baseline`) is byte-identical to the
configuration already on the tablet — `out/boot-bundle-stall-baseline/vendor_boot.img`
is `06902f993f6fe9b682686ab36ad956032a8f6a250e595a85e1d7ac82092f211f`, the same
image the test-191 flash wrote — so the rounds needed no write and none was made.

## Result

**5 of 5 rounds clean.** Every round: `stall=0`, `rpmh_timeout=0`,
`dpu_frame_timeout=0`, `mmc_timeout=0`, `rcu_stall=0`, `failed_units=0`,
`gpu_driver=adreno`, `aoss_driver=qcom_aoss_qmp`, `panel_status=2:connected`,
`usb_state=configured`, and a distinct `boot_id`.

Five warm reboots cannot reproduce a ~3–7 % event, and this result is not offered
as evidence that the stall is absent. What it establishes is that the **harness
works end to end on real hardware** — preflight, the parameter guard, the
reboot, both probes, the per-round record and the summary table — and that the
baseline profile is not obviously worse than anything else.

Reproduction is established elsewhere in this session and is stronger: **2 wedge
cycles in 29 warm reboots** on this kernel (`wedge-rate.sh` rate1 cycle 1, and
rate2 cycle 9, whose boot restarted itself twice at back+76 s and back+135 s).
Both were harness-issued `systemctl reboot` cycles, so warm reboots are a
sufficient reproduction vehicle.

## The defect this run found, and why the numbers above are trustworthy

The first attempt at this series was voided by a defect in the harness's primary
readout, and the run above is the one made after fixing it.

The COM19 capture holds **13577 bytes and zero kernel lines** — no
`Booting Linux`, no `Linux version`, no `encoder is disabled`, no
`supply vdd not found`. The gadget console carries userspace output only, so an
anomaly count taken from it is **structurally 0 for every profile, including a
wedged one** — and it looks correct, because a clean round really is 0. That is
the same shape as the `gmu_bound` / `aoss_bound` metrics fixed earlier in the
round, and it would have produced the conclusion "no profile shows anomalies,
therefore none of them is the cause".

`channel-coverage.txt` records the evidence and the fix's effect. On every round:

* `console_kernel_lines=0` — the blind channel, recorded so it stays visible;
* `klog_lines≈974` — `journalctl -k -b -1`, the previous boot's whole kernel ring
  from 2.7 s onward;
* `pstore_lines=3` — the ramoops console, which survives the reboot and carries a
  panic;
* `gpu_dummy_reg_klog=2` and `disp_rcg_stale_klog=1` — the two dummy-regulator
  messages and the display-clock message, **visible now and counted as 0 by the
  broken version**, on a clean boot, exactly as `docs/X710_EARLY_BOOT_WARNINGS.md`
  predicts.

The two kernel channels have different blind spots and are therefore both kept:
journald stops when a boot wedges, so the panic tail can be missing from KLOG;
pstore is a ring that the next boot overwrites.

## Files

| file | what it is |
|---|---|
| `ab-baseline.txt` | the full harness log for the run |
| `preflight.txt` | the pre-flight probe: which cmdline and driver state the tablet was in |
| `channel-coverage.txt` | per-round counts from both kernel channels, with the blind one shown |
| `rounds/round-N.txt` | the per-round record |

The round records name `console_log=` paths under `out/stall-ab/baseline/`, which
is not versioned; those files contain no kernel data (see above), so nothing is
lost by their absence.

## What is next

Profiles **B** (`msm.disable_acd=1`) and **C** (`msm.skip_gpu=1`) need a
`vendor_boot` flash each and are the recommended next physical test. C is the
decisive one. This test deliberately ran the profile that needed no flash first,
both to validate the harness and because it is the control the other two are
compared against.
