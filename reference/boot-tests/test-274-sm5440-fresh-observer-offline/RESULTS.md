# Test274 — bounded passive fresh observer qualified offline

OFFLINE_BOUNDED_FRESH_OBSERVER_QUALIFIED at source10d57da0. Explicit external
GPL diagnostic .ko against Test272's frozen399eb497 provider; no device command,
install/flash/reboot/PPS/pumpON/current change. Installed Test263 remains unchanged.

## Implementation

One kthread starts on a future explicit module load, at most8 sequential fresh
requests,1s between successes. First provider or consumer error stops; no retry.
No lock over API/sleep/join. Exit joins before removing debugfs. Cached0400result
read never requests a conversion; no parameters/autoload/raw-register/write/
charging interface. Rows preserve request/return/genuine acquisition BOOTTIME,
provider/consumer errno and raw uV/uA/deciC with usable flag. Unusable failed raw
values are diagnostic only. Mode/lifetime/PM/conversion-sequence enforcement is
in frozen Test272 API; public ABI does not export converter sequence. Row number
is caller order, not an invented converter sequence.100ms remains a software
validity guard, not hardware cutoff or measured worst-case timing.

Consumer refuses offline/nonzeroIBUS/invalid voltage or temperature, acquisition
before request/after return, reversed time or delivery>100ms. Original<4.3V
OFF-mode diagnostic boundary unchanged. No SM5714, TCPC, TCPM, SM5440 registers,
DTS/config, USB/adbd/NCM/Wi-Fi/rootfs or policy change. Driver scheduling changes
only if this explicit caller is later loaded; normal installed monitoring is untouched.

## Qualification

| Check | Result |
| --- | --- |
| Actual-C observer tests |18 PASS: returns/time/bounds, partial failure, no retry, stop/interrupt/unload, lock scope |
| Isolated mocked builder tests |2 PASS: valid frozen provider; changed header cannot pair old Image even if prepared tree matches |
| Final full host |1475 PASS,0 failures/errors/skips,89.404s unittest (report elapsed in JSON) |
| Retention |All1424 Test272 and all1473 initial Test274 IDs retained;0 removed |
| ARM64 external module |PASS, sameclang21/ccache; ELF AArch64, expected7.2-rc3 vermagic/CRC |
| W=1 / sparse |PASS, no module diagnostics; identical object after static and finalbuild |
| Module imports |Fresh passive API + ordinary kernel/debugfs/thread functions; no directI2C/regmap/power_supply/TCPM writes |
| Test272 config/DT/Image/notes/181module archive |Exact sealed hashes unchanged; config/DT diffs empty |
| Old hardware/rootfs/build integration inputs |Unchanged; all compiled-provider/header bytes match frozen399eb497 |

Module SHA9d66c0804f40f8882e0e4550cfc012a54e9c3d0364915ab0b160f45b39924c52,
267536bytes, out/sm5440-fresh-observer/sm5440-fresh-observer.ko. It is deliberately
separate from the existing181 matched files and unsigned; no autoload/install.
The old263 kernel lacks its required fresh symbol; never force-load there.
Fullhost retains two pre-existing mockPogo unused-function warnings, not module
warnings. No GitHub Actions. W1/sparse/module build logs, imports, source/artifact
hashes and reports retained; no full Image rebuild was needed for an external
consumer of an unchanged qualified provider.

Initial module build/full1473 passed. Final review found that comparing current
header with prepared tree alone could later allow both to change while the sealed
Image remained old. Add explicit git399eb497 source freeze and two behavioral
builder tests; final build/full1475 were therefore necessary. Initial records
retained as superseded, not represented as final qualification. A host metadata
writer parenthesis error was corrected without changing candidate/tests/artifacts;
its note is retained. No actual device failure occurred in this offline test.

## Next boundary

FUTURE_PHYSICAL_PLAN is an unexecuted Test275 plan: exact272 provider+paired
181modules, exact263rollback, one observer load on ordinary PCUSB/pumpOFF,
30s observation, stop/no reload on first error, unload and sameboot device endpoint.
Successful passive timing alone never authorizes PPS/pump/current. Independent
voltage/nonzero-current accuracy, OCP/cutoff and live adapter/PM remain unqualified.
ActiveStage3 NOT READY. SourceAPDO was already captured in Test273; don't repeat
its physical window just for documentation or mistake advertisement for45W.
