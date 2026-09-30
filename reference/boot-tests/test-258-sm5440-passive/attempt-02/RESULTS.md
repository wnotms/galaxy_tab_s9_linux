# Test258 attempt02: boot/probe passed, passive health failed, rolled back

Registration328621ac was pushed before device recovery/reboot. Start HEAD was
a4437ece. Kernel source/artifacts remain the same f3a266b5-qualified passive
profile; no rebuild/full regression, PPS, pump ON, current/float/thermal or
USB/adbd/TCPM configuration change. The earlier stopped attempt is immutable.

Fresh14 runtime/rescue gates passed on accepted0456f423, including Wi-Fi SSH
10.191.121.119. A case-sensitive host NCM-name predicate initially rejected
UsbNcm despite recorded Up and working SSH. The original derived stop is kept;
structured JSON/casefold review of the same raw evidence qualified it without
a device retry/change. No earlier Wi-Fi failure is rewritten as a pass.

TWRP inspection verified original five partitions, microSD/root/current181
modules, battery and sealed files. The corrected release-root helper installed
and verified181 paired modules, saved the accepted pair and preserved older
backups. boot/vendor_boot were written/read back; init_boot/dtbo/vbmeta remained
exactly unchanged. Install evidence778cd116 was pushed before normal startup.
Registration seal records the original328621ac source; the later ca8d0897
BCB zero-readback amendment/rollback source is sealed separately in RECOVERY_SHA256.

Candidate bootf96739d4c57b4968b971889368351458 matched registered config
f2891de2… and notesfd89d2bd…. SM5440 revision2 probe/binding and enabled DT child
passed; DCC absent, ADB/NCM/Wi-Fi, Sink/Device, no Code43 and no failed unit
were observed. Successful probe is distinct from ADC/passive health acceptance.

First non-clean evidence: kernel source1.608590s reports
`passive fault bitmap=0x82`; sample000 at uptime30.07s reports
Not charging/Unspecified failure, with no online/voltage/current/die fields.
Battery gauge4008mV,-165mA,61%,29.6C,Good. Stop occurred before a clean sample;
the registered150s observation did not complete. Full first-failure journals,
uevents, timestamps and transport records were saved. CPU/panic parser found
no CPU-stall/panic signature in the captured window; SM5440 fault is separately
recorded as failure and is not hidden by that generic parser result.

0x82 is software-decoded VBAT_OVP+REVBLK, not a raw register. Source stores a
completed mode-OFF-checked sample, latches the fault and stops its poller; by the
host sample the2500ms ADC cache has expired. No ADC timeout is directly logged.
INT events and STATUS were merged, so historical latch versus live/default
protection cannot be distinguished. No real battery overvoltage or independent
ADC accuracy is established. See FAILURE_ANALYSIS.md; flags were not suppressed,
thresholds were not changed, and protection/active initialization was not tried.

Registered rollback entered verified TWRP, restored the exact accepted Test255
boot/vendor_boot and181 saved modules and read back all five partitions.
Failed candidate modules remain at/usr/lib/modules/.gts9-test258-tested. Older
Test254/Test252/Test249 directories were not modified. Temporary BCB cleared,
root unmounted, rollback evidence9fc012fd pushed before ordinary system boot.

Final accepted bootf965e05406b04d3aaa78b86bc1979f13 passed12 runtime gates:
exact old config/notes/normal cmdline, absent DCC/passive supply/staging,
Sink/Device, Good battery62%,29.2C,4018mV, no failed unit/new kernel fault,
ADB/NCM/Wi-Fi10.191.121.242 and Windows no Code43. Partition/module verification
uses the preceding exact rollback readback, not duplicate per-sample hashing.
Net pack discharge on PC USB is recorded, not mislabeled pump charging.

Validation reused: full1264 host/build/bundle/artifact qualification from
f3a266b5 and5 real-archive host transaction tests(2.671s) from a4437ece. Adapted
runner syntax/diff and NCM structured-parser fixtures were reviewed locally.
No new full1269 pass is claimed. This results/documentation commit has
executed:false for host regression and kernel_rebuilt:false; only recorded
evidence/summary integrity is checked. No CI/main merge. Window/start/first
fault/final boot identities are machine-readable in summary.json; final evidence
is sealed in FINAL_SHA256.json, alongside immutable earlier seals.

Next is offline provenance for raw first-fault INT/STATUS/mode/ADC/protection
state, then a separately qualified and registered passive candidate if needed.
Do not clear latched faults/retry this attempt or enable PPS/pump to force a
pass. Passive health/ADC acceptance remains NOT PASSED; active Stage3 NOT READY.
