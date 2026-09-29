# Test255 attempt02: bounded PC USB checks after owner reboot

**Passed within the registered scope. Full fixed-PD acceptance remains
incomplete.** The owner reported one manual reboot and asked to continue
the following items. No deployment, reboot, service change, charge policy
change or charger connection was commanded in this attempt.

The new Debian boot `d745248e6a164243b9ccc5e6ede21fb2` uniquely follows
attempt01 boot `a5b8b87f…` in persistent journal history. Both boots' complete
source-timestamped kernel journals were saved. Neither has a detected new
fault or suspect after applying the previously accepted bounded startup
classifications. This attribution follows the owner's report; it is not an
autonomous reboot stability round or evidence of same-boot cable recovery.

## Physical evidence

| Gate | Observed result |
| --- | --- |
| Initial/final identity | 27/26 gates passed, same current boot |
| PC observation | 162.143 seconds, 10 successful repeated samples |
| ADB | Native shell responses; binary `/proc/config.gz` transfer decompresses to the exact candidate config hash |
| NCM | Authenticated SSH plus Windows interface-bound TCP/SSH banner, repeated successfully |
| Wi-Fi | Authenticated SSH, same boot throughout |
| Type-C | Sink, Device/UFP; no Host/Source transition observed |
| Windows USB | ADB/NCM/composite devices OK, no Code43 |
| PC charge path | SDP, ordinary SM5714 input limit 500 mA |
| Battery | Good health; 32.2–32.4°C during the window; VBAT below 4.44 V |
| Kernel/systemd | Complete ending journal has no new fault/suspect; no failed unit |
| Rootfs/Test253 | Protected USB/SSH settings and both adbd/helper hashes unchanged; adbd active |

PC charging status coexists with negative net pack current under the active
system load; the raw readings remain unmodified. This is not a passed positive
charging-power test. The existing startup boot-register/SMMU variants, clk-rcg2
and display/aux-bridge warnings are recorded rather than claimed repaired.
The QCA initialization warning completed within the accepted source-time
bounds. Initial and final analysis outputs retain counts and every suspect.

## Exact installed identity and rescue

| Item | SHA-256 |
| --- | --- |
| boot | `26ef6bd143a9575b997b8cf73f24686d647f1ac742f0e7d92d44aa600ef7c063` |
| vendor_boot | `d80d03cdf0ac810d9ac741074a9b97327c48880a98a4459db219ed7813461a46` |
| Embedded config | `cd7ec9cbd259475a027862ddaf125eb5ad63ae3dc63e33cea5073ef492cdde3f` |
| Kernel notes | `fb3d249642e900d9bb591fb629c1865b370b50098d44970b986cc793f45c160c` |

All 181 candidate module hashes match. Exact Test254, Test252 and Test249
181-file rollback directories remain present. Test254 images remain under
`D:\android\gts9-active\gts9-test255\`; no rollback occurred. `init_boot`,
`dtbo`, `vbmeta`, cmdline and protected rootfs settings retain accepted values.
Linux stays 7.2-rc3, HVC_DCC stays disabled with hvc0/getty absent, and the
Stage1 thermistor plus Test254 USER_NS/POSIX_MQUEUE configuration remains.
No hardware or software configuration was altered by these checks.

## Host validation and remaining gates

`bash scripts/check-stall-offline.sh --changed --base HEAD~1` executed all
1183 retained tests through the documented changed-path fallback, with zero
failures/errors/skips, in 98.483 seconds. Raw output and a derived summary are
under `host-validation/`. This supersedes the earlier host-run interruption
only for this fresh invocation; the original interrupted record is preserved.

Attempt01's independent 155.473-second battery-only pass remains valid.
Its following same-boot PC reconnect was interrupted before completion by
the manual reboot; these new PC checks cannot substitute for that gate or
charger-to-PC reconnect. No independent 5V-only source or actual-VBUS meter
is available, so the 5V-only, negotiated 9V, 5/20-minute PD charging, and
charger-to-PC gates remain unexecuted. The Lenovo 18W PD supply was not
connected by this attempt. An 18W rating does not supply an independent
actual-VBUS measurement for the registered 9.5 V stop gate.

No Stage3, SM5440/PPS, source/OTG, DP/dock, protection-limit testing or GitHub
Actions were started. These are bounded observations, not a general safety
or reliability proof. See `summary.json`, the initial/final raw captures and
`pc-window/` for the exact evidence.
