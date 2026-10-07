# Test344 — natural discharge ready; awaiting owner PC handoff

The finite read-only watch completed five samples over 125.610 seconds. Final sample at 2026-10-07 12:21:16 UTC: Test331 boot dc8442f1b39f48f8855d8918979be1af, SOC75%, pack4.070V/26.4C/-1.726A, USBoffline, directN, healthy/present. The registered preparationSOC20–75 gate is met in this sample; fresh PC preflight must still verify the actual state before deployment.

Windows TCP relay retains strict local WSL SSH identity/trust. No device writes, stress load, staging, flash, reboot, PPS or pump activation occurred. Prior direct-path timeout remains preserved; no CPU failure inferred. See natural-discharge-watch-01 for all five raw packets, commands, timings and terminal status; watch-soc.py records the finite procedure.

Kernel/source/build/68 actualC qualification and 15 affected host+guardian tests are unchanged and reused. This evidence/status phase has tests executed:false and build executed:false; Python source syntax reviewed. No fullsuite/Actions. Next: owner PC handoff, one fresh preflight/install/admission, then a separate owner C1-confirmed activation. Unconditional exact331 restoration; full port NOT_READY.

Host staging subsequently completed and all staged manifest hashes verified at D:/android/gts9-active/gts9-test344 (HOST_STAGE_STATUS.json). This copied only qualified host artifacts; device preflight/install has not run and owner PC handoff remains pending.
