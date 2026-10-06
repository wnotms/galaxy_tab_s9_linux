# PPS snapshot adapter correction (offline)

Base: `00cecaa4`, first-failure Test330 sealed. Live accepted Test323 was
restored; this correction performs no device operation or repeat PPS trial.

Scope:

1. Use the existing leased PPS snapshot API for **both** source reads around
   the pack sample during PPS. Fixed contracts retain the public fixed-only
   API. Preserve lease, instance, source/budget generation and pack checks.
2. Make the actual C mocks honor the fixed-only API and inject first/second
   owned-read failure and detach during the pack read. Preserve pump-OFF and
   checked fallback behavior.
3. Add `scripts/x710-pps-guard.py` as the current observer. Historical
   Test328/Test330 observers remain immutable. Classify active TCPM mode by
   ONLINE, accepting PPS-capable USB_TYPE at fixed ONLINE=1. Require fixed9V,
   coherent 100mA–1.5A current and restored SM5714 switching supply separately.
4. Run affected tests and one incremental standard ARM64 build using the
   existing Fedora cache, plus changed-object W=1/sparse and config/DT/module
   pairing/protected-source qualification. Preserve old formal artifacts.
5. Package a default-OFF candidate offline. No flash, reboot, rootfs, USB/ADB,
   TCPC/TCPM-core, DTS, configuration, ADC or safety-threshold changes.

Independent unresolved issue: physical fixed-return proof requires ±100mV
and zero raw pump current. Test330 protocol returned fixed9V but continuous
ADC remained approximately9.272–9.293V; switching release failed. The new
+272mV injected test must continue returning timeout with pump OFF and lease
held. Do not add offsets or weaken proof. Fedora's simpler fallback has no
such independent proof and is not sufficient justification to delete it.

A passing build/tests qualifies only this adapter correction. Full direct
charging remains NOT_READY. Any subsequent physical scope needs a new
registration, first-failure cleanup and accepted Test323 paired rollback;
the old consumed327-original backup is not a future deployment resource.
