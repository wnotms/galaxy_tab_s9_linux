# Test262 attempt02: five-minute fixed-PD charging phase PASS

Registered/corrected host source70cda251 was pushed before this attempt. Initial
boot/config qualification is reused from unchanged Test260; complete live kernel,
health and retained startup-event gates pass before attachment. The owner then
confirmed connection to the requested Lenovo YG65G USB-C2 18W PD source.

Fixed9V/1.5A contract and SM5714 ICL1.5A remain unchanged throughout
**300.011s /61 charging samples**, same boot18bce160. This is ordinary SM5714
switching charging; SM5440 remains passive/OFF, reported IBUS0 throughout.

| Measured/reported quantity | Result |
| --- | --- |
| Battery net power (gauge VBAT × IBAT) |6.568–8.289W; mean7.827W |
| Battery current |1.659–2.068A, positive61/61 samples |
| Battery voltage |3.959–4.016V |
| Battery SOC |54% →56% |
| Battery temperature |28.4–29.2C |
| Passive SM5440 reported VBUS |9.077–9.123V |
| Passive SM5440 reported die temperature |27.5–35.0C |
| Configured input ceiling |9V ×1.5A =13.5W |

Health remains Good, roles Sink/Device, no failed units, new kernel/CPU fault,
I2C failure, repeated passive fault or reset loop detected. Complete boundary
journals and incremental source-timestamped journals are retained. The single
Test260 confirmed-inactive startupREVBLK warning remains unchanged; it is not
removed or reclassified. Attempt01's pre-attachment host parser STOP and the
separate Windows connection-sound incident remain retained.

No PPS request/pumpON, higher charging current, protection/float/thermal change,
USB/adbd change, reboot/flash or rootfs change occurred. Rollback is retained
and was not required. No build/full regression repeats: corrected host parser
44 affected tests plus syntax were qualified before this physical attempt.

Limits: battery net watts are not actual charger-input watts. Contract/ICL is
an input ceiling; there is no inline power measurement or independently
calibrated physical VBUS. This bounded result does not qualify PPS/direct
charging, OCP/protection, PM, high-current or long-term reliability.

**Charging phase PASS; unplug and PC-reconnect gates remain pending.**
No automatic20min extension. ActiveStage3 remains NOT READY.
