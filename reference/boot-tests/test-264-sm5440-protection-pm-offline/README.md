# Test264: SM5440 active protection/PM offline review

Start test HEAD655d39fa; Test263 device acceptance is complete under the owner's
updated device-normal criterion. The original host STOP remains historical.
This registration is OFFLINE: fix the future completion evidence namespace,
execute affected host tests, and audit vendor protection/watchdog/PM semantics.
It does not create a kernel candidate or authorize deployment, reboot, PPS,
SM5440 activation, current escalation, suspend tests or device commands.

Keep installed Test263/frozen5V<=1.8A,9V<=1.5A/4440mV/thermal/USB/DCC state.
Reuse ea938b24 build/config/DTB/modules/full1351 qualification: no kernel,
DTS, config, toolchain or image changes. No rebuild or new full regression for
host-only helper/docs. Existing admission/transport tests plus the combined
real-recorder namespace regression run locally with mocked device operations.
No suite routing change or removed/skipped test. Preserve all Test263 evidence.

Read docs/SM5440_ACTIVE_PROTECTION_PM_PLAN.md. The future read-only helper takes
an unused child evidence directory, reuses accepted ADB-first admission and
verifies DCC/services. Host failures report incomplete evidence without making
an automatic hardware rollback decision. Device faults still stop acceptance.
No original attempt runner/raw verdict is rewritten to claim it passed.

Outputs: sources.json, review findings, validation/host-tests.json/log,
summary.json/RESULTS.md/SHA256.json. Physical work NOT EXECUTED. ActiveStage3
remains gated by actual protection/ADC/PM/live adapter acceptance, not the
presence of a software_ocp_verified boolean or passing mocks.
