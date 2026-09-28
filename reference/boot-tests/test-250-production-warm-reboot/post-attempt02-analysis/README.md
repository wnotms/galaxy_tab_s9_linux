# Read-only analysis after stopped attempt 02

The owner's subsequent goal is to complete the full registered test. No further
reboot was issued during this analysis; boot remains
`188fd5c9-14ca-4818-9ded-e96669a9c836`. Old verdicts and sealed evidence are not
rewritten or counted as clean.

## SMMU address gate was narrower than the actual production carveout

The installed device-tree `splash_region/reg`, read through ADB, decodes to
base `0xb8000000`, size `0x02b00000`, end-exclusive `0xbab00000` (43 MiB).
The repository DTS contains the same values. The accepted Test249 compiled
DTB SHA-256 is `eecc98b89b59f44608cfd31e34ddaa21d967b1dc912911921d763d7c0435bfe0`,
verified against the manifest-verified `validation/build-check.json`.
`fdtget` on that unchanged artifact independently returns
`0 b8000000 0 2b00000` for the same property.

Attempt 02's 2 MiB region was inferred from the two accepted journals rather
than taken from the device's actual reserved memory. Its new IOVAs
`0xb82a6d00`–`0xb844da00` remain inside the existing 43 MiB production splash
region, with the same ten early FSR/FSYNR/context-bank/SID errors. An address
outside the sampled 2 MiB range does not by itself prove a new CPU fault. A
fresh registered attempt can classify this already accepted startup error
class against the verified DTB region while retaining the time, count,
priority and syndrome restrictions. This does not claim SMMU errors repaired,
and the old stopped attempt is not retroactively accepted.

## NCM path attribution and socket-only probe

Current Windows `Find-NetRoute` selected NCM interface 11 and source
`169.254.254.208`. No alternate current `169.254.0.0/16` route was shown, so an
incorrect current route is not established as the cause of old timeouts.
Both NCM MAC addresses vary from the earlier boot, but this observation alone
does not identify a timeout cause. Full route/interface/address snapshots are
retained, including the device-returned function MAC addresses.

A diagnostic socket bound to that existing NCM source address and outgoing
interface obtained an SSH banner. The first draft failed on a .NET enum/API
lookup before any connect; its error is retained as a host-probe programming
error. The corrected probe and structured probe succeeded, showing interface
11, source `169.254.254.208`, remote `169.254.42.1:22` and an OpenSSH banner.
No permanent route, address, neighbor, adapter, driver, gadget or service was
changed. These probes cannot retroactively classify earlier timeouts as clean.

The outgoing-interface option follows Microsoft's
[IPPROTO_IP socket-option documentation](https://learn.microsoft.com/en-us/windows/win32/winsock/ipproto-ip-socket-options):
IP_UNICAST_IF sets a per-socket interface using a network-order index and
returns the selected index in host order. Its value 31 is confirmed by
[Microsoft's generated Winsock constants](https://microsoft.github.io/windows-docs-rs/doc/windows/Win32/Networking/WinSock/constant.IP_UNICAST_IF.html).
A fresh runner can record these endpoints to prove the NCM path rather than
relying on an unqualified destination-IP banner. It must still stop on the
first initial timeout, even if same-boot retries recover.
