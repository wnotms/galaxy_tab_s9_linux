# Opt-in X710 Wacom + palm-aware FTS pair

This is a separate candidate from the accepted ordinary FTS loader. It loads
`wacom-wez01.ko` first, then `fts1ba90a-palm.ko`, whose external build imports
`wacom_wez01_should_suppress_touch`. The loader refuses to replace an already
loaded FTS module and therefore cannot disturb the accepted desktop touch path.

Install both exact Test362 artifacts, the loader as
`/usr/local/libexec/gts9-palm`, and the unit in `/etc/systemd/system/`. Enable
only in a newly registered desktop boot. The GDM Wants relationship avoids text
boots and charging experiments. No kernel config, DTS, firmware, charging or
USB/ADB setting is changed.

The pair is offline-built and symbol-checked, but has not been loaded on the
device. Physical pen hover, palm suppression, touch release, calibration,
suspend and recovery remain a separate acceptance scope.
