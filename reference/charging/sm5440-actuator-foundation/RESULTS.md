# Pump register layer — offline qualification

Implemented checked mode/ENHIZ preparation and shutdown with actual settings
and watchdog helpers, default-disabled guard and native PPS snapshot admission.
Kernel TCPM remains protocol owner. No active adapter/Kbuild/live caller is
installed; no device pumpON/PPS/watchdog/current write. Actual software OCP,
physical ADC/calibration/monitor and cutoff qualification remain open.

44 affected host C tests PASS0.574s (14actuator/16watchdog/14OFF settings), no
failure/error/skip. Tests cover every start/cleanup bus error, uncertain/dropped
writes, permission/lease/source/mode/APDO/physical age refusal, cancellation,
unsafe OFF uncertainty and single-attempt cleanup. Host fake OCP=true is not
an approved live source. ARM64 isolated object W=1/sparse PASS3.657s; known
unrelated vDSO warning remains, no changed-helper warning. Initial host signed
comparison/mock-parentheses issue corrected. Earlier ARM64 success before the
cleanup latch is explicitly superseded by final matching-source qualification.

Existing316 provider six hashes, all98 sealed317 inputs and nine formal
artifacts remain exact. Config/DT diff empty; no candidate Image/modules
build/full regression/CI. Same incremental directory reused for unlinked object;
no new full build tree, image copy or test retention number.

Device initially showed native TWRP this turn. Later ADB became empty and the
registered Wi-Fi SSH probe returned No route to host. No new boot ID is observed,
no capture process is running, and no candidate failure/success is inferred.
Test317 remains installed with rollback_required=true and owner charger boot
confirmation/access pending. Candidate capture and unconditionalaccepted311
restore must complete before integrating this layer in a separate offline
active profile. Full charging port NOT READY.
