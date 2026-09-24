# test-187 on-device result — the GPU binds, and the ACD chain is gone

Status: **partially executed on hardware.** Profile A (baseline) was flashed and
booted; the GPU-bind question is answered. The stall-rate A/B has **not** been run
yet, because the fix landed mid-session and changed the kernel.

The user authorised flashing: *"后续可以直接刷入测试"*, confirmed as
*boot + vendor_boot for profiles A and G*, with warm reboots labelled honestly as
warm.

## What was flashed, and the two attempts it took

| attempt | kernel | `boot.img` | result |
|---|---|---|---|
| 1 | round-1 fix: `CONFIG_QCOM_AOSS_QMP=y` only | `afd9371633cdc9f7…` | **GPU still unbound** |
| 2 | round-3 fix: `+ CONFIG_QCOM_IPCC=y` | `12f65577e9731d98…` | **GPU binds** |

Both flashes used `flash-profile.sh` (backup → verify → write → readback), and
both readbacks matched the host SHA256 exactly. The pre-test pair was backed up
first and is the rollback source:

```
boot        2e8a693f6f208a74496631f82f82ac959d66b427acf22f7743cfdc48c47a4923
vendor_boot f1f4ccf76d91f8841cbb5f7752bf9ce19f01f8fdf95714ab35d6765a0615cc56
```

## Why attempt 1 failed: `CONFIG_QCOM_IPCC` was missing

`CONFIG_QCOM_AOSS_QMP=y` alone was not enough. The AOSS QMP node gets its mailbox
from IPCC:

```
power-management@c300000 {
        mboxes = <&ipcc IPCC_CLIENT_AOP IPCC_MPROC_SIGNAL_GLINK_QMP>;
};
```

With `CONFIG_QCOM_IPCC` unset, `mailbox@408000` had no driver, so
`qcom_aoss_qmp` failed **its own** probe:

```
[   14.563130] qcom_aoss_qmp c300000.power-management: failed to acquire ipc mailbox
```

which leaves `qmp_get()` returning `-EPROBE_DEFER` exactly as if AOSS QMP had
never been enabled — enabling it only changed which driver printed the failure.
X910 sets **both** symbols; X710 had neither. That is the substance of the
round-3 config fix.

## Attempt 2: verified state on hardware

Booted profile A on `boot.img 12f65577e9731d98…`, then:

```
$ readlink -f /sys/bus/platform/devices/3d00000.gpu/driver
/sys/bus/platform/drivers/adreno                      <-- the GPU BOUND

$ dmesg | grep -c "Unable to send ACD"                0
$ dmesg | grep -c "Unable to drop a managed"          0
$ dmesg | grep -c "failed to acquire ipc mailbox"     0
```

Four consecutive boots (one flash reboot + three warm reboots) all showed the GPU
bound with zero occurrences of any of the three errors that defined this failure
chain through rounds 1 and 2. Before the fix every boot showed all three.

`/sys/kernel/debug/devices_deferred` dropped from 8 permanent entries to 8
entries with a *changed composition*: the `smp2p-*` reason moved from
`qcom_smp2p: IRQ index 0 not found` to `unable to allocate local smp2p item`,
which is a different (later) failure and is not yet investigated.

## The stall was NOT tested yet

```
uptime   up ~4 min            soft lockup    0
rpmh_write_batch  0           rcu stall      0
deferred probe pending  7
```

A clean boot. That is **not** a fix claim: the stall was always intermittent, four
clean boots bound the rate and nothing more, and the profile-A-vs-G comparison
that would actually test the burst hypothesis has not been run.

## Open observation: the deferred-probe burst still lands at 14.307 s

On the fixed kernel, after the GPU binds:

```
[   14.307537] gcc-sm8550 100000.clock-controller: sync_state() pending due to 3d6a000.gmu
[   14.307543] gpu_cc-sm8550 3d90000.clock-controller: sync_state() pending due to 3d6a000.gmu
```

The burst is still there, still at ~14.3 s, and still names the GMU — even though
`3d00000.gpu` is bound. So with the config fix the `gmu@3d6a000` *platform
device* still has no driver (there is no `adreno-gmu` driver in this tree; the GMU
is driven as a sub-device of the adreno GPU), which means `gcc`/`gpucc` still
cannot complete `sync_state()`.

**This is important and unresolved:** the sync_state blockage on the GMU is not
caused by the ACD failure, so fixing ACD does not remove it. It is now the
leading remaining candidate for whatever the burst does, and it is independent of
everything rounds 1-2 focused on.
