# Current sensor preparation: read-only inventory

Same d197 boot, accepted Test370 config/notes, permanent USB helper enabled/active.
79% battery, 38.4°C, Good; PC input charging. ADSP offline/no FastRPC node;
native SoC519 present. Four exact-version SSC packages installed/inactive behind
90 controlled gates, no userspace pd-mapper, copied sensor prefix absent.

Remote command status0. Local json.loads originally rejected two concatenated
JSON objects because the capture source main printed once before the extended
inventory. Both raw objects preserved in before.stdout; before.json is the
second object decoded without another device command. This is a host parser
incident, not a device or SSC failure. No runtime/firmware/service/device writes.
Host tests/build executed:false (read-only inventory); next new Test372 scope.

Later connection check: original WiFi banner timed out, ADB empty. Owner reconnect
restored realADB in same d197,76%/27.1C, lifecycle enabled/active, normal GNOME.
Read-only kernel admission initially rejected a new priority3 pogo -ENXIO. Full
source timestamps show physical keyboard hot-reconnect, single event NACK, MCU
firmware response and handshake complete after1retry within0.5s; retained exact
row/context, not a general waiver. One additional exact ep0 diagnostic is source
attributed to permanent helper owned unbind within250ms. ENROLLMENT.json proves
remaining full kernel delta has no other errors/CPU signature. Test372 had not
started; its fresh preflight accepts only this exact past same-boot evidence,
any subsequent error remains STOP. No kernel/USB/keyboard or device edits.
