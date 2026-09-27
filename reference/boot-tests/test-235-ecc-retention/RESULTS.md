# Test 235: ECC trial, retrieval and rollback pending

Candidate kernel Image.gz matches the earlier production rebuild exactly;
decoded DTB differs only by ecc-size=64. Source
`059c1400-1ccf-4861-9590-1fe2592611b7` confirmed ECC=64, mem_type=0,
2 MiB at 0x880900000 and a working /dev/pmsg0. It remained responsive beyond
151 seconds, with zero failed units and no detected CPU stall in the journal.
First-boot header errors concern incompatible older ECC=0 records.

Source wrote capture `55366034-ba7d-490e-a130-564f3956bd37`, 33,005 bytes,
SHA-256 `7322a93f988d377a96d4ea2df30d092cbadbee4304e3538332a605104b35be01`,
after device file hash verification, plus 16 identified known console lines.
The exact console lines appeared in the source's pre-reboot journal.

Normal reboot reached observer `bd682a9a-82c5-4955-8f5e-b5777f67b559`.
At uptime 6.53 it answered ECC=64 and new pstore file metadata/hashes:

| Archive | Bytes | SHA-256 |
|---|---:|---|
| PMSG | 33055 | 9032410eaa7666d8d0622afa00adee3ba34081607116c330816afeb5544399a4 |
| console | 5076 | 7fd0a63545d7a7e74672980685e8b5191733c1c895fe5449585c600f68ccd55f |

The subsequent journal boot-list command timed out. USB file pulls, exec-out
dmesg and TCP ADB then failed/timed out. Raw pstore has not yet been retrieved;
file sizes and hashes alone cannot establish ECC success. No positive CPU
failure signature from this observer has been captured yet. Classify its loss
of responsiveness as unattributed pending disk evidence, not a clean boot.

Manual TWRP was requested to read disk pstore/journal and restore production.
**ECC candidate remains installed; rollback is pending.** Only boot and
vendor_boot were flashed; complete readbacks passed and init_boot/dtbo/vbmeta
matched production. No rootfs/USB configuration changed. Do not start another
diagnostic boot or wedge series while this observation is unresolved.
