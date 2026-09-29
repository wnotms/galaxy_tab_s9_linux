# Final local validation

`python3 scripts/run-host-tests.py all --fail-on-skip --report
out/host-tests/test255-pd-final-all.json` executed all1200 retained tests:
zero failures/errors/skips. Unittest time96.129s; whole runner96.240s.
No GitHub Actions/CI, kernel rebuild, device reboot or configuration change.
Initial wrapper/all, changed transition coverage,17 new power/parser checks and
33 existing cable/FunctionFS checks remain separately archived. Mock boot/fault
messages in host logs are fixture outputs, not physical tablet events.
All existing per-stage manifests were verified before final sealing.
