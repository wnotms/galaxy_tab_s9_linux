"""Check the override against the actual Debian48.1 schema, not a mock schema."""
from pathlib import Path
import io, os, shutil, subprocess, tarfile, tempfile, unittest
ROOT=Path(__file__).resolve().parents[3]
class PowerKey(unittest.TestCase):
 def test_real_schema_override_changes_only_power_button(self):
  with tempfile.TemporaryDirectory() as td:
   folder=Path(td)
   archive=ROOT/'out/gnome-trixie-arm64/packages/gnome-settings-daemon-common_48.1-1_all.deb'
   data=subprocess.check_output(['dpkg-deb','--fsys-tarfile',str(archive)])
   with tarfile.open(fileobj=io.BytesIO(data)) as tar:
    for member in tar.getmembers():
     if member.isfile() and member.name.startswith('./usr/share/glib-2.0/schemas/') and member.name.endswith('.xml'):
      (folder/Path(member.name).name).write_bytes(tar.extractfile(member).read())
   env=dict(os.environ,GSETTINGS_SCHEMA_DIR=td,GSETTINGS_BACKEND='memory')
   subprocess.run(['glib-compile-schemas','--strict',td],check=True,capture_output=True)
   def get(key):return subprocess.check_output(['gsettings','get','org.gnome.settings-daemon.plugins.power',key],env=env,text=True).strip()
   baseline={n:get(n) for n in ('power-button-action','sleep-inactive-ac-type','sleep-inactive-battery-type','sleep-inactive-ac-timeout','sleep-inactive-battery-timeout','idle-dim')}
   self.assertEqual(baseline['power-button-action'],"'suspend'")
   shutil.copyfile(ROOT/'userspace/gnome/99-gts9-power-key.gschema.override',folder/'99-gts9-power-key.gschema.override')
   subprocess.run(['glib-compile-schemas','--strict',td],check=True,capture_output=True)
   self.assertEqual(get('power-button-action'),"'nothing'")
   for key,value in baseline.items():
    if key!='power-button-action':self.assertEqual(get(key),value)
if __name__=='__main__':unittest.main()
