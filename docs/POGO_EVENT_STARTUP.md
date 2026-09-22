# Pogo event startup audit — 2026-09-22

Starting checkout: `f6c5c6b`, with pre-existing uncommitted startup experiments
and untracked test-087 logs. Those experiments are retained behind the new
`keyboard_samsung_pogo.startup_diagnostics=1` boot parameter; they are not the
normal input-driver startup. The untracked logs and GENI_TRANSFER_DIFF document
were not rewritten or treated as newly executed tests.

## Reference implementations

- [S9 Ultra driver, pinned local reference](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/32273b0a410b3e73b20a3a2451e24260fb2a36bd/kernel/drivers/samsung_stm32_pogo.c):
  `samsung_pogo_connection_work()` enables power, waits 50 ms and arms DATA;
  then it releases the protocol mutex. `samsung_pogo_read_event()` handles the
  model packet and reads VERSION; application initialization is separate work.
- Samsung X710 source, supplied locally at
  `/home/ms/Samsung/kernel_platform/msm-kernel/drivers/input/sec_input/stm32/`:
  the working event handler uses level-low DATA and performs version reads in
  response to a model announcement.
- Pinned mainline `Documentation/driver-api/gpio/consumer.rst`, active-low
  semantics: descriptor reads return logical assertion, unlike raw GPIO reads.
- [S9 Ultra hardware report](https://github.com/agcarbajo/ubuntu-galaxy-tab-s9-ultra/blob/main/docs/hardware-status.md)
  reports V34/V37-dependent behavior on its EF-DX920. This is a useful comparison,
  not proof that X710 firmware must change. X710 has EF-DX710 and working V34 in
  TWRP. No firmware write, X910 blob, or MAX77816 booster configuration is imported.
  X710's supplied board node does not describe the S9U keyboard booster; its
  MAX77816 display supply must not be treated as a keyboard supply.

## Defects in this checkout

`announce-gpios` uses GPIO_ACTIVE_LOW. A logged descriptor value of 1 therefore
means physical low. The rationale used to invert the IRQ in test 087 interpreted
logical values as raw levels. Restore IRQ_TYPE_LEVEL_LOW and the vendor port's
matching 0x2008 flag. Line transitions alone do not prove a valid model packet.

`pogo_connect_work()` held `p->lock` over a 30-second preamble, power cycling,
scans, a five-second observation and up to 60 seconds of version polling. The
threaded DATA handler takes the same lock. Enabling the IRQ partway through does
not allow it to read a packet while that lock remains held. The model handler
also called the 60-second retry loop under the lock. These are source-level
blocking paths; the extent to which they caused previous hardware failures is
not established by reading the source.

## Change and scope

Normal startup now obtains one regulator reference, settles for 50 ms and arms
DATA outside the mutex. Repeated connect work does not take another reference
or enable the IRQ twice. Failed power-on leaves DATA disabled. It does not
poll, scan, toggle NRST, visit the bootloader or power-cycle the accessory.
The model handshake makes one version attempt; the diagnostic-only long retry
and bus-recovery paths are disabled in normal operation. A failed event still
releases key state. The existing 200 ms DFU-to-application command settling
remains; it is distinct from the former minute-long retry loop.

Prior uncommitted experiments remain in `pogo_diagnostic_connect_work()` and are
explicitly opt-in, including their scans and rail cycle. Their historical comments
are not new findings. The parameter is read-only after load so the startup policy
cannot change underneath a running work item. Automatic MCU firmware writes
remain absent.

## Validation

All 10 host tests pass, including 12 packet/error cases and the real bootloader
framing helpers. The startup test checks that DATA is enabled with the mutex
unlocked after 50 ms, no I2C/reset/recovery happened in normal startup, repeated
work is idempotent, power errors do not arm DATA, and an unavailable version
returns after one attempt without bus recovery. It retains DFU ABORT coverage.
The old startup harness failed to compile against the incoming uncommitted code;
it has been updated to test the new normal path. Host tests do not replace the
kernel build or demonstrate hardware support.
