# Test314 — SM5440 OFF-only settings qualification

Purpose: implement and offline qualify the register preparation/restoration
layer missing from the direct-charge port. This is not another ADC condition
trial and has no physical execution registration or activation authority.

Accepted311 ordinary charging stays installed; Test313 remains terminal STOP.
Use the existing default-inactive sm5440-policy-offline build profile. Add no
config symbol or device-tree change. The three audited settings are input
limit1000..1800mA rounded down, battery regulation4437.5mV and vendor450/650/
850kHz frequency mapping. Original settings and ten untouched control witnesses
are read back; uncertain writes/failed cleanup preserve pending/error/OFF proof.

Follow docs/SM5440_OFF_SETTINGS_TRANSACTION.md. New actual-C fault tests and
only affected passive/ADC/consumer/prepare classes qualify the implementation.
Record standard8-job ARM64 Image/DTB/modules, embedded config, notes, exact
config/DT diff, source/protected hashes and module pairing. Freeze Test312
symbols/CRC/generated inputs before reusing the one incremental cache.

No live caller/export/probe hook, PPS request, CHG_ON, automatic charging start,
watchdog/ENHIZ/reset/protection masking or rootfs/USB/DCC/SM5714 change. No
flash/reboot/partition/module replacement. No physical pass or direct readiness.
The next hardware adapter still needs qualified physical ADC and software OCP,
source/lease/pack/pre-status context and drain/PM/fallback ownership.
