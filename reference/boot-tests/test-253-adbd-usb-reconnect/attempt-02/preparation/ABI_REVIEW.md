# Host-side ARM64 load check

QEMU user-mode execution of the exact built daemon with the recorded ARM64
builder libraries completed exit0 and printed Android Debug Bridge Daemon
version1.0.41. Only --version was used; no daemon connection, device write or
service start occurred. Binary hash remains
053348e27a1e6b5b70940abd9cf7054225c802d4d9ce6681eb4c3b22cd85c7f5.
The read-only device package report shows the same Debian13 ABI family:
libc6 2.41, libstdc++6 GCC14, protobuf3.21.12 and Android libraries34.0.5-12.
NEEDED/RUNPATH/version requirements are archived in the parent build folder.
This is a host load check, not an on-device loader or reconnect acceptance.
Device loader verification remains mandatory during authorized staging.

This supplementary record changes only documentation/evidence. The retained
1080-test full report is unchanged; no new host suite was run here:
`executed: false`. Original stopped Test253 seal remains unchanged.
