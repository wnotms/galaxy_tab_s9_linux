# Read-only PC preflight — stopped before Test336 installation

Boot `3d359c9296fe43ce871c0a40a9fb5bd4`, Linux7.2-rc3, accepted331 config51/
notes03, exact allfive accepted partition hashes and all181 accepted module
hashes match. ADB shell and strict enrolled WiFi `10.91.255.247` authenticate;
Windows Code0/no43, device NCM/services present, no failed units. Physical
SM5440 CNTL5=01/OFF; direct_charge=N, fixed/PPS checks absent. Complete kernel
journal has no classified fault or suspect. No software/device mutation.

First packet: SOC56%, VBAT3.969V, temperature25.4°C, net current+0.935A,
Charging/Good. These values belong to the saved packet, not an enduring entry
guarantee. Fresh pack/boot gates remain mandatory before any future action.

Preflight stopped at the exact command-line gate. Multiple `lpcharge=1` tokens
are present, including the three PDIC/NFC/flicker parameters previously0 and
additional vendor charging-mode tokens. Thus this is not the registered normal
boot even though installed software matches. The launch source/cause has not
been proven; do not infer manual action or CPU/USB failure from these arguments.

No Test336 PPS transaction, native check, flash, reboot, module swap or live
driver/service modification was attempted. Original stopped packet is retained;
any later successful preflight must use a new refresh namespace. A normal-boot
recovery proposal is separate and needs owner approval: see
normal-boot-recovery-plan.json. This is not approval for Test336 PPS deployment.

Tests/build executed:false — evidence and recovery plan only, reusing unchanged
57-test/qualified-kernel inputs. No full suite or GitHub Actions.
