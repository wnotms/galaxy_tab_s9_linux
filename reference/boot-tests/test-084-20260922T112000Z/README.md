# test-084 — the rail pin rises now, and the application still NACKs

- started: 2026-09-22T11:20:00Z
- source commit: `22985e6`
- images: `boot.img 3def79e0…`, `vendor_boot.img 6be74b07…` (new DTB);
  `init_boot aed8f3c5…` (with firmware), `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-083
- driver: the vendor port, i.e. Samsung's own code with the firmware present

## The fix, and its verification

Test 083 found the pad low while the regulator reported itself enabled, because
the pinconf state added in test 058 was winning over the regulator's write.
`pogo_supply` now carries no output value at all, so the fixed regulator decides
the level - low when it probes, high when the driver enables it.

```
[   34.084224]   pin 10: io 0x3     <- driven high, output bit and input bit both set
[   34.092322]   pin 13: io 0x3     NRST, for comparison
```

The rail pin is now in the state stock has, verified by the register rather than
by the regulator's own report. **The configuration bug is fixed.**

## The application still does not answer

```
[   37.234398] stm32_i2c_write_burst: I2C retry 3, ret:-6
[   39.610540] stm32_i2c_write_burst: I2C retry 3, ret:-6
[   41.987437] stm32_i2c_write_burst: I2C retry 3, ret:-6
```

With the rail pin high, the firmware path reproduced and Samsung's own driver
issuing the writes, `0x2a` still NACKs - so the hypothesis this round was built
on is disproved as the root cause: gpio10's level was a real defect, worth fixing
and now fixed, but not the reason the application's slave is silent.

## Where that leaves the count

Every host-side signal and every settable variable now matches stock by
measurement, including the one that did not until this round. The application
runs (test 082), announces itself (test 076), and its I2C slave still answers
nothing at any address (test 077) even though the same peripheral in the same
part answers the same controller in boot mode. The next candidates are therefore
inside the cover's own side - what the application checks over its internal bus -
and, on the host side, only the controller driver remains uncompared
(i2c-msm-geni against i2c-qcom-geni), which stock's own boot log shows doing the
same kind of transfers this port does.
