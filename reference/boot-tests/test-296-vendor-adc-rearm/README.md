# Test296 — Samsung ADC single-shot rearm

Offline source qualification followed by a separately registered ONE passive
candidate boot. Source-backed change: checked ADC-disable20ms before the unchanged
converter. This tests a missing vendor rearm interval; root cause not asserted.
No pump/PPS/current/threshold/deadline/fault-reset changes. Design:
docs/SM5440_ADC_REARM.md.228affected tests PASS,8new,7.638s. No full rerun.
Build and independent physical registration pending; device still restored263.
