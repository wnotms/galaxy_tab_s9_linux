# Pogo application startup repair — 2026-09-22

## Evidence and current status

The repository has physical evidence for ABL → mainline → BusyBox, storage,
report collection through microSD, and a working panel console after display
recovery. The EF-DX710 input device registers, but registration is not successful
keyboard operation. Earlier runs obtained bootloader version `0x12` at I2C
`0x51`; application communication at `0x2a` and actual key events remain
unverified for this candidate. No physical test was performed during this repair.

The previous head was `776b7d4`. Its live-session GO attempt still had three
source-level defects:

1. Get Version consumed only the initial ACK and version byte. The final ACK
   was left unread before GO. This could stall or misalign the following
   exchange; the exact hardware failure caused by it has not been measured.
2. `pogo_connect_work()` pulsed NRST unconditionally after the bootloader helper
   returned, including after a successful GO/application version read.
3. If the initial application version read succeeded, startup enabled the event
   IRQ and returned without checking application mode or setting `ready`. Key
   packets are suppressed while `ready` is false unless a later announcement
   completes initialization.

The full ACK/version/ACK exchange is specified in
[ST AN4221, Get Version](https://www.st.com/resource/en/application_note/an4221-i2c-protocol-used-in-the-stm32-bootloader-stmicroelectronics.pdf).
It is also implemented by the owner-supplied Samsung source:
`kernel_platform/msm-kernel/drivers/input/sec_input/stm32/stm32_pogo_fw.c`,
`stm32_sysboot_i2c_get_info()` and the `STM32_BOOT_I2C_CMD_GET_VER` case.
The local extracted reference is under `.work/reference-samsung/official/`.
AN4221 is the I2C reference; the previous GO comment named the UART note AN3155.

## Candidate behavior

Get Version now validates all three reply frames, preserves transport errors,
and rejects short transfers and non-ACK replies. A failed version exchange
requires a fresh successful bootloader entry before GO, so an incomplete reply
cannot be treated as GO's ACK. Successful version reads stay in the same session.

Both application startup paths now check version and mode before enabling the
IRQ. Successful entry is not followed by an unconditional reset or bus recovery;
recovery is attempted only after an application read fails. `ready` is cleared
before verification so a failed check cannot preserve stale readiness. The
existing failed-read reset retries and vendor reset fallback remain available.
No MCU flash-write or firmware-update command was added. The GO target remains
`0x08000000`; this repair does not independently prove that the installed
application can start at that address.

## Local validation

`python3 -m unittest discover -s tests -v`: all 9 tests pass. The new startup
harness compiles and executes the actual driver functions with AddressSanitizer
and UndefinedBehaviorSanitizer. A stateful transport rejects GO until the final
version ACK is consumed. Cases cover each version short/error transfer, rejected
ACKs, failed GO transfers, new sessions after version failure, application already
running, GO success, reset fallback, failed power-on, failed sync, non-application
mode, and failed-read readiness clearing. Existing IRQ tests cover 12 packet and
error cases; panel and boot regression tests also pass.

The first test invocation exposed a LeakSanitizer sandbox restriction, and the
new mock initially counted SWCLK writes as NRST pulses. With distinct mock GPIOs
and the permission restriction removed, the full suite passes. These were host
test setup issues, not hardware observations.

The final overlay compiles with `USE_CCACHE=1 BUILD_MODULES=0 JOBS=16
./scripts/build-kernel.sh` against the unchanged pinned kernel. The built driver
source matches the repository overlay byte-for-byte. The isolated bundle passes
`scripts/validate-boot-bundle.sh`, including extraction and image hashes.

Final artifact SHA-256 values:

```
3cdf19d8e848461996c0aa73540b5745fa1b6893597cae9d5c122b4e11a08ff4  Image.gz
6d5556599ecafb8dbdce566acb94cbc5f2a535de1a56b5e4df471be44a3be473  sm8550-samsung-gts9wifi.dtb
e8d3fd612d9e0612296a32040f29217b3d7f12eda92b0f52f772710458aec72a  config
b3f154357931f9e2ddce4bd3b37facae84a69e93a280dbb9bb877f7c824d5658  kernel.release
13c59031f3dbeac6a0d861423044770efe36a20f8a7285920e36e75d288164dc  boot.img
c17418be08365c03a5ce3a220af734b14ec2e6b03c0cbc1ed9721be6f21d3ef3  dtbo.img
2fb24cd0bb8f9513d4c214c069dd2d3b4cdaf391e17af8fcc43563372cef9dc5  init_boot.img
9802104d4bbd8c223f10ad58e4e9966a8c299788a067eb804a52469f2d85808f  initramfs-bringup.img
b95e5ef931fbe588f8574c06331db56ae906b1ac91ed73204704b35cb220b3d4  vbmeta.img
828dadec334fa440aca7f81879cc6405240e9a7ff0388f6b1608caa6e2535d25  vendor_boot.img
```

Local build/test/package logs, `BUNDLE_INFO`, source hashes and `validation.txt`
are retained in `out/boot-bundle-pogo-startup/`. Build outputs are not committed.

## Next physical test

Use the isolated `out/boot-bundle-pogo-startup/` candidate after recording the
owner's current test request and checking device identity, partition sizes,
backups and write/read-back hashes. Follow `AGENT.md` and `docs/FIRST_BOOT_TEST.md`.
The bundle's presence does not authorize flashing all generated images.

Capture the complete bootloader exchange diagnostics and the application
version/mode line. Success requires a mode-1 application plus real key-down and
key-up events, including releases and Caps Lock behavior. A GO ACK alone is not
proof of application startup. Archive raw logs and hashes under a new
`reference/boot-tests/test-NNN-.../` directory before another experiment.

## Hardware follow-up: test 046 and Samsung connect STEP3

Test 046 booted `ad4463f`, with working screen/USB console, but Get Version
returned -110 and GO was refused. Reset-based app entry still NAKed. See the
complete [test record](../reference/boot-tests/test-046-20260922T055740Z/README.md).

Samsung's `stm32_sysboot_connect()` (lines 400–436 of the supplied firmware
source) has a second boot-mode reset after the successful 0xFF probe. Crucially,
it does not transmit 0xFF after that reset. `STM32_BOOT_I2C_CMD_SYNC` is labelled
UNKNOWN in its command switch. Our original helper lacked that step; invoking
it twice also sent the unknown command twice. The next candidate factors out
the GPIO reset sequence and performs reset → 0xFF probe → reset → commands.
The second reset occurs before Get Version/GO, never after successful app entry.

A new host test executes the actual reset and entry functions and checks the
sequence against Samsung STEP3, including short/error probe and missing-client
paths. All 10 host tests pass. Hardware confirmation remains separate.

## Hardware follow-up: test 047

[The second test](../reference/boot-tests/test-047-20260922T060344Z/README.md)
validated source `1d8a977`: complete version `0x12` and GO command/address ACKs
now succeed. The application still NAKs after the 150 ms wait and the reset
fallback does not revive it. No real key events were observed. The tablet
returned to TWRP with the corrected candidate installed and hashes verified.
This is a bootloader communication fix, not completed keyboard support.

Next distinguish slow application startup (poll without resetting it) from a
wrong/unusable application entry point, using read-only MCU inspection if needed.
