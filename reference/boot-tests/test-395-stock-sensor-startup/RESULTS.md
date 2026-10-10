# Test395 — original startup inputs exported, unchanged desktop

One registered read-only export completed in 1.259s. The exact
X710 super/vendor metadata checks passed; temporary read-only/noexec mount and
its own loop were removed before archive output.69 original files, including
8 init rc files, sensor scripts, APPS daemons and32/64-bit libraries, were
collected. Archive3,247,385bytes, SHA256
`6709a8a16f585c6f7f59f7e9deb234e2d9a1c9b5efe83beec7e2ec295b7eb6a4`; retained in ignored
`out/ssc-stock-startup395.tar.gz`. Hash-bound manifest and complete command/
identity/kernel/cleanup outputs are committed. No proprietary binary deployment.

Boot remains `26754f29-f759-472c-8098-16ad4cecdd62`. Before/after config/notes match
accepted Test370; GDM/ADB/device NCM normal, no failed unit or new kernel error/
CPU signature, ADSP remains offline. Final battery 100%,
33.6°C, VBAT4.447V within
the existing passive bounds;4.44V float unchanged. No flash, reboot, DSP/RPC
startup, kernel/DTB/modules/rootfs/registry/USB/input/charging change.
Test394's exact five partition and181 module identity reused on this same boot,
not a new final hash pass. PPS/pump/DCC remain OFF.

31 affected host tests passed,0skips (19 export/scope plus12 unchanged LP-layout
cases). Results host tests executed:false, reuse unchanged qualification.
Actual offline analysis separately executed on59 ELF files and9 init/script
inputs; the unrelated sensordebug script is preserved in the archive but not
analyzed. Full readelf/strings output and three startup disassemblies are
compressed with deterministic gzip and hash-sealed. These are metadata reads,
not execution of Android binaries. No kernel build/full regression/Actions.

## Source-supported findings

* Actual X710 init starts `/vendor/bin/sscrpcd sensorspd`, class`early_hal`,
  whereas `/vendor/bin/adsprpcd` is class`main`. These declarations establish
  intended Android classes/arguments, not a mainline readiness requirement or
  complete observed Android timing. The current registered mainline diagnostic
  starts rootPD before sensorsPD; order is an explicit comparison target.
* sscrpcd disassembly checks `/sys/kernel/boot_slpi` to choose the listener
  library; the two APPS listener libraries respectively depend on libadsprpc
  and libsdsprpc. Their dependency names do not justify changing X710's proven
  ADSP routing or adding an SDSP. libsdsprpc and full transitive closure were
  outside the selected export scope; absence from archive is not source absence.
* sscrpcd resolves `adsp_default_listener_start` and a FastRPC wake-lock control
  entry. The actual selected listener's disassembly opens static-PD/default
  listener handles and registers/polls. Neither direct daemon imports nor this
  reviewed path establishes a mandatory sns_dynamic_loader/proc-state init call.
  A dynamic symbol/export alone is not a call sequence. Android wake-lock glue
  is not a demonstrated SSC publication prerequisite.
* Actual64-bit sensors.ssc.so/libssc.so/libsnsapi.so dynamic dependencies do not
  include sns_dynamic_loader_stub or sns_remote_proc_state_stub, and their
  dynamic symbol imports do not reference those APIs. Runtime dlopen remains
  possible; this does not prove they are never used. Both original APPS stubs
  are present, and must be distinguished from DSP Hexagon skel libraries.
* Qualcomm FastRPC primary source at
  `a56e9d4de3614a8d8f4b0e15ff561350c4b686e3` maps SENSORS_STATICPD to
  INIT_ATTACH_SNS in its upstream-kernel wrapper, matching the current
  Fedora-derived attach. The reviewed daemon start path likewise does not
  supply a required extra sns_dynamic_loader call. Full hashes in SOURCE_AUDIT.

Success is source-input collection with unchanged desktop. SSC400 publication,
accelerometer data and automatic rotation remain unfinished/unaccepted. No
root cause is claimed. Next compare actual stock default-listener lifetime,
static-PD startup order and callback APIs against the qualified0.4 implementation;
introduce a separately tested/registered changed boundary only when supported.
Do not repeat unchanged393 startup, invent DSP calls or reset factory registry.
