# Test273 preparation — source attach not yet performed

Original prepare STOP is retained as a host-only omitted DCC section; it was not
restored DCC. Corrected prepare-completion READY on the same846248af boot:
exact263config/notes/cmdline, DCCabsent, battery75%/4.108V/32.9°C Good,
passiveGood/fault0/OFF/IBUS0, cache692ms; Wi-Fi responsive, deviceusb0 present.
No new kernel failure, original20 startupSMMU variants unchanged/unresolved.
First complete PC TCPM ring was consumed once and archived. No cable action,
charging window, flash, reboot, PPS, pumpON or software change on the device.

Actual pinned TCPM logs schedule a pending HARD_RESET timeout after an ordinary
Request. A pending target is not an executed reset. Tighten pure parser to actual
state transitions/Received hard reset/Soft_Reset RX instead of substring matching.
Actual archived PC ring and explicit pending/actual reset tests pass; current
source reset/detach still invalidates evidence. No global kernel whitelist changed.

Final affected qualification: parser29 + unchanged collector16 pass; syntax pass.
Original25+15 and correction16 evidence retained. Build/full executed:false,
reuse unchanged Test272 qualification, not a new full regression pass. Historical
registration seal verified againstb7e27663; correction seal against60feb5c5.
Current active observer hashes are in SOURCE_OBSERVER_SHA256.json.

Next ONLY owner-confirmed C1 attach/C2empty,30s ordinary fixed-PD capability
identification, then one PC endpoint. Missing capability evidence staysUNKNOWN.
There is still no PPS/APDO result for C1 and no authorization inferred from PDOs.
