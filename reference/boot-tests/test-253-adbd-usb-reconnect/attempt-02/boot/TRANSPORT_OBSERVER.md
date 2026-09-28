# DHCP transport discovery

The first native USB shell proved the same new boot and custom daemon identity,
and read wlp1s0=10.191.121.29. The old-address SSH probe was unavailable because
DHCP assigned a different IPv4 address. Its original failure is retained; no
Wi-Fi, NCM, SSH or DHCP configuration was changed. The observer was extended
only to read GTS9_TEST253_WIFI as its destination. Its complete executed source
is preserved as tools/check-runtime.py; the pushed predeploy tools/check.py and
PREDEPLOY_SHA256 seal remain byte-exact. boot-initial/ used that runtime source
with GTS9_TEST253_WIFI=10.191.121.29. All identity/fault/transport gates are
otherwise identical, and the discovered destination is bound to the native
USB shell's boot ID. Subsequent captures invoke check-runtime.py explicitly.
