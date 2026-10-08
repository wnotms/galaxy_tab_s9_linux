# SM5714 computer USB input control

## Finding

Current mainline has **no writable USB input-disable API**. The live
`input_current_limit` is read-only; `input_suspend` and `charge_control_limit`
are absent. There is no `set_property`/`property_is_writeable` in the current
SM5714 power-supply descriptor. Setting a desktop preference cannot currently
stop the tablet drawing power from the PC.

Samsung X710 stock code does implement a distinct BUCK-off mode, so a future
driver-supported input inhibit is plausible. It is not yet implemented or
physically verified in this mainline port. In particular, stopping battery
charging is not proof of zero computer input or electrical isolation.

## Exact source basis

Read-only stock sources under
`/home/ms/Samsung/kernel_platform/msm-kernel/drivers/battery/charger/sm5714_charger/`:

| Source/function | Meaning |
| --- | --- |
| `sm5714_charger.c: sm5714_chg_buck_control()` | BUCK off: ENQ4FET=1 → SUSPEND event → ENQ4FET=0; BUCK on: clear SUSPEND, wait 10–11 ms |
| `sm5714_charger_oper.c: set_OP_MODE()` | CNTL2 low four bits; SUSPEND mode 0x0, VBUS charging mode 0x5 |
| `sm5714_charger.c: psy_chg_set_charge_mode()` | `BUCK_OFF` and `CHARGING_OFF` have different semantics |
| Current `sm5714-battery.c` | Q4 gates the battery pack, not all VSYS consumption; minimum input setting 100 mA is not VBUS isolation |

Hashes and the observed live state are saved in
`reference/desktop-bringup/initial-readonly-1791439861/`. The same-model Fedora
driver has no ready-made manual input-inhibit userspace API to copy. No stock
source, current driver, charger register or USB configuration was modified.

## Proposed independent implementation

Keep one driver-owned input-inhibit state, serialized by `chg_lock` and honored
by the normal poll/configure paths. Expose a standard power-supply interface only
after defining its semantics: for example, an explicitly documented
`INPUT_CURRENT_LIMIT=0` meaning hardware suspend, not an unrepresentable 0 mA
register encoding. Nonzero limits must remain within existing ceilings; restore
must use the currently valid attach/thermal/PD state, not stale cached values.

Reject transitions while direct/PPS ownership is active; never change TCPC roles
or enable pump/OTG. Apply the stock BUCK sequence with error/readback handling,
preserving fail-closed thermal behavior. Integrate the inhibitor with detach,
probe/remove, PM and fault recovery so the poller cannot silently undo it.
Do not implement this with concurrent raw `i2cset` against the bound driver.

Validate first on PC Sink/UFP with the battery comfortably charged: inhibit,
confirm readback and net battery discharge, keep ADB/NCM and Wi-Fi responsive,
then restore conservative PC charging. A negative battery current alone does
not prove zero VBUS draw; physical USB current measurement is needed for that
claim. Check reconnect, suspend and I2C failure separately. This is a new kernel
candidate/test after Test348, not a runtime change to its frozen baseline.

Validation for this source-assessment document: source references/recorded
hashes and current descriptor reviewed; tests/build/device experiment:
**executed: false**. This does not claim acceptance of a new control interface.
