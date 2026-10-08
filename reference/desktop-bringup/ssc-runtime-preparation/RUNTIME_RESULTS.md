# SSC controlled runtime overrides — host only

`userspace/sensors/prepare-runtime.py` produced five drop-ins in
`out/ssc-runtime-overrides`. Per-file hashes are in `RUNTIME_OVERRIDES.json`.
The four ADSP/mapper/proxy units are gated by a future runner's volatile ready
marker, have `Restart=no`, and allow one start per manager lifetime. SDSP has
its own absent gate. No marker, enablement, ADSP helper or installation exists
in this output. No tablet command was issued for this preparation.

HexagonRPC uses its documented `-R` option to serve the already qualified
X710 asset prefix. Both daemon commands replace their original ExecStart;
sensorsPD alone has `-s`. Their system view is read-only except the copied
sensor subtree. Provision ownership and verify SoC identity before any future
use. Original source versions, compiled binaries and Debian packages unchanged.

Validation: 32 affected tests passed, zero skipped (runtime overrides 6,
Debian packaging 16, asset staging 10). Host systemd 259 accepted the five
qualified original templates plus generated drop-ins in a private `--root`
with inert executable/account/dependency fixtures. Exit status 0; no output.
This is syntax validation, not a running sandbox/daemon/ADSP test.

Kernel rebuild/full regression: `executed: false`; no kernel, config, DTS,
module, charging candidate, routing or compiled component changed. No CI.
Test348's independent authorized charging observation continues unchanged.
Deployment still requires native SoCinfo/identity mapping and a separately
registered controlled early boot; do not late-start ADSP on a live desktop.
