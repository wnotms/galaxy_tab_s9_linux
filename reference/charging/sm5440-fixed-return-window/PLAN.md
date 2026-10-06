# Fixed-PD return voltage and stability gate

Status: offline correction; Test331 remains installed, direct charging OFF.

## Evidence and purpose

Test330 measured fixed-return ADC 9.272–9.293 V with a logical fixed9V
contract, pump OFF and raw IBUS zero. Its sealed timeout remains a failure.
The old ±100mV nominal gate was an added mainline-port policy, not a Samsung
or Fedora requirement. This correction does not repair or calibrate ADC.

[USB-IF USB Power Delivery r3.2 v1.2, 2026-08-19](https://www.usb.org/document-library/usb-power-delivery),
§4.1.2.1.1, §4.7.1 Table4.6, PDF pp50/82/83:
fixed vSrcNew is PDO voltage ×0.95 through ×1.05, measured at the **source
receptacle**. vSrcValid describes additional transient allowance; we do not
use that wider transient allowance to authorize switching release.
The official PDF SHA256 is
`1a041ab16c7ffcd39569809859fc59e569ade9cf155e4c314a46c9e9b1184027`.
The licensed PDF stays in the ignored download cache, not this repository.

This port chooses the same numeric steady-state window at the pump ADC as a
conservative board acceptance rule [BRINGUP_LIMIT], not proof of source
compliance. Cable drop, ADC accuracy and unobserved transients remain limits
of this observation. A 9.272V ADC observation is numerically inside the window;
that alone does not prove safe PPS operation or sensor accuracy.

## Minimal implementation

- Shared fixed-window helper accepts only approved 5V and9V contracts:
  4.75–5.25V and8.55–9.45V inclusive. Unsupported voltages, even enormous
  values, fail before multiplication. The 9V ceiling stays below9.5V.
- Fedora-port proof producer requires at least three consecutive in-window,
  raw-IBUS-zero observations spanning at least100ms, with at most100mV
  minimum-to-maximum variation [BRINGUP_LIMIT]. Out-of-window/current/unstable
  samples reset the qualifying interval. This distinguishes steady offset from
  movement; repeated ADC reads are not asserted to be independent conversions.
- Retain the existing bounded30 attempts, ADC sequence/conversion, checked
  pump OFF, zero raw IBUS (including fractional mA), fresh proof≤100ms,
  exact source/instance/budget/lease and failure inhibition.
- Independently enforce the fixed-window helper at native lease release;
  do not change the companion proof ABI, lock order or introduce waits there.
- Do not change PPS entry/settle range, ADC offset, current, hardware registers,
  thermal/4.44V policy, TCPM, USB, DTS, config or userspace.

## Source cross-check

Samsung X710 `msm-kernel/drivers/battery/charger/sm5440_charger/`
`sm5440_charger.c:sm5440_convert_adc`: VBUS=4096+raw13 and raw IBUS scale
match Fedora. Its wired direct-charger adjustment forces v_offset=0; wireless
compensation is unrelated and is not ported. Fedora snapshot
`ab123e7d1dbc0cbcd35661f9761197e977b15aa9` `kernel/files/sm5440_direct.c`
restore requests TCPM fixed ONLINE=1 without physical return proof; retain our
stronger OFF/source/physical/freshness gate rather than copying that omission.

## Qualification and next physical question

Run actual-C producer/release/fault/coherence tests and unchanged interface
consumers, one incremental ARM64 build and affected-object W=1/sparse.
Verify exact Test331 config/DTB identity and paired181 module file set.
Freeze Test331 formal artifacts and rollback; no device operation this scope.

Next physical scope must be separately registered/pushed and prove a pump-OFF
fixed return before expanding active PPS testing. No automatic current increase,
PPS trial or flash is authorized by this offline result. Preserve Test331 OFF
acceptance and Test330 suspect result. Full charging port remains NOT_READY.
