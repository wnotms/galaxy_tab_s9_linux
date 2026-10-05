# Test320 — USB recovered after one unchanged normal reboot

The first charger-to-PC incident remains stopped in Test319. Code43 persisted
through owner-confirmed cable/port reconnection. One normal `systemctl reboot`
over authenticated Wi-Fi was registered and pushed before execution. No flash,
BCB/modules/rootfs/kernel/USB/adbd/charging configuration changed; no PPS/pump ON.

Exactly one new boot: `647d50c8-0fc9-4fb0-bfea-5006c519a255` ->
`8146a9cf-c160-4e13-a351-0db1a8f958a7`, uniquely attributed by journal history.
Exact accepted311 embedded config/notes and accepted NORMAL command line match;
ABL lpcharge is now0. This correlation does not establish USB root cause.

Native USB ADB shell proves new boot/machine within25.783s of reboot request.
Windows composite/ADB/NCM devices all Code0; no Code43; NCM adapterUp.
Authenticated Wi-Fi at new DHCP address10.139.153.11 proves same boot/machine
within125.952s, WindowsCode0 capture within128.680s. All within150s registration.
The initial controller kept probing old .121 and reported unavailable at154.495s:
raw summary preserved, explicitly resolved by real native/new-address evidence,
not overwritten or replayed. Do not interpret its host false negative as a wedge.

The registered15s same-boot endpoint passes: ADB/Wi-Fi/deviceNCM/sshd,
Sink/Device, no failed units, HVC DCC absent, pack22%/3.767V/31.1C/Good and
real pack thermal enabled. Passive pumpOFF/IBUS0/fault0 remain. Full previous,
new and endpoint kernel JSON retained. No new CPU-stall/panic/Oops/unclassified
fault signature detected. Known10 early MDSS/SMMU diagnostic contexts retained
with UNKNOWN root cause; this is not an overall stability-clean claim.

Result: **USB_RECOVERED_UNCHANGED_NORMAL_BOOT**. Recovery is not a permanent
USB driver fix, not charger-to-PC regression acceptance, not charging qualification.
Test318 remains undeployed. Prior software/artifact qualification is unchanged;
no partition/module rehash loop, no full build/regression/Actions. Seven existing
identity tests PASS0.004s/0skip; capture helper syntax and evidence hashes checked.

Next: use fresh native ADB Wi-Fi discovery after reboot to avoid stale DHCP
polling. Investigate charger-to-PC descriptor failure separately using retained
host/device timeline, with a new registered scope if reproducing; do not reuse
this recovery as proof of a fixed root cause or relax Test318 rescue gates.
