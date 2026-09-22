# Test 042 — pre-panel host/PHY power cycle also fails

Source 4b05fd1, boot only, validated bundle and write/readback hashes.
Pretest backups for every boot-chain partition are preserved off-device.
Recovery plan is to restore pretest boot through TWRP; recovery and vbmeta
were never written. Raw logs and report hash verification are archived.

X710 first-enable link cycle executes at 5.373 s, but ID is still zero at
5.514 s. Normal framebuffer blank recovery reads 80 00 04 at 8.033 s.
This disproves the claim that simply powering down the inherited host/PHY
before panel prepare is sufficient. A full modeset teardown also changes
panel sleep/power state and host enable state. No owner visual verdict yet.
Final state: returned to TWRP using USB console and BCB; test boot remains.
last_kmsg is recovery/bootloader evidence only; see pstore-status for availability.
