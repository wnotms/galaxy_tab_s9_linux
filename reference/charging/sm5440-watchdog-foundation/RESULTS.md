# SM5440 watchdog foundation — offline only

Implemented actual checked regmap arm/service/OFF-only restore operations.
Source audit records Samsung X710 timer/enable/reset encodings, Fedora
ab123e7d's actual equal-value rewrite, and pinned Linux regmap skip semantics.
No Kbuild integration, live caller, pumpON, PPS, charging grant or physical
watchdog/cutoff result. Current Test317 diagnostic and rollback remain frozen.

16 host C/fault tests PASS0.233s; ARM64 object W=1/sparse PASS3.236s. Initial
ARM64 build exit2 (`current` macro collision) is retained, corrected tocntl1.
No changed-helper warning; unrelated existing vDSO sparse warning remains.
Six existing316 provider hashes, all98 sealed317 inputs and nine formal
artifacts unchanged; config/DT diff empty. No kernel-image build/full/Actions.

Device remains TWRP at observed checkpoints, candidate317 installed with
rollback_required=true; owner fixed9 charger boot pending. Wi-Fi attempt failed
No route to host while in recovery; this is not a failed candidate boot or
active process. No extra reboot, converter request or charging write.

Next: once317 finishes and accepted311 is restored, wire the new helper only
into a separately qualified offline active profile and later validated adapter.
Physical ADC/current protection/monitor/ON/PPS/fallback/PM still required.
Full charging port NOT READY.
