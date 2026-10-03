# SM5440 watchdog transaction foundation

Test317 is installed and waiting for the owner's fixed9 charger boot. Its
sealed kernel, runner inputs and rollback are unchanged. This separate code
is not in Kbuild, has no live caller/export and is not a new device candidate.
It removes an implementation gap in the future active hardware adapter;
physical watchdog/OCP acceptance remains outstanding.

## Source and contract

* [VENDOR] X710 `sm5440_set_wdt_timer()` uses CNTL1(0x0c)[6:4]. The enum assigns
  30 seconds code4; `init_reg_param()` selects that code. `enable_wdt()` owns
  bit7. Bit0 is software reset and must never be echoed as1 by this helper.
* [FEDORA] The audited same-model snapshot's worker explicitly services the
  watchdog by rewriting CNTL1. Its `sm5440_update_bits()` always issues an
  SMBus write, even when the byte did not change. This refresh mechanism is a
  Fedora cross-check, not a claimed vendor-only finding or physical result.
* [MAINLINE] Pinned regmap `_regmap_update_bits()` normally skips equal-value
  writes. Replacing Fedora's helper with plain `regmap_update_bits()` would
  silently omit refresh. Use a checked `regmap_write()` on the already verified
  CNTL1 byte, followed by exact readback, including the equal-value case.

`sm5440_watchdog_arm_off()` accepts only a new transaction, correct DEVICEID,
verified pumpOFF, VBUSPOK and fault-free live STATUS. It requires inherited WDT
disabled/reset clear, saves the original byte and marks ownership before a
possibly uncertain write. It programs only timer/enable fields; no pumpON,
reset, protection mask, voltage/current setting or PD operation occurs.

`sm5440_watchdog_service()` requires the same caller epoch, a monotonic nonzero
clock and service gap at most1000ms [BRINGUP_LIMIT, not physical cutoff]. It
rechecks CHG mode/live faults/POK and exact expected CNTL1 before each real write.
Any failure latches the operation error and blocks later refresh. The future
active adapter must stop/verify the pump and perform safe fallback; this helper
cannot prove OFF after an I2C failure. Successful refresh never grants charging.

`sm5440_watchdog_restore_off()` requires OFF readback before disabling/restoring
the owned fields. It does not write pump mode or restore an originally enabled
watchdog. Unknown OFF/reset state causes no CNTL1 write. Unrelated-bit drift is
preserved but reported; uncertain writes/readback retain ownership and cleanup
error. Clean restore returns the exact original byte. First operation error
survives successful cleanup; cleanup never retries itself indefinitely.

The caller must supply an uncached regmap, serialize all SM5440 I/O, drain work,
and bind the transaction lifetime/epoch to the current attachment. No helper
holds a cross-device lock or sleeps. The caller still owns fresh physical ADC,
software OCP, pack safety, source provenance, monitor deadline and PM ordering.
One healthy register read or a30s watchdog is not a100ms protection certificate.

## Offline verification

16 executable C tests pass, including every arm/service/cleanup I/O failure,
uncertain/ignored writes, equal-value actual refresh, source epoch/clock refusal,
mode loss, reset/unowned-bit drift and verified-OFF-only cleanup. ARM64 isolated
object compilation with W=1 and sparse passes in3.236s; the first build exposed
a kernel `current` macro collision, corrected to `cntl1`. Original failed log
and exit2 are retained. Existing vDSO sparse warning is outside this helper.

The unchanged316 provider config/release/Module.symvers/vmlinux and two qualified
SM5440 objects retain exact hashes. All sealed317 inputs and nine formal package
artifacts retain exact hashes. No Image/DTB/module relink or deploy was done.
This is an unlinked object qualification, not a complete charging candidate.
See `reference/charging/sm5440-watchdog-foundation/summary.json`.

## Next integration

After Test317 capture and unconditional accepted311 restore, integrate this
layer in a separate offline active profile, run the standard ARM64/W=1/sparse
checks and preserve exact config/DT/protected-file gates. A live adapter must
arm the watchdog while OFF before any eventual pumpON, refresh only after
healthy source/pack/physical monitoring, and verify pumpOFF before cleanup.
Default passive/fixed paths must remain unchanged. Do not deploy or intentionally
let an active battery charging watchdog expire to demonstrate safety.
