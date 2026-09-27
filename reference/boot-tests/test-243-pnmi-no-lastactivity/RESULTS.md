# Test 243: recorder disabled; one 306.92-second window did not reproduce fault

Target 2094eeee-8fe2-48e5-aea6-abbc1788ea92 stayed responsive through 306.92
seconds without detected CPU/RCU/workqueue failure or suspect timeout. This
is not a CPU fix, rate comparison or proof the recorder hides/causes faults.

The exact test241/242 kernel was reused. Only lastactivity=1 changed to 0;
calibration stayed disabled. The actual la_setup/la_init host harness proved
no UUID/board/probe work for disabled inputs and seven registrations for an
enabled control. Runtime verified empty recorder ID, both disable flags,
helper enable=N/started=0, GIC pseudo-NMI/priority masking, ECC64, arming
1/1/1/10 and console 5/4. Notes matched; six anchors gave +0x188000. Source
commit before flash was 785dcac. The paused preparation resumed with a fresh
TWRP identity/battery (100%) and all-five partition check before staging.

No synthetic or manual CPU action occurred. One priority-0 userspace marker
labels this boot and exact notes hash. All 1,103 complete live JSON entries
carry the target boot ID and kernel source time; the final query has 1,105
entries. The marker occurs once in each, and neither contains a fault or
recorder READY. The host stream was intentionally stopped at the observation
end. All command stdout/stderr/status, symbols/hash references, artifacts,
full source-clock JSON and validation are archived. Defaults/rootfs/USB and
non-boot partitions remain unchanged.

The single candidate-boot budget is complete. Separately registered test244
will exercise one direct normal Debian reboot, a transition that produced
CPU5 non-response in test234. This is a new transition-specific capture,
not an extension of this window or a rate estimate. Original restoration is
deferred to the end of that shared session, avoiding needless restore/reflash
writes. Test244 must stop on its first non-clean result and restore originals;
its five-hash and independent production result will close both trials.


Shared rollback completed in test244: all five original partition hashes
match and production `1aaffb9a-3a07-4415-91a8-7bf40d14328e` passed 179.21
seconds without detected CPU failure. ADB/NCM SSH protocol respond. See
[paired result](../test-244-pnmi-direct-reboot/RESULTS.md) and its raw restore/
and production/ evidence. No healthy window establishes CPU-stall repair.
