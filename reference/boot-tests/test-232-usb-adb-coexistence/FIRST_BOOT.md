# First deployment observation

Boot acb16bf4-66d2-43cb-9fa8-5d35154ef586 used commit 6d200aa.
Windows enumerated Android Composite ADB Interface at MI_02 and the original
NCM adapter at MI_00, ifIndex 10, Up. adb devices listed gts9wifi-0001.
USB shell and direct adb sync reads timed out; TCP ADB/SSH did not answer.
The owner reported a log-screen stall and manually returned to TWRP.

The retained source journal ends at 6.88 seconds, after FunctionFS bind/enable,
NCM 169.254.42.1/16, ssh.service and multi-user.target startup. It contains no
positive CPU non-response signature. This is a suspected hang, with cause and
CPU unattributed; successful unit startup does not prove later SSH usability.
The failed relative boot query is retained; retry used the exact boot ID.

Independent source review identified internal adbd endpoint reopen as another
shared-gadget reset path. The next revision adds an idle ep0 holder before
binding; this is not claimed as a fix for the observed log-screen stall.
No kernel partitions were changed.
