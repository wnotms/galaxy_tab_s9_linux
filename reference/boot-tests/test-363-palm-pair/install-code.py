"""Install Test363 optional pair without loading or rebooting the current boot."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys
import tarfile
import tempfile

EXPECTED = {
    "wacom-wez01.ko": "bc3816a8f37c0f45bdaca3ac9548793df1784541364da9017d08d5c4841e1412",
    "fts1ba90a-palm.ko": "7e71ca5816bf720ce4b3065727a4d43633be3c6abbcb070a4dd723c321d56171",
}
BOOT = "25ff0ad0-cf2f-4cc6-971d-2b38365da2db"
CONFIG = "51ba6a9c2ba3d1d5c6ebd9288fb6d04765e8c200ce58fd932975f11588c66c6a"
NOTES = "03c9c46e21fcc587dbfd5a337f5c9cf68d9cbfa605e074d5a74d2f9a8073dc95"
DEST = Path("/usr/local/lib/gts9-desktop")


def run(argv):
    return subprocess.check_output(argv, text=True).strip()


def main():
    if os.geteuid() != 0:
        raise RuntimeError("root required")
    if Path("/proc/sys/kernel/random/boot_id").read_text().strip() != BOOT:
        raise RuntimeError("unexpected boot")
    import gzip
    if hashlib.sha256(gzip.decompress(Path("/proc/config.gz").read_bytes())).hexdigest() != CONFIG:
        raise RuntimeError("unexpected config")
    if hashlib.sha256(Path("/sys/kernel/notes").read_bytes()).hexdigest() != NOTES:
        raise RuntimeError("unexpected notes")
    if not Path("/sys/module/fts1ba90a").exists() or not Path("/sys/module/wacom_wez01").exists():
        raise RuntimeError("current Test362 modules are not both loaded")
    if run(["systemctl", "is-active", "gts9-touch.service"]) != "active":
        raise RuntimeError("ordinary touch service is not the expected current owner")
    incoming = Path(sys.argv[1]).resolve()
    if not incoming.is_file():
        raise RuntimeError("missing archive")
    DEST.mkdir(parents=True, exist_ok=True)
    with tarfile.open(incoming, "r:gz") as archive:
        names = {member.name for member in archive.getmembers()}
        if names != set(EXPECTED) | {"gts9-palm", "gts9-palm.service"}:
            raise RuntimeError("unexpected archive contents")
        payload = {member.name: archive.extractfile(member).read()
                   for member in archive.getmembers() if member.isfile()}
    for name, digest in EXPECTED.items():
        if hashlib.sha256(payload[name]).hexdigest() != digest:
            raise RuntimeError("hash mismatch: " + name)
    targets = {
        "wacom-wez01.ko": DEST / "wacom-wez01.ko",
        "fts1ba90a-palm.ko": DEST / "fts1ba90a-palm.ko",
        "gts9-palm": Path("/usr/local/libexec/gts9-palm"),
        "gts9-palm.service": Path("/etc/systemd/system/gts9-palm.service"),
    }
    for name, target in targets.items():
        if target.exists() or target.is_symlink():
            if target.read_bytes() != payload[name]:
                raise RuntimeError("refusing to replace existing " + str(target))
    for name, target in targets.items():
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            fd, temp = tempfile.mkstemp(prefix=".gts9-palm-", dir=str(target.parent))
            try:
                with os.fdopen(fd, "wb") as stream:
                    stream.write(payload[name])
                os.chmod(temp, 0o755 if name == "gts9-palm" else 0o644)
                os.replace(temp, target)
            finally:
                Path(temp).unlink(missing_ok=True)
    subprocess.run(["systemctl", "daemon-reload"], check=True)
    # Keep current boot's loaded ordinary FTS alive; only change its future
    # enable link. The next boot's GDM Wants will use gts9-palm instead.
    subprocess.run(["systemctl", "disable", "gts9-touch.service"], check=True,
                   capture_output=True, text=True)
    subprocess.run(["systemctl", "enable", "gts9-palm.service"], check=True,
                   capture_output=True, text=True)
    print(json.dumps({"verdict": "INSTALLED_NOT_STARTED", "boot": BOOT,
                      "ordinary_touch_current_boot": "left active",
                      "future_touch_service": "disabled",
                      "palm_service": "enabled", "reboot": False}, sort_keys=True))


if __name__ == "__main__":
    main()
