# Test394 — actual recovery SoC fields match native mapping

One registered recovery round trip completed. Before boot
`b8af4759-1bd2-444e-b33f-e8a0b1a81c86` passed exact five partitions,181 module
hashes/config/notes, GNOME/ADB/device NCM, ordinary battery and full same-boot
kernel health/noCode43. The53 selected host tests passed,0skips.

X710 recovery boot `f4d3264c-cb14-4a57-9213-6da6494f05f2` passed the existing
three-snapshot root/device/kernel gate. Its **actual Samsung socinfo sysfs
bytes** match all five values translated from the fresh mainline SMEM snapshot:

| Attribute | Recovery bytes / native mapping |
| --- | --- |
| soc_id | `519\n` |
| hw_platform | `MTP\n` |
| platform_subtype | `Unknown\n` |
| platform_subtype_id | `0\n` |
| platform_version | `65536\n` |

Full raw recovery dmesg and available persistent logs are preserved; missing
pstore/last_kmsg entries are explicitly labelled. Hex encoding preserves the
sysfs bytes despite ADB CRLF conversion. No field was guessed or repaired.
Recovery is a Samsung-kernel snapshot, **not a full stock Android boot**.
This verifies these five mapped identities; it does not prove firmware parsing,
SSC publication, sensor bus readiness, accelerometer data or automatic rotation.

No image was flashed or restored; no modules/rootfs/registry/configuration was
modified. ADSP/RPC never started; no TCPC/charging/input change. Only existing
boot-mode BCB request/clear was written. The same verified recovery's five
partitions still matched before return, and the full2048-byte BCB clear was
read back. Ordinary return boot `26754f29-f759-472c-8098-16ad4cecdd62` is the sole
new Debian journal boot, with unchanged five partitions/config/notes and normal
GDM/palm/ADB/device NCM. No failed unit or CPU/new severe kernel signature.
ADSP remains offline and direct charging remains disabled. Return sample:
100%,31.4°C,VBAT4.446V within the registered passive observation bounds.
The existing4.44V float setpoint is unchanged. This is service/identity evidence,
not a newly requested visual desktop/physical input acceptance.

Results-only tests/build/full regression executed:false; reuse the53 affected
host qualification and unchanged Test370 kernel/modules. No new image or
Windows staging directory; no GitHub Actions. Registration seal unchanged.
`execution-state.json` confirms return_required:false; no live physical runner.

Next: compare firmware/SNS initialization and FastRPC/SSC-related platform paths
against the exact same-model Fedora inputs. Do not edit these now-confirmed five
identity values, reset the registry, guess foreign firmware or repeat this
unchanged observation. Test393 UP snapshots plus matching SoC inputs still do
not complete sensor/rotation bring-up; the overall migration goal remains open.
