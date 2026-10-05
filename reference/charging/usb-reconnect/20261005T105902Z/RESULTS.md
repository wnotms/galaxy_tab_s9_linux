# PC USB reconnection endpoint

Owner confirmed reconnection. One read-only capture passes native ADB shell,
Windows composite/ADB/NCM ProblemCode 0, NCM Up, interface-bound NCM SSH banner
and authenticated Wi-Fi SSH. Same accepted311 boot/config/notes, Sink/Device,
three active services, no failed units and DCC absent. SM5440 OFF, IBUS0/fault0.

Battery **0%, 3.226V, 30.8°C, Good**, net **−119mA** despite Charging label under
PC SDP500mA. Deployment/reboot testing is stopped for low battery; owner was
asked to use the previously accepted ordinary USB-C2 18W charger. No current
limit, service, USB configuration or charging policy was changed.

Full kernel journal and source timestamps retained; exact previous cursor prefix
and new-message comparison in journal-comparison.json. Historical display faults
remain unresolved. This endpoint is not proof of permanent USB repair or captured
physical-cycle recovery time. First Wi-Fi capture failed because the host script
reused a removed temporary known-hosts file; preserved separately. The corrected
read-only retry pins the host key obtained over native ADB and succeeds.

Verdict: **USB_RECONNECT_ENDPOINT_PASS**; charging recovery pending.
No flash/reboot/PPS/pump ON/rootfs/configuration mutation. Host tests and kernel
build executed:false (evidence only); no Actions. Raw outputs preserved losslessly.
