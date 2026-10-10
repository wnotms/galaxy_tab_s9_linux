# SSC initialization inputs — offline Test389 replay

This is a new offline interpretation, not Test390 or another device startup.
Test389 raw evidence, original verdict, registration and result seal are unchanged.

The return parser now offers an exact virtual-path file-content allowlist. Its
existing registry API still rejects unknown files in the registry namespace and
requires successful transport acknowledgement and close. A successful unrelated
open cannot silently reuse a tracked descriptor. Matching bytes and completed
sessions are separate results; an unclosed file never becomes a completed session.

`replay.py` verifies the original Test389 result-seal hashes, re-decodes the full
raw unit journal with boot/process/sequence attribution, independently translates
the captured native SoC snapshot, and verifies the exact registered stock asset
archive and member hashes. It does not read or change the device. Reproduce into
a **new** directory:

```sh
python3 reference/desktop-bringup/ssc-init-inputs/replay.py \
  --output out/ssc-init-inputs-replay
```

| Actual returned initialization input | Bytes | Hash match | Closed/acknowledged session |
| --- | ---: | --- | --- |
| `/vendor/etc/sensors/sns_reg_config` | 329 | Yes | No close captured |
| `/sys/devices/soc0/hw_platform` (`MTP\n`) | 4 | Yes | Yes |
| `/sys/devices/soc0/platform_subtype` (`Unknown\n`) | 8 | Yes | Yes |
| `/sys/devices/soc0/platform_subtype_id` (`0\n`) | 2 | Yes | Yes |
| `/sys/devices/soc0/platform_version` (`65536\n`) | 6 | Yes | Yes |
| `/sys/devices/soc0/soc_id` (`519\n`) | 4 | Yes | Yes |
| `/mnt/vendor/persist/sensors/registry/sns_reg_version` | 10 | Yes | Yes |

The version-marker open uses `registry/registry/../sns_reg_version`; canonical
path matching accounts for that actual stock request. It returns `version=6`
plus its NUL byte, rather than a text newline. Only reported read bytes are
hashed, excluding the unused output-buffer tail.

**7/7 input byte hashes match, 6/7 sessions completed; complete:false remains.**
The config file opened at sequence7 with fd2 remains unclosed in this bounded
capture. This is an observation, not proof of a firmware bug or the reason SSC
is absent. Do not force-close it or change the file callback on this basis.
The unchanged registry API additionally replays all178/178 closed, acknowledged
stock groups successfully. These checks prove host-returned bytes, not DSP parsing,
sensor hardware initialization, SSC publication or automatic rotation.

114 affected host tests passed, zero skips:53 return/profile/real-C/framing/content
tests,24 wire dependencies,11 stat tests and26 runtime/overlay consumers. Eight
new tests cover exact input bytes, canonical marker alias, path substitution,
unclosed matching data, missing/error/pending/corrupt replies, unrelated descriptor
reuse, invalid manifests and empty expectations. No routing changes, full host
regression, kernel or daemon rebuild, or GitHub Actions. Existing unchanged
Test389 ARM64 daemon/library/kernel/config/DTB/modules qualification is reused;
the updated parser runs only on the host.

A short live read confirms ADB shell, accepted370 boot
`0f360b00-4f24-43cf-8ce5-1aa135c5f7a3`, GDM active, sensor RPC inactive, ADSP offline,
100% battery and31.8°C. This is not a fresh partition/module acceptance. No reboot,
flash, service restart, registry reset, foreign firmware, guessed `ro.revision`
or sensor bus parameters, kernel/config/DTS/charging/USB/input change occurred.

Next investigate the firmware's initialization/selected-configuration semantics
and exact X710 prerequisites. A new physical test needs a concrete changed input
or newly observable boundary; another identical transport startup adds no evidence.
Sensor migration and automatic rotation remain unfinished; PPS/pump/DCC remain OFF.
