"""Start one qualified desktop and non-grabbing capture; preserve GDM masks."""
from pathlib import Path
import json
import os
import subprocess
import sys
import time

BOOT = "28fcdaa6-15f0-4188-a2a0-4e3e6cbb96af"
assert Path("/proc/sys/kernel/random/boot_id").read_text().strip() == BOOT
assert subprocess.check_output(["systemctl", "is-active", "gts9-palm.service"], text=True).strip() == "active"
names = ("gdm.service", "gdm3.service", "display-manager.service")
for name in names:
    path = Path("/etc/systemd/system") / name
    assert path.is_symlink() and os.readlink(path) == "/dev/null"
try:
    subprocess.run(["systemctl", "unmask", *names], check=True, capture_output=True)
    subprocess.run(["systemctl", "start", "gdm.service"], check=True, capture_output=True, timeout=40)
finally:
    subprocess.run(["systemctl", "mask", *names], check=True, capture_output=True)
assert subprocess.check_output(["systemctl", "is-active", "gdm.service"], text=True).strip() == "active"
assert not Path("/var/log/gts9-test363-pair").exists()
source = sys.stdin.buffer.read(32768)
assert source and len(source) < 32768
script = Path("/var/tmp/gts9-test363-capture.py")
with script.open("xb") as out:
    out.write(source)
with Path("/var/tmp/gts9-test363-capture.stdout").open("xb") as out, Path("/var/tmp/gts9-test363-capture.stderr").open("xb") as err:
    worker = subprocess.Popen(["systemd-inhibit", "--what=sleep", "--mode=block",
        "--who=Test363", "--why=Pen/palm input acceptance; suspend outside scope",
        "python3", str(script)], stdin=subprocess.DEVNULL, stdout=out,
        stderr=err, start_new_session=True)
for _ in range(50):
    meta = Path("/var/log/gts9-test363-pair/meta.json")
    if meta.exists():
        value = json.loads(meta.read_text())
        stat = Path("/proc") / str(value["pid"]) / "stat"
        assert stat.read_text().rsplit(")", 1)[1].split()[19] == value["proc_start_ticks"]
        assert not Path("/var/log/gts9-test363-pair/terminal.json").exists()
        print(json.dumps(value))
        break
    assert worker.poll() is None, "capture exited before ready"
    time.sleep(0.1)
else:
    raise RuntimeError("capture readiness deadline")
