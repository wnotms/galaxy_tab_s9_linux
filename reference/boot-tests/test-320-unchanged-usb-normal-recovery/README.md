# Test320 — unchanged USB normal-boot recovery

Current native USB descriptor failure survives one owner-confirmed cable/port
reconnection; authenticated Wi-Fi remains healthy. This separate recovery scope
allows the observed incoming Code43/absentADB, while Test319 remains STOP before
reboot. It does not waive Test318 rescue or baseline gates.

Save boot-attributed full journal, both Windows failures and source/pack/role/UDC/
FunctionFS/service state before any action. No live adbd restart or shared gadget
rebind (FAST_DEBUG_CHANNEL.md guard preserved). One normal systemctl reboot over
strict authenticated Wi-Fi after pushed registration and fresh same-boot safety
packet. No flash, BCB, modules, rootfs/config/register writes; no PPS/pump/current
raise. No partition/module rehash loop for an unchanged recovery boot: config/
notes and exact normal command line must match; full deployment identity remains
mandatory before any future Test318 flash. Original308 accepted311 operating
rollback is retained for Test318/Test320, not a new production candidate.

One uniquely attributed new boot, readiness150s maximum, one15s same-boot endpoint,
actual native ADB shell and WindowsCode0/no43, Wi-Fi/deviceNCM/services/pack/pump/
fulljournal. Any unclassified fault/wrongidentity/unexplainedboot/remainingCode43
stops; no second reset. Recovery does not establish a permanent USB fix or charging
acceptance. No new host implementation or kernel input, tests/build executed:false.
