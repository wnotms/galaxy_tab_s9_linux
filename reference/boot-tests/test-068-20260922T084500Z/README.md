# test-068 — the MCU pulses its line exactly like stock, but serves neither interface

- started: 2026-09-22T08:45:00Z
- source commit: `150b8ef`
- images: `boot.img 303b8673…`; `vendor_boot 4d496064…`, `init_boot 12b77d17…`,
  `dtbo c17418be…` unchanged
- authorization: standing device-test authorisation recorded for tests 046-067

## What it asked

Test 067 left the MCU alive (announce line high) while `0x2a` NACKs. A plain read
separates the two remaining cases: `pogo_state_report()` probes `CHECK_VERSION` at
`0x2a` and Get Version at `0x51` immediately after the rail cycle, with no dance,
no reset and no GO.

## Result — a pulse that matches stock, and then nothing

```
[    4.491944] MCU rail on with BOOT0 low, announce line armed (level 1)
[    4.617962] right after the rail cycle: application -6, bootloader -6, announce level 0
[    4.656773] waiting up to 60000 ms for the MCU application
```

126 ms after the rail rose the line has gone **low**, and at that instant neither
interface answers. Put beside the captured stock cycle, that is the same
behaviour:

| | stock (bringup-cycle-dmesg.log) | mainline (this test) |
| --- | --- | --- |
| rail rises | 70.311157 | 4.491944 |
| line asserted (low) | 70.499288 (+188 ms, `stm32_dev_isr`) | by 4.617962 (+126 ms, level 0) |
| host reads the event | 70.499906, succeeds (`03 00 02`, model 0x2) | `application -6` |
| then | `CHECK_VERSION` succeeds, `[MODE] 1`, CRC `EADF376E` | still `-6` after 60 s |

So the MCU does in mainline exactly what it does in stock: it powers up, and
about 130-190 ms later it pulls its announce line low to say it has something to
send. The difference is not the MCU's startup and not its timing - it is that the
host's read of that event fails with a real address NACK on an idle bus (test
063), and the same read succeeds in stock at the same point in the same sequence.

`bootloader -6` also answers the question this test asked: right after the rail
cycle the part does **not** sit in its system bootloader. It is the application
that owns the line and the interfaces at that moment.

## Next step

The MCU is alive, pulses like stock, does not sit in the bootloader, and yet does
not acknowledge `0x2a` - while the bootloader at `0x51` answers on the same
controller after a dance. Since both interfaces in stock are the same silicon and
the same framing (test 055 byte-for-byte), the remaining difference is what the
host does to the part's I2C side *before* that read: the port's own traffic and
pin state in the seconds before the rail cycle. The next candidate therefore
records the announce line at high frequency across the rail cycle and the first
host attempt, so the pulse's shape and the moment of the first NACK can be put on
the same timeline as stock's, and any extra host activity in that window becomes
visible.
