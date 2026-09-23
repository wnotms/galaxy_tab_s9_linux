# Test 170 — read-only USB serial check after the early-display screen

**Result:** the owner reported that the panel still showed the two early
initramfs console lines. A read-only Windows COM17 probe then received a Debian
serial-getty banner and `gts9 login:` prompt. This shows that Debian's USB ACM
login service was active during that probe; it does not by itself correlate
the prompt with the current photographed boot or prove the panel updated after
the initramfs markers.

The first COM17 open used 115200 8N1 and read for 12 seconds without sending
input. Its directly observed text was:

```text
Debian GNU/Linux 13 gts9 ttyGS0

gts9 login:
```

The host also received terminal control sequences; the first probe was streamed
to the tool output rather than saved as a byte-for-byte file. A second
read-only open, captured in `com17-reopen.txt`, remained open for 8 seconds and
received no new text. No username, password, or command was sent. No flash,
reboot, filesystem write, or power operation was performed.

The result changes the interpretation of the static panel image: it may be
showing retained framebuffer contents while userspace continues to boot. To
correlate this login prompt with the current boot, the next useful read is
`/var/log/gts9-last-boot-stage` over the serial login, including its boot ID,
followed by the current boot ID and `systemctl is-active serial-getty@ttyGS0`.
Until then, the evidence is a live Debian login prompt observed on COM17, with
the boot-ID match still unverified.

## Files

- `com17-reopen.txt`: saved output from the second read-only open. The earlier
  prompt was directly visible in the first probe result but was not persisted
  as a raw byte capture.
- Raw byte capture: unavailable.
