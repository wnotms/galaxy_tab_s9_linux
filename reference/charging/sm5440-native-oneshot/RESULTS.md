# Isolated native one-shot candidate — offline qualification

**OFFLINE_NATIVE_ONESHOT_PASS; full charging port NOT_READY.** Current device
remains accepted Test323; only read-only controls/identity/pack observations ran.
The last live packet is the same fca646a8 boot/config/notes, 56% SOC, 4.010V,
32.0C/Good and net +1.238A on PC USB with input limit 1.8A. No PPS/pump request.

The new explicit `sm5440-adc-oneshot` profile invokes the **unchanged** native
converter from the bound passive worker after healthy startup. Four once-only
OFF acquisitions use separate 100ms deadlines, retained INT/status/raw data,
fresh pack/source brackets, checked cleanup and first-error termination.
It does not link the native actuator/controller or publish charging qualification.
Generation pointers are cleared before heap evidence is freed. No core mutex is
held while allocating, sleeping or calling source/pack providers.

The current ordinary passive sample is fault-latched startup data, not fresh:
32 read-only control observations showed 0c/0c with an unchanged sample stamp,
872–873s age, fault=1 and startup_pending=1. This is **not** ADC self-clear proof.
Last old ADC/gauge pair differs by about27.5mV, first startup pair about329mV;
neither is calibration. Previous continuous READY timeout remains a failure.
The measured zero IRQ masks differ from vendor initialization; no causal claim
or speculative mask/ENHIZ/protection write is made.

## Executed checks

- 139 affected host tests, zero failures/errors/skips, 6.485s: actual new wrapper
  and unchanged converter C, I2C/cleanup failure, PM cancellation, changing
  source/pack, invalid admission, allocation failure, deadline/old READY,
  existing passive/rearm/timing/raw/fixed-PD and profile gates. No routing change
  or complete suite run; exact modules are in `host-tests.json`.
- Initial new fixture failed to compile because its errno mock was not included;
  retained as `new-tests-first.txt`. The second run exposed an overstrong test
  assertion claiming successful ADC restoration after injected cleanup failure,
  plus a missing converter freeze entry. Tests now require refusal, invalid
  evidence, fault latch and checked pump OFF on failed cleanup; they do not hide
  unknown ADC state. Native converter was not modified. `new-tests-second.txt`
  is retained; all final15 new cases pass.
- Full ARM64 Image/DTB/modules build PASS, 78.783s final incremental build. First
  67.110s build also passed; the normal project build was repeated because W=1
  changed cached objects. W=1/sparse inspect only changed driver/converter;
  one known upstream vDSO warning and no changed-driver warning. Final static
  check restores exact qualified objects after standard command records, with
  no relink of formal artifacts. See `static-first.json` and `static.json`.
- Resolved config diff from accepted323 has **only**
  `CONFIG_SM5440_ADC_ONESHOT_TEST: absent -> y`. No unexpected changes;
  Linux7.2-rc3 pin, HVC_DCC=n, Docker/UPower, SM5714 and ADC5 retained.
- DTB byte-identical; exact181 module-file set, archive readback and runtime
  ELF sections/symbols verified. Debug/BTF-only changes recorded, not claimed
  byte-identical modules. 59 protected sources and23 formal artifacts frozen.
  Frozen native converter digests additionally checked against base git blobs.
- Boot-only package built/unpacked offline, payload/header/AVB-size checked;
  matched181 modules and exact accepted323 rollback hashes sealed in PACKAGE.
  No device deployment, rootfs/configuration change, Actions or main update.

## Remaining physical question

Test324 must establish whether the unchanged native single-shot acquisition
gets a new READY plus checked data/cleanup within100ms. Four successful OFF
transactions would not establish current calibration/coherence, pump-running
cutoff/OCP, PPS safety or full port acceptance. PC5V can latch startup UVLO;
prepare a single fixed9V-source boot instead of replaying the failed continuous
profile or bypassing startup confirmation. Keep fixed9V input<=1.5A, pack/float/
thermal unchanged; restore accepted323 boot/181 after result or first failure.
