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

Test363 loaded the offline-built, symbol-checked pair on a fresh exact Test331
boot. The owner confirmed pen position, palm suppression and finger recovery;
raw proximity and touch-release events support this bounded result. Pen tip,
pressure and side-button events were not observed. Suspend and full calibration
remain untested. Historical GDM masks remain, so the installed Wants link does
not globally enable graphical startup; use the registered explicit service/GDM
start sequence. No current-boot driver replacement is supported.
