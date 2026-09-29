# SM5440 X710 register and ADC audit

Primary source: owner-supplied `msm-kernel/drivers/battery/charger/
sm5440_charger/sm5440_charger.c/.h`. Cross-check: Fedora
`ab123e7d`, `kernel/files/sm5440_direct.c`. Source hashes are in Test256.
Numbers below are [VENDOR] unless noted; unverified protection encodings are
not guessed. Passive code must not import vendor active init wholesale.

| Function | Vendor register/bits or encoding | Fedora | Port disposition |
| --- | --- | --- | --- |
| Interrupt latches | INT1..4=0x00..03; reads used by vendor IRQ | reads/decodes | retain raw evidence; not generic writable status |
| Masks | MSK1..4=0x04..07 | masks | not reprogrammed for passive polling |
| Live status | STATUS1..4=0x08..0b | polls | fault decode, no clearing writes |
| Reset/WDT | CNTL1=0x0c, reset bit0; WDT bits6:4, enable7 | reset,30s | no passive reset or WDT enable |
| OCP/thermal enables | CNTL2=0x0d, init0xF2 disables IBUS/IBAT OCP/THEM | copied init | NOT imported; software OCP requirement unresolved |
| Charge timer | CNTL3=0x0e bit2; init0xB8 | copied | unchanged in passive profile |
| Debounce | CNTL4=0x0f, init0xFF (8ms) | copied | active-only, not passive write |
| Operation mode | CNTL5=0x10, bits3:2; OFF0,CHG1,reverse2/3 | gate | only OFF write + readback allowed initially |
| PWM/HIZ | CNTL6=0x11, init0x09 | copied | unchanged; reverse/bypass excluded |
| Switching frequency | CNTL7=0x12 bits4:0; (kHz-250)/50 | 850/650/450 | pure checked encoding; no passive write |
| VBUS OVP | VBUSCNTL=0x13, low3 bits7 means11V | copied | threshold encoding outside proved value UNKNOWN |
| VBAT regulation | VBATCNTL=0x14 bits5:0;3800+code*12.5mV | helper | checked encoding, round down, no automatic+50mV |
| VOUT regulation | VOUTCNTL=0x15, init0x3F(max) | copied | no passive write |
| IBUS limit | IBUSCNTL=0x16 bits6:0;50mA/code | helper | bounded pure encoding; not proof of usable HW OCP |
| Protection | PRTNCNTL=0x19 init0xFE | copied | bits not fully documented; no speculative write |
| Thermal threshold | THEMCNTL1=0x1a init0x0C(120°C); THEMCNTL2=0x1b | copied | not bringup temperature allowance |
| ADC control | ADCCNTL1=0x1c:enable0,rate1,average3 | oneshot | named enable/channel operation only, pump stays OFF |
| ADC channels | ADCCNTL2=0x1d;vendor0xDF | 0xDF | same traced channel mask for conversion |
| ADC data | VBUS0x1e/1f,VOUT20/21,IBUS22/23,THEM24/25,DIE26,VBAT27/28 | reads | physical telemetry, complete conversion only |
| Identity | DEVICEID=0x2b;low nibble1,high nibble revision | same | no writes if ID invalid |

## ADC conversion and validity

Vendor `sm5440_convert_adc()`:

* 13-bit raw = `(high << 5) | (low >> 3)`; low three bits are not data.
* VBUS mV =4096+raw; VOUT/VBAT mV =2048+raw/2.
* IBUS mA =raw*625/1000 (0.625mA/LSB).
* THEM mV =raw/4; this is a thermistor voltage, not an invented temperature.
* Die temperature deci°C =225+byte*5. No signed conversion in vendor.
* No independent IBAT ADC is present in this verified map. Report SM5714
  gauge current separately, not a fabricated pump IBAT.

ADC_UPDATED is INT4 bit0; readings must follow a newly started conversion,
bounded ready wait, complete multi-register transfer and mode-OFF confirmation.
Clear/consume a previous completion before starting; do not turn reset/default
raw0 into a plausible4096mV measurement. The exact conversion/ready behavior
with pump OFF remains a **physical acceptance requirement**: vendor comment
says ADC is not normally worked below CHECK_VBAT, while its enabled conversion
path and Fedora demonstrate an explicit converter mechanism. Timeout/invalid
range means unavailable, never permission to enable. No lock held while waiting.

## Fault decoding

INT1/STATUS1: VOUT_OVP bit4, VBAT_OVP bit3, reverse OCP bits1/0.
INT2/STATUS2: IBUSLIM bit7 and VBATREG bit3 are regulation indications, not
automatically OCP faults; THEM regulation bit1 and indication bit0 require
conservative thermal handling. INT3/STATUS3: VBUS_OVP7, VBUS_UVLO6,
VBUSPOK5, thermal alarm4/shutdown3, startup-fail2, REVBLK1, flying-cap short0.
INT4/STATUS4: WDT-off2, charging-timer-off1, ADC_UPDATED0. Lost mode CHG_ON
or VBUSPOK during direct operation is a fault even without a latched bit.
IBUS/IBAT OCP must additionally use verified physical current/pack gauge limits;
do not invent ordinary OCP bits from reverse-boost flags.

Any transport/ADC/fault problem: best-effort OFF, verify OFF, latch evidence.
If I2C is unavailable OFF is **not proven**: refuse voltage/fallback activation
and require unplug/recovery. Hardware fail-closed cannot be guaranteed by a
failed software write. No endless bus retries.

## Board protection caveat

Vendor X710 config:850kHz, low-current450/650kHz, r_ttl320000uohm,
en_vbatreg0. Driver adds+50mV hardware regulation offset and+300mA input margin
(+600 at minimum input), and explicitly requires software OCP. These are
vendor behavior, not an authorization to exceed our4440mV/1800mA bringup caps.
The complete active protection recipe and hardware-current overshoot response
must be resolved before a pump-ON candidate. This audit does not label all
register bits understood when source only gives a magic aggregate value.
