# SSC native-to-Samsung SoC identity mapping

The current accepted kernel has QCOM_SOCINFO disabled. No live native SoC
snapshot is available yet. This step adds a host-only converter, not guessed
X710 identity files or device activation. Native SoCinfo enablement is deferred
until the active Test348 charging candidate is restored.

`userspace/sensors/map-socinfo.py` accepts a captured JSON snapshot and creates
five Samsung-compatible regular files. It reads no sysfs and installs nothing.
All 23 hardware-platform ID/name entries match Samsung's `hw_platform[]`
table exactly, including its `SLVTE_SURF` spelling. Samsung's separate QRD and
ordinary subtype tables are retained. Unknown/invalid/sparse entries are
rejected rather than presented as an established board identity.

| Samsung virtual file | Mainline source | Interpretation |
| --- | --- | --- |
| soc_id | soc0/soc_id | Same SMEM ID; this X710 converter requires SM8550 ID 519 |
| hw_platform | qcom_socinfo/hardware_platform | Samsung string table indexed by native raw ID |
| platform_subtype | qcom_socinfo/hardware_platform_subtype | Samsung QRD/ordinary string table |
| platform_subtype_id | same raw subtype | Decimal integer |
| platform_version | qcom_socinfo/platform_version | Raw u32, **not** SoC silicon revision |

Native platform fields are in debugfs, not mainline SoC-bus sysfs. `info_fmt`
is hexadecimal; raw platform fields are decimal. Formats 0.6–0.23 are admitted,
as covered by this pinned mainline driver; partial/unknown formats, another
SoC/family/machine, malformed integers and overflow fail before output creation.
A captured boot UUID is mandatory. A host JSON file cannot independently prove
physical identity; every output manifest explicitly leaves that unverified.

Source hashes and the mainline commit are in `SOURCE_AUDIT.json`. The source
auditor compared the complete platform table, native debugfs field names and
SM8550 ID constant. Samsung getters show that platform version and subtype ID
are raw decimal values, while platform/subtype names use their string tables.
No vendor framework or kernel code was copied into the device.

12 affected host tests passed, zero skips. They cover known/Qrd mappings,
unknown and sparse IDs, format boundaries, other SoCs, missing/invalid/overflow
fields, raw version semantics, exact output files and refusal to overwrite.
No kernel/full regression build or test was executed; no routing changed.

Next: after Test348 restoration, enable the stock mainline QCOM_SOCINFO driver
in the authorized kernel rebuild, capture one boot-stable native snapshot,
then qualify these five real identity values before private registry deployment.
Do not create fixture identity files on the tablet. ADSP/FastRPC/SSC and GNOME
rotation remain untested; no early/late ADSP start was attempted here.
