# Warm reboot exposed a bounded startup race

Boot a1eb9541-aff7-4269-b739-c0dd371b01af kept SSH and NCM working; its
155.56-second health capture reports no failed units. Native USB ADB remained
offline. The journal identifies the cause: adbd opened ep0 at 5.089 s, timed
out waiting for FUNCTIONFS_BIND at 6.305 s, then could not rewrite descriptors
on the held endpoint. This is a startup-ordering failure, not evidence of a
CPU wedge. Initial SSH failures preceded the Windows APIPA address becoming
available; subsequent authenticated sessions succeeded.

The corrected revision prepares NCM/configuration/UDC before launching adbd,
and polls readiness/holder every 50 ms within the same five-second bound.
Deployment updated files only over TCP ADB; no live unit restart or UDC
unbind occurred. NCM/SSH file hashes stayed identical. The next normal boot
validates the revised order. The endpoint-holder safety behavior is retained.
