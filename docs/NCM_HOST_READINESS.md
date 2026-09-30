# NCM connection readiness on the current Windows/WSL host

The accepted Test255 fixed-PD boot currently has working ADB and NCM. The first
Test259 NCM SSH attempt started about 9.3 seconds after boot and timed out after
10 seconds. ADB identity had succeeded at uptime 8.26 seconds. That attempt did
not save Windows APIPA/WSL route state before connecting. Tablet usb0/sshd were
up in a later ADB capture at uptime 98.70 seconds. These observations do not
establish the historical timeout's cause or its recovery time. The stopped
Test259 result remains unchanged.

`scripts/gts9_ncm_ready.py` addresses the missing host readiness gate. It is an
explicit read-only connection check, not a replacement for the old SSH wrapper
or a retry facility. It uses the existing key and native Windows ADB at
`/mnt/d/android/platform-tools/adb.exe`. It changes no interface, address,
firewall, service, gadget or tablet setting.

```sh
python3 scripts/gts9_ncm_ready.py --wait 30 --out out/ncm-ready-unique
```

The output directory must not exist. This entry supports the observed mirrored
WSL topology: Windows NCM has a preferred APIPA /16 and WSL has the same address
on an UP/LOWER_UP interface. Mirrored networking mirrors Windows interfaces into
Linux; it differs from WSL's NAT architecture. This helper does not change WSL
network mode. See [Microsoft WSL networking](https://learn.microsoft.com/en-us/windows/wsl/networking).

Only metadata is polled, for at most the registered readiness deadline (30
seconds by default, maximum 60). Each Windows state, WSL route, address, status,
stderr and timestamp is retained. It waits for exactly one production NCM NIC,
preferred APIPA, and the WSL direct route using that same source address. A
Wi-Fi/default-gateway route cannot satisfy this gate. Metadata collection
failure, Code43, conflicting host/device addresses or ambiguous NIC/source
identity stops immediately. A missing/not-yet-ready address or route may wait;
the first not-ready snapshot and elapsed recovery time remain visible.

After readiness it makes exactly one noninteractive authenticated SSH attempt
(10-second connect limit; 15-second process limit). SSH binds the verified
local source address, ignores user proxy/connection settings with `-F /dev/null`,
and checks the remote boot ID against the initial ADB read. OpenSSH defines
[BindAddress](https://man.openbsd.org/ssh_config#BindAddress) as selecting the
local source address. Readiness is a snapshot, not a guarantee the cable remains
attached during connection. Any SSH error or boot mismatch remains STOP; no
command retry or fallback through Wi-Fi occurs.

On STOP it saves additional read-only tablet state. After an actual SSH attempt
it can collect one Windows interface-bound banner probe to distinguish a WSL
connection failure from Windows/device transport failure. This diagnostic
cannot change the verdict. The first SSH stdout/stderr/status is immutable.

Use this entry only in a newly registered workflow with a separate readiness
budget, after applicable device safety checks. Existing `gts9-ssh.sh`, historical
passive admission and wedge runners retain their original deadlines and first-
failure meaning. Never enable this implicitly inside a 15-second outer timeout.
Delayed readiness is reported as `delayed_readiness: true`; a strict series may
classify it as suspect. It must not be relabelled a fully clean transport round.

This fixes the host-side omission of a readiness gate. It does not establish
that APIPA/mirroring caused Test259, repair a USB driver, or qualify cold/warm
boot transport stability. Such claims require a new attributed observation.
