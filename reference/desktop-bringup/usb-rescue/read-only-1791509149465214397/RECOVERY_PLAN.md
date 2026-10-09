# Current USB recovery — single runtime rebind

The owner reports the tablet is connected to the computer but not recognized.
Read-only authenticated SSH at 10.49.219.210 confirms exact Test331 config and
notes, same boot 78ec1906, Good battery 98%/27.7°C. Existing GDM/input, Type-C
Sink/Device, adbd and shared NCM gadget remain present. DWC3 UDC retains
configured/super-speed-plus and FunctionFS has no recent enable/disable events.
Windows CIM completed: no present 0525/ADB/NCM and no Code43. The slower full
PnpDeviceProperty probe timed out and is not a successful negative observation.
The complete current kernel journal is retained with the original two GPU
suspect pairs; no additional GMU errors appear in this later 1272-row capture.
No statement that either GPU error was harmless or USB cause is established.

Registered next action: once only, through authenticated Wi-Fi, on exact
machine/boot/config/notes, verify unchanged a600000.usb UDC, gadget 0525:a4a7,
ffs.adb+ncm.usb0, Sink/Device and disabled direct-charge flag; snapshot gadget
identity and service state, then write empty UDC and restore the same UDC after
0.5 seconds. Use a finally path to restore binding even on operation failure.
Keep adbd/FunctionFS descriptors open. No descriptor/function/service file,
charger register/current, PD/PPS request, modules, firmware, partition or kernel
change; no reboot. This is live USB recovery, not Test366 retry or sensor start.
No automatic retry or broad Windows driver removal. If it fails, preserve the
first outcome and investigate physical/device link state before another action.

Check Windows enumeration/ADB and device NCM once after rebind, retain source
timestamps and same boot, and record the actual result. ADB recovery alone is
not proof of NCM TCP availability. No flash at current 98% and stopped Test366.
The next registered sensor/kernel test still includes the compiled native Escape
update; this recovery does not deploy it or change the interim XKB mapping.
