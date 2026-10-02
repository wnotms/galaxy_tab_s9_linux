# Test281 — normal baseline reentry completed

Registration1a6dfcb2 and transport admission4041fc4c were pushed before the one
ordinary `systemctl reboot`. No BCB, partition, module, kernel/config/DT/rootfs,
USB, ADC or charging change. Test280 STOP remains unchanged.

Boot31e9a212 ->1c1c3d0d387c469098bfcd6db2ac6fb3 is uniquely attributed in journal
history. The command line is now byte-for-byte the accepted normal Test263 form;
the previous lpcharge=1 additions disappeared. This proves recovery on this one
ordinary reboot, not a universal boot-mode/CPU-stability conclusion.

Before reboot, all five partitions and181module hashes matched Test263. Config
f2891de2 and notes fea0613f remain exact after reboot. Sink/Device/PCSDP500,
passive fault0/pumpOFF/IBUS0, battery health and4440mV policy are normal. ADB,
same-boot Wi-Fi10.125.29.181, deviceNCM/sshd and Windows enumeration pass; no
Code43. Host NCM TCP was not retested. No detected CPU/kernel fault or failed unit.

Readiness took42.515s including early preserved ADB/service unavailability.
Two healthy endpoints were86.64s apart, satisfying the registered15s minimum;
this is NOT continuous86.64s observation or long-term acceptance. No repeated
reboot and no observer/trace/fresh request. Final raw endpoint/boot/kernel/USB
records are preserved. Installed263 unchanged; rollback unnecessary.

Host-only display checks initially failed on Windows non-UTF8/mixed-case UsbNcm
output. Original raw bytes/status0 were retained and parsed without issuing the
command again. They did not change device behavior or require a repeat test.

New build/full/tests executed:false: documentation/results with existing frozen
gates only; reuse28024 and unchanged272/2761481/W1/sparse qualification. No CI.
Future passive trace still needs separate registration, paired deployment and
exact263rollback. ADC/timeout attribution remains UNKNOWN; activeStage3 NOT READY.
