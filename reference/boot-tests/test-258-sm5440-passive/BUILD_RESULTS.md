# Test258 offline qualification

Compiled source: f3a266b5, isolated sm5440-passive profile, Linux7.2-rc3
pin a13c140cc289c0b7b3770bce5b3ad42ab35074aa, clang21.1.8, ccache, JOBS=8,
BUILD_MODULES=1. Full Image/DTB/modules build and standard bundle validation
passed. 181 matched module-directory files; 96 protected files unchanged;
all85 Test254 container requirements retained, HVC_DCC=n.

Exact Test255 config delta: CHARGER_SM5440_DIRECT absent->y,
X710_CHARGING_POLICY absent->n (new inactive declaration). DT delta only
hub3 charger@63 status disabled->okay; GPI DMA retained. No unexpected delta.
Only boot/vendor_boot/modules may be deployed. Original ramdisk/cmdline/
bootconfig remain; init_boot/dtbo/vbmeta are retained, not flashed.

Full1264 host tests passed with zero failures/errors/skips in88.225s. The
wrapper previously executed the same1264; this duplicate run is recorded,
but future workflow uses one final run. Original1255 tests retained +9 passive
admission tests. No CI. Raw logs, config, notes, module manifest and artifact
report are under validation; ARTIFACTS.json records exact deployment hashes.

Owner requested change-scoped checking: subsequent documentation/results
commits reuse these unchanged source/artifact qualifications and do not rebuild
or repeat full regression. Such commits record executed:false; they are not
new host passes. Device observation and OFF-backed telemetry remain separate
from compiled/host-tested status. ADC calibration and active PPS/pump remain
NOT READY.
