# Incomplete same-boot reconnect observation

The monitor only recorded USB offline while waiting for the owner to reconnect
the PC. It ended before an attach/recovery window was recorded. No 150-second
PC reconnect or native ADB/NCM recovery bound was completed by these rows.

The owner subsequently reported one manual reboot and authorized continuation
from the following items. The newly observed boot is `d745248e…`; do not
rewrite attempt01's monitor as a same-boot pass. Attempt02 records fresh
identity and bounded PC USB checks without commanding another reboot.
