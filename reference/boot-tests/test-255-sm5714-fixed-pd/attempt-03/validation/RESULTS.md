# Direct PD telemetry collector validation

- Focused battery/contract parser tests:17 passed, no skips.
- Required `bash scripts/check-stall-offline.sh --changed --base HEAD~1`:
  all1200 selected tests executed and passed in96.710s; shell syntax passed.
- `python3 scripts/run-host-tests.py all --fail-on-skip --report
  out/host-tests/test255-pd-telemetry-all.json`:
  all1200 passed in84.093s, zero failures/errors/skips.
-1183 prior tests retained;17 new tests distinguish measured battery watts from
  configured input ceiling, selected PPS from inactive supported labels, and
  reject unsafe voltage/current/temperature, boot/role changes and contract loss.
- Kernel/config/DTS/driver/service/rootfs remain unchanged. No build, firmware
  deployment, device reboot, GitHub Actions or CI is part of this workflow update.
  Log reboot/fault messages are mocked host fixtures, not tablet commands/events.
- Fresh Wi-Fi preflight passed23 identity/health gates; nativeADB/NCM are
  physically unavailable while the computer USB cable is disconnected, as expected.
