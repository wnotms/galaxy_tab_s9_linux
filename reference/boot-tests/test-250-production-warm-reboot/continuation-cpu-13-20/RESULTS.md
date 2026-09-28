# Test250 CPU-focused continuation: 20 attributed warm reboots observed

**Result under the owner's revised criterion:** twelve previously CLEAN attempt-05 rounds plus eight new CPU-focused rounds, numbered 13–20, completed 20 consecutive, boot-attributed ordinary production warm reboots. Every new boot was observed from startup to at least 150 seconds. No CPU non-response, soft/RCU/CSD/workqueue lockup, hung task, panic, Oops, BUG or SError signature was detected in the captured complete kernel journals. The offline replay passed. This is **not** a retroactive 20-CLEAN result under attempt 05's original strict transport rule: attempt 05 remains stopped before its thirteenth reboot on an unresolved Windows host-probe timeout.

## Authorization and baseline

After attempt 05 stopped, the owner explicitly instructed: “继续第十三轮，后续只要未触发之前的cpu卡死即视为完成测试”. The separately registered continuation was committed and pushed before physical work. Its full read-only preflight, also committed and pushed before reboot 13, verified the same source boot `a48bfed924f64996833e789baf2ab011`. No attempt-05 result or file was rewritten. The only device mutations were eight normal `systemctl reboot` requests; no kernel, config, DTB, partition, module, rootfs, USB or diagnostic setting was changed or flashed. No rollback was needed.

The production baseline throughout was the accepted Test249 Linux `7.2.0-rc3-gts9wifi-dirty`, build-notes SHA-256 `dc063ad84cb33354b646380261b7378dbe27889925c193ec4253c9c90ce40e97`, complete embedded config SHA-256 `95de6695511a60c5b5025b63c5e65b1bdf89e4335a5a191bda5cc75deeb4ef82`, exact five accepted partition hashes and all 181 matching module files. `CONFIG_HVC_DCC=n`; hvc0 device/sysfs/getty and DCC write symbols remained absent. The temporary diagnostic profile and backup module directory remained absent. Full five-partition/module/config/notes checks passed at continuation preflight and final acceptance; each round rechecked kernel identity, DCC, runtime profile, source/new boot attribution and failed units.

## Newly executed rounds

| Round | New boot ID | Observed uptime (s) | Result |
| --- | --- | ---: | --- |
| 13 | `31a895998bdf41f58149cb12e6347b86` | 150.10 | `cpu_clear` |
| 14 | `f7ed4e2a3ce746879dd262b3941b5a66` | 150.10 | `cpu_clear` |
| 15 | `ac60e29d0a6649baa99d9651b22c0ca6` | 150.09 | `cpu_clear` |
| 16 | `a11116d6a95d4895a047f8dcdbdeff71` | 150.10 | `cpu_clear` |
| 17 | `fafcbbfa5ed849629e2d5f5234c89d05` | 150.10 | `cpu_clear` |
| 18 | `e7764b9dfc4741128b7c7a7df08b4efb` | 150.10 | `cpu_clear` |
| 19 | `937e137f21e04540b548d13d33d918fc` | 150.10 | `cpu_clear` |
| 20 | `8810021ce7cc43ed996a1984e0aba4a2` | 150.10 | `cpu_clear` |

Each row has a distinct changed boot ID, exactly one new journal-history boot, source and just-ended-target journals kept separately, full new-boot kernel JSON/text and live follow capture, five-second boot-ID polls, DCC/systemd/USB/ADB/SSH evidence and a machine verdict. Complete new-boot scans found zero CPU fault counts and zero kernel suspects. The bounded QCA `0xfc48` startup messages, where present, satisfied the previously approved per-cycle rule; the accepted startup SMMU/register-warning class is still present and is not claimed repaired. ADB, source-bound NCM SSH banner and authenticated SSH passed on the first measured attempt in all eight new rounds; no Code43 or NCM transient was observed in this continuation. The earlier attempt-05 round-13 Windows probe timeout remains unresolved and recorded as a separate host observation anomaly, not reclassified as CLEAN.

## Final acceptance and audit

The final boot ID was `8810021ce7cc43ed996a1984e0aba4a2`. At 178.86 seconds uptime, full read-only acceptance again matched all five Test249 partition hashes, the exact 181 module hashes, embedded config and kernel notes; DCC and hvc0 remained absent, no systemd failed unit or new kernel fault was found, and ADB/NCM/SSH passed. `audit-evidence.py` replayed the previous twelve-round chain, confirmed the unchanged attempt-05 stop with no thirteenth reboot there, checked all eight reboot commands, source/ended/new journals, one-boot transitions, 150-second windows, identity and DCC, then verified SHA-256 seals on all continuation evidence. It passed without device access. The machine-readable `summary.json` retains the original strict 12-CLEAN count separately from the revised 8 `cpu_clear` count; `EVIDENCE_AUDIT.json` records replay results.

The runner and host tests passed the complete 1,056-test local suite with no failures, errors or skips; changed-scope offline checks also passed. No GitHub Actions was started or awaited. All evidence is committed to `origin/test`; `main` was not changed.

These are bounded warm-reboot observations, not a failure-rate estimate, long-term reliability proof or guarantee against future stalls. They do not cover cold boot, battery-only boot or Type-C power transitions, and do not prove that all historical CPU wedges had the DCC cause. Test247 directly proved the DCC TX-busy CPU4 stall path, and Test249's production repair remains the deployed baseline. A separately registered **Test251 production cold/power-path stability regression** is the next suggested phase; it was neither created nor run here.
