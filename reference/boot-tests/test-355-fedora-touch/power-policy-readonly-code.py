from pathlib import Path
import subprocess,json
for argv in (["systemd-detect-virt"],["systemctl","is-active","gts9-power-key.service"],["systemd-analyze","cat-config","systemd/logind.conf"],["runuser","-u","ms","--","dbus-run-session","--","gsettings","get","org.gnome.settings-daemon.plugins.power","power-button-action"],["runuser","-u","Debian-gdm","--","dbus-run-session","--","gsettings","get","org.gnome.settings-daemon.plugins.power","power-button-action"]):
 p=subprocess.run(argv,capture_output=True,text=True,timeout=10);print(json.dumps(dict(argv=argv,rc=p.returncode,stdout=p.stdout,stderr=p.stderr)))
p=Path('/usr/share/glib-2.0/schemas/org.gnome.settings-daemon.plugins.power.gschema.xml');print(p.read_text())
