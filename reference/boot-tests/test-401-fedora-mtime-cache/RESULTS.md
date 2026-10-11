# Test401 — cache reinitialized; interface and trace gaps; returned370

Registration366f17e0 was pushed before one physical candidate boot
e72b9cfb-ed0b-4c42-a580-d90b7fbe8b6f. The exact Test400 complete Fedora52-file
firmware/early image/kernel/config/DT/181 modules/provider/daemon were reused.
Only the copied config-mtime cache35 data values were changed initially; no
physical persist, factory calibration or charging/USB/input configuration changed.

Both physical snapshots succeeded with216 sensor files and both producers
inactive. The before snapshot matched all qualified installed bytes/modes/mtimes.
After the single30s window, all35 cache values returned from0 to1640995200,
and the resulting cache bytes equal the frozen Test400 initial cache. Only this
member changed **content**. Other rewritten registry members changed mode/mtime
without changing bytes; exact86 metadata-only members are in offline-cache-boundary.
All changes remained in the owned disposable copy and were removed on recovery.
They were not adopted over factory persist or the accepted desktop baseline.

All35 config stat observations matched unchanged physical config metadata.
The partial decoded trace contains three config-file opens and18 write replies;
this is not full read/write coverage or proof that every config was parsed.
The listener observer reached its registered1MiB text budget at seq1379 and
reported RPCRETURN_LIMIT reason=budget; the strict frame parser also reports
missing buffer header. The7,712,368-byte complete raw unit journal is preserved.
Do not truncate those faults, make frames complete, or fabricate an I/O replay.
Full acknowledged final-file reconstruction remains unqualified for this boot.

An earlier complete callback at seq1025 also returned4294967291 (-5), transport0,
when DSP asked handle0 to open **sns_registry**. Raw log: “Could not find local
interface sns_registry”. The frozen Fedora-derived localctl.c explicitly returns
-5 for an unregistered local interface; rpcd.c registers apps_remotectl/apps_std/
apps_mem. Fedora's current three package patches do not implement sns_registry.
Thus this is a real unsupported-interface reply and an unqualified status in
this registration, **not proof that this interface is necessary or causes absent
SSC**. It may be a compatibility probe; source-specific classification requires
independent qualification. Do not invent an implementation or blanket-waive -5.

Both registered PDR cycles completed UP. Native trace22 events/8CPUs zero-loss
passed: ADSP negotiation at0.545401, feature1; slave-kernel0/0,2/2,6/6,6/6 observed.
SSC service400 remained absent; no accelerometer sample or automatic rotation
acceptance. The full source kernel journal collected offline was classified by
the unchanged strict scanner with no new CPU/panic/Oops/RCU/CSD/severe fault.
The32.710831s through raw journal collection is bounded observation, not a
long-term stability claim or proof of all initialization semantics.

The first callback evidence error was preserved and no second candidate/RPC
launch occurred. Recovery restored all52 original firmware absences and owned
directory absence, archived the terminal ledger before removing owned backups,
removed the nine overlay files and isolated assets, and restored/read back exact
370 vendor/allfive partitions/181 modules/config/notes. Normal return boot
c9a70924-60d3-4caa-b3a4-f7d7fb468b66 was uniquely attributed;20.203s health passed.
GNOME/GDM/palm/ADB/device NCM/sshd were normal; no failed unit or new kernel fault.
Final telemetry100%,33.0°C,4.446V; float4.44V unchanged, PPS/pump/DCC OFF.

All39 Windows stage files were independently hash-verified and removed, freeing
their recorded byte total; /mnt/d/android/platform-tools/adb.exe was preserved.
Retention392–401, expired391 image already absent, current370 and399/400 images
retain explicit401 consumers. No new kernel/image/module build/full routing
regression/Actions. Offline qualification81 tests passed, zero skip; this
results-only stage executed:false and reuses that exact source qualification.

Next: qualify a larger **bounded** optional observer budget using the actual
initialization workload, retain strict frame/fault gates, and separately audit
the exact missing local interface semantics against the same Fedora implementation.
Do not retry unchanged401 or claim sensors are working. Any future independent
comparison must again restore the normal desktop after preserving first evidence.
