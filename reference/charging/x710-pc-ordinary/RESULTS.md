# Ordinary PC charging candidate — offline qualification

Base/source85419619. Incremental sm5440-passive ARM64 build PASS89.513s.
49 affected passive tests PASS1.807s/0skip; same-source109 charging fix tests
PASS4.604s reused from x710-pc-current, not a second execution. New Test322 pure
evidence/runner14 tests PASS0.033s. No full regression/routing change/Actions.

Exact accepted311 DTB preserved. Config diff ONLY ADC_RAW_TEST absent->n and
ADC_TIMING_TEST absent->n; new embedded hash31d5a941... differs for these explicit
OFF entries, no enabled feature change. DCC=n/container retained. Native control
symbols absent, pump capability absent; TCPC/USB/DTS/adbd/rootfs/thermal unchanged.
181 matching module files: runtime unchanged; BTF only differences detailed in
summary, candidate archive must still be installed as matched181 pairing.
57 protected source/48 previous formal artifacts checked unchanged. Passive308
incremental cache is now this provider, not older accepted or raw321 provider;
necessary old raw debug inputs archived/verified per inputs-before, not fulltree.

Image/DTB/config/notes/modules hashes in summary. Offline header4 boot-only package
and exact accepted311 rollback in PACKAGE.json, unpackpayload exact, boot size
100663296; no nonboot bundle regeneration. Windows staging only for imminent322,
no new fullcache. Qualification did not mutate device. Later read-only reconnect
snapshot is separate:49%,3.877V,30.4C,accepted311 config/notes,lpcharge1,5V1800mA
logical source grant versus actual reported input500mA/net−517mA. ADB/sink/device,
usb0 andWi-Fi10.139.153.35 restored. This proves current grant underuse; TCPM
current is authorized budget, not physical cable current/watts. Currentdevice
still oldimage at this qualification; no charging effectiveness claim yet.

Proceed only with pushed Test322 one unchanged normal reentry and fresh safe
normal preflight, boot+181 swap,60s PC observation, first-device-failure restore.
Full charging port NOT READY; no new ADC/calibration/OCP/PPS/pump acceptance.
