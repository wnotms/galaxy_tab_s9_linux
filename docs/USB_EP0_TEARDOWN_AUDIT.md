# FunctionFS/DWC3 ep0 teardown audit

Test367 stopped, recorded the first error and removed its userspace overlay.
It remains STOP. The following source analysis informs a **new** Test368;
it does not rewrite the earlier result or silence a kernel message.

The actual pinned Linux7.2-rc3 tree is
`a13c140cc289c0b7b3770bce5b3ad42ab35074aa`. The three relevant files are
unchanged relative to that commit; excerpt and full-file hashes are preserved
in [source evidence](../reference/boot-tests/test-368-usb-cable-reconnect/source-audit.json).

| Step | Pinned source | Behavior |
| --- | --- | --- |
| Empty configfs UDC write | `drivers/usb/gadget/configfs.c`, `gadget_dev_desc_UDC_store` | Unregister existing gadget |
| Composite cleanup | `configfs_composite_unbind` / `purge_configs_funcs` | Invoke function unbind callbacks |
| Last FunctionFS instance | `drivers/usb/gadget/function/f_fs.c`, `ffs_func_unbind` | Emit UNBIND; call `functionfs_unbind` |
| ep0 cleanup | `functionfs_unbind` | Unconditionally call `usb_ep_dequeue`, ignore its return, free ep0 request and clear gadget |
| Request already absent | `drivers/usb/dwc3/gadget.c`, `dwc3_gadget_ep_dequeue` | Walk cancelled/pending/started lists; if on none, print exact no-queue error and return-EINVAL |

The no-list DWC3 branch itself does not reset the controller, alter registers
or cancel another request. It can be reached during ordinary FunctionFS
teardown when there is nothing queued. A KERN_ERR severity alone does not make
that branch a kernel panic or proof of a live USB transfer failure. It remains
an error-return diagnostic, not a reason to ignore arbitrary USB errors.

Test367's actual single error source timestamp42552.324630s is4.0ms from its
recorded owned unbind42552.320602s. Both are on boot78ec1906; binding was empty
before cleanup and restored on stop. The earlier manual rebind produced the
same message. Source and bounded correlation explain this particular teardown
path; no live function-stack trace was captured, so the call-chain attribution
is an inference supported by source, not a new stack-trace observation.

Test368's host observer preserves the full raw journal and permits at most one
exact `dwc3-qcom a600000.usb: request <16hex> was not queued to ep0out` at
priority3 per uniquely recorded owned unbind, within250ms of kernel/helper
**source monotonic** time. Missing source time, wrong boot/unit, ambiguity,
repeat, other endpoint/severity/message or an error outside that boundary
stops. CPU signatures, all other new severe errors and failed transport gates
still stop. A classified teardown is provisional until actual ADB shell and
device NCM return on the same boot. No broad regexp warning allowlist or driver
log suppression, no kernel/FunctionFS/DWC3 patch and no diagnostic activation.

Root cause of the missing physical-disconnect handling is still not fully
established. The userspace bridge handles the confirmed Type-C/configfs cable
boundary while retaining the fixed-peripheral, Sink/Device policy. It does not
claim to fix Code43, hardware faults, host drivers, suspend or every USB failure.
No charging, current, PD/PPS/pump, OTG, descriptors or adbd policy changes.

The Test367 runner also generated an incidental helper bytecode cache through
SourceFileLoader. Exact frozen code/header/hash ownership was verified, then
only that cache was removed with same-boot/inactive-unit gates. Test368 executes
the verified source without importing it as a module, so it generates no helper
bytecode. Transaction and rollback code are reused with a distinct scope/unit;
there is no automatic restart of Test367.
