# test-099 — keys stop after a while: the one-shot startup never re-armed the MCU

- date: 2026-09-22T14:20:53Z (flash) – 14:25:58Z (verification)
- source: working tree on `0e2bf1b`; `boot.img ab813a20…` flashed and read back
- authorization: owner report ("启动内核后停留一段时间后按键屏幕不再出现反应，键盘拔掉重连后仍然没有反应") and the standing test authorisation
- raw logs: `gts9-test099.log` (boot), `gts9-test099b.log` (after the timed test)

## Diagnosis, before any change

With the keyboard dead the running kernel showed:

```
 169:         26  ...  msmgpio     75 Level     5-002a      <- last announce long ago
 170:       2224  ...  msmgpio     62 Edge      pogo-connect
[   43.99] ... key 0x22 released (from the MCU packet)      <- last packet of the boot
dmesg | grep -c "event transfer failed|announce line released"  ->  0
```

So nothing was dropped, gated or failed: the MCU simply stopped taking the bus at
kernel time ~44 s, and a physical re-seat did not bring it back. The reason the
re-seat did not help is structural: this driver's startup is one-shot. Once
`powered` and `event_enabled` are set, `pogo_connect_work()` does nothing, so a
stopped MCU is never released from its bootloader again.

## Change

A keep-alive watchdog: every 2 s it reads GET_MODE (one byte, does not consume a
queued key event), and after three consecutive failures it clears `powered`,
`event_enabled` and `ready` and re-queues `pogo_connect_work()`, so the *proven*
bring-up path (BOOT0-low NRST pulse, rail, arm DATA, handshake) runs again instead
of a second copy of it.

## Result — the reported symptom is gone, but the MCU is still unstable

```
dmesg | grep -c "stopped answering the keep-alive"   ->  8
dmesg | grep -c "application-entry reset"            -> 17
dmesg | grep -c "key 0x"                             -> 26
[  193.237668] key 0x16 pressed ... [195.526308] key 0x39 released
 170:         28  ...  msmgpio     75 Level     5-002a
```

Keys still work at kernel time ~195 s, four times past the point where the keyboard
used to die, and after the cover was unplugged and re-seated. **The user-visible bug
is fixed.** What is *not* fixed is the underlying instability: the MCU still stops
answering periodically, and the watchdog has re-armed it 8 times in ~3 minutes (17
entry resets in total including earlier ones), i.e. roughly every 10 s.

That cadence is too aggressive to leave as it is. The next question is whether an
idle MCU is *supposed* to NACK a GET_MODE poll - if it is, the failure counter must
require a much longer silence (or the poll must be dropped entirely) before touching
the reset line. The evidence needed is one boot with the poll result logged: healthy
idle polls succeeding, or failing, decides it.
