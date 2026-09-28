# Host validation and read-only checks

Focused final observer/parser suite:33 passed, including actual cycle01 journal
replay, stale configured/offline capture, conservative recovery deadline,
short unplug, identity changes, failed/missing context and a proposed
registration blocked before device access. Mocked first Wi-Fi identity failure
stops before recovery; the shared production policy is restored. Tests do not
operate physical USB or establish physical recovery.

Development command `bash scripts/check-stall-offline.sh --changed --base HEAD~1`
selected1123 retained tests through unknown-dependency fallback. It failed one
old conservative-production-policy test because the new runner's mocked
baseline read leaked p.P=attempt05 into subsequent tests. This was a host
process state bug, not a tablet fault. The runner now restores p.P in finally.
The failed log is retained; it is not called a pass.

Final explicit `python3 scripts/run-host-tests.py all --fail-on-skip --report
out/host-tests/adbd-cable-observer-all.json` passed1124 tests, zero failures/
errors/skips (74.569s unittest, see JSON for orchestration timing). Final33-test
focused check also passed after strengthening the duplicate-warning fixture.
Shell syntax checks in the development wrapper passed; new Python AST/compile
and code/docs whitespace checks pass. Raw archived ADB CRLF/formatting is
preserved even where git diff --check diagnoses trailing whitespace. No kernel
rebuild, device variant, host backend/driver/config change or physical cycle
was made for these local checks.

Full read-only preflight passed five partition hashes, exact embedded config/
notes,181 candidate plus181 retained original modules, DCC absence, protected
settings and active daemon hash/PID834, complete kernel journal, no new fault/
failed unit/Code43 and native ADB/NCM/Wi-Fi. Actual read-only snapshot parsing
and combined kernel/adbd journal selector were verified on this boot. The
proposed policy remains owner_adopted=false and is rejected before device
access by the physical runner. This is not new physical-test acceptance.
