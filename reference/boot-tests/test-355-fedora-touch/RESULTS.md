# Test355 stopped before module load

Owner reported “设备刚才自行关机了，已重启” before any touch transfer or insmod. This registration is closed with zero load attempts; never rerun it on the new boot. Fresh authenticated Wi-Fi at owner-supplied 10.175.236.157 identifies boot1adc0f13-a210-4856-bb15-c6e9df17867a with unchanged exact331 config/notes, 83%,32.4°C,Good/Discharging,4.169V. /sys/module/fts1ba90a and /var/log/gts9-test355-touch are absent.

The previous boot journal records a short power-key event at7546.954717s, the GNOME gsd-media-keys VM shutdown warning, logind's poweroff request at7546.983284s, and orderly systemd poweroff/journal shutdown. Current systemd-detect-virt returns vm-other; GNOME48.1 default power-button-action is suspend. Upstream do_config_power_button_action explicitly maps every non-nothing power-key action on vm chassis to PowerOff. Current logind ignore setting and gts9-power-key backlight service are already correct; GNOME bypasses that low-level default. No recorded panic/stall/Oops/BUG signature in full previous/current kernel journal; pstore empty. This does not establish who pressed the key or exclude faults outside retained logs.

Preserve raw restart-incident.tar.gz (full kernel journals, last3000 prior system entries and full targeted power units, command return codes/pstore), new identity and all failed transports. Different boot requires fresh registration before touch load. Fix the desktop policy only; do not alter power-key driver/logind/kernel/charging. Prior desktop manual success remains valid with this independently documented regression.

Host tests/build executed:false for incident recording. Existing eight decoder tests and37-import exact331 CRC qualification remain evidence; no physical touch acceptance.
