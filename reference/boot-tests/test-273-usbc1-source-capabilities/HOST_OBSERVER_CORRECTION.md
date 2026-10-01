# Preparation observer correction

Registration source is b7e27663; REGISTRATION_SHA256.json remains its historical
seal and is verified against that revision, not silently replaced. Original
capture.py/host_tests.py are additionally archived byte-for-byte in observer-initial.

Original prepare/summary.json STOP_FIRST_NON_CLEAN/error=DCC absence changed,
zero samples, retained. The command collected no @@dcc section at all; identity
config/notes stayed exact263, device was healthy/OFF. It did not detect restored
DCC. No ring read, cable request or charging window occurred before this stop.

Add the missing read-only DCC paths/getty query to CURRENT. The original prepared
folder cannot be overwritten. One fresh prepare-completion namespace collects the
missing evidence and first PC log boundary; source/PC refer to that namespace.
This is a host observer correction, not a new hardware attempt or a relaxed gate.
Do not reflash, reboot, change services, request PPS or enable pump. Validate affected
collector gates/syntax; unchanged parser/kernel/all qualification reused.
