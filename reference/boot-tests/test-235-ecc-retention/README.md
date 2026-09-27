# Test 235: independent ECC retention calibration

Test-234 established exact live PMSG RAM before reset and damaged archived
bytes after reboot. It also captured a CPU 5 non-response in the observer's
disk journal; a common cause remains unproven. Production rollback must be
verified before this trial. Authorization continues the owner's CPU diagnosis
and physical-test instructions.

Candidate: diagnostic patch 0024 only, adding upstream DT ecc-size=64 to the
existing ramoops node. No lastactivity/live-read code, production cmdline and
config unchanged. Default builds keep ECC=0. No reservation/zone-size change;
ECC consumes capacity inside each existing zone. 128 data + 64 parity symbols
fit GF(256)'s 255-symbol limit; at most 32 erroneous symbols per block can be
corrected. Parity damage counts too. This is a hypothesis, not a repair verdict.

1. Verify candidate/build hashes, same config and exact DT difference. Back up
   using verified originals; flash only boot/vendor_boot in TWRP, then full
   readbacks and verify init_boot/dtbo/vbmeta unchanged.
2. First ECC boot can report errors for incompatible old ECC=0 data. Record
   those separately. Require runtime ECC=64, current source identity and a
   working PMSG sink. Write a freshly identified known binary probe once after
   device file hash validation. Save a small identified console marker as a
   separate sink calibration, without claiming CPU instrumentation coverage.
3. After a healthy source observation, perform one normal direct Debian warm
   reboot with the same candidate. Retrieve raw PMSG/console and exact boot
   history, require full source-byte integrity and zero unrecoverable blocks
   in the relevant recovered record. Archive correction notices and raw bytes.
   Missing/corrupt data fails. No missing CPU-event inference or wedge series.
4. Stop at first unexpected failure. Preserve disk/pstore evidence; manual
   recovery may be needed with the unchanged unarmed production profile.
5. Restore original boot/vendor_boot with full hashes and verify final health.

Passing one normal reboot proves only that observation. Lastactivity capture
and crash-triggered persistence still need separate validation before CPU
forensics rely on this sink. Do not use ECC=0 raw-ring decoding for ECC=64.
