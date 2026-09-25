"""Host checks for the Debian-side X710 USB ACM debug console."""
import os
import re
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OVERLAY = ROOT / 'rootfs-overlay' / 'usr'
HELPER = OVERLAY / 'libexec' / 'gts9-usb-acm'
STAGE_HELPER = OVERLAY / 'libexec' / 'gts9-record-debian-stage'
UNIT = (OVERLAY / 'lib/systemd/system/gts9-usb-acm.service').read_text()
HELPER_TEXT = HELPER.read_text()


def code_only(text):
    """Drop comment lines: the checks below are about executed commands."""
    return '\n'.join(line for line in text.splitlines()
                     if not line.lstrip().startswith('#'))


HELPER_CODE = code_only(HELPER_TEXT)

INITRAMFS_RECORD = """\
format_version=1
origin=initramfs
boot_id=aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee
kernel_release=7.2.0-rc3-gts9wifi-dirty
cmdline=console=ttyMSM0,115200n8 gts9_minimal_rootfs=1
timestamp=2026-09-24T00:00:00Z
uptime_seconds=3
root_device=/dev/mmcblk1p1
stage=switch-root
stage_history=kernel-userspace,waiting-root,root-found,mounting-root,root-mounted,init-found,switch-root
failure=none
mmc_devices=/dev/mmcblk1,/dev/mmcblk1p1
"""


class UsbAcmServiceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.configfs = self.root / 'configfs'
        self.gadget = self.configfs / 'usb_gadget' / 'gts9'
        self.udc_dir = self.root / 'udc'
        (self.configfs / 'usb_gadget').mkdir(parents=True)
        self.udc_dir.mkdir()
        self.record = self.root / 'gts9-minimal-last-boot'
        self.record.write_text(INITRAMFS_RECORD)

    def run_helper(self, *args, udc='a600000.usb', wait='2', env=None):
        if udc is not None:
            (self.udc_dir / udc).write_text('')
        environment = dict(os.environ,
                           GTS9_USB_CONFIGFS=str(self.configfs),
                           GTS9_USB_GADGET_DIR=str(self.gadget),
                           GTS9_USB_UDC_DIR=str(self.udc_dir),
                           GTS9_USB_TTY=str(self.root / 'ttyGS0'),
                           GTS9_USB_UDC_WAIT_SECONDS=wait,
                           GTS9_USB_TTY_WAIT_SECONDS='1',
                           GTS9_STAGE_HELPER=str(STAGE_HELPER),
                           GTS9_MINIMAL_BOOT_RECORD=str(self.record))
        if env:
            environment.update(env)
        return subprocess.run(['sh', str(HELPER), *args], env=environment,
                              text=True, capture_output=True, check=False)

    def record_fields(self):
        fields = {}
        for line in self.record.read_text().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                fields[key] = value
        return fields

    def test_creates_the_verified_acm_gadget(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.gadget / 'idVendor').read_text().strip(), '0x0525')
        self.assertEqual((self.gadget / 'idProduct').read_text().strip(), '0xa4a7')
        self.assertTrue((self.gadget / 'functions' / 'acm.usb0').is_dir())
        self.assertTrue((self.gadget / 'configs' / 'c.1' / 'acm.usb0').is_symlink())
        self.assertTrue((self.gadget / 'configs' / 'c.1' / 'acm.usb0').resolve().is_dir())
        self.assertEqual((self.gadget / 'UDC').read_text().strip(), 'a600000.usb')

    def test_creates_the_two_acm_functions(self):
        # Two ports since test-184: acm.usb0 is the login shell, acm.usb1 is the
        # kernel console.  A gadget serial console takes its port's IN endpoint,
        # so one port cannot be both.
        self.run_helper()
        functions = sorted(p.name for p in (self.gadget / 'functions').iterdir())
        self.assertEqual(functions, ['acm.usb0', 'acm.usb1'])
        links = sorted(p.name for p in (self.gadget / 'configs' / 'c.1').iterdir()
                       if p.is_symlink())
        self.assertEqual(links, ['acm.usb0', 'acm.usb1'])

    def test_console_split_is_requested_for_the_second_port(self):
        # The configfs "console" attribute only exists when the kernel is built
        # with CONFIG_U_SERIAL_CONSOLE, so a static fake tree cannot host it and
        # the split is checked at the source level instead: 0 on the shell port,
        # 1 on the console port, and both best-effort so the gadget still comes
        # up on a kernel without a gadget console.
        text = HELPER.read_text()
        self.assertIn('echo 0 > "$GADGET/functions/acm.usb0/console"', text)
        self.assertIn('echo 1 > "$GADGET/functions/acm.usb1/console"', text)
        self.assertIn('[ -e "$GADGET/functions/acm.usb0/console" ]', text)
        self.assertIn('[ -e "$GADGET/functions/acm.usb1/console" ]', text)
        self.assertIn('split_consoles', text)

    def test_helper_never_mentions_dangerous_usb_functions(self):
        # Mass storage would expose the root filesystem, RNDIS/MTP/UVC/HID are
        # not needed, and the ADB *function* would need a second gadget - which
        # cannot bind while this one owns the UDC.  None of them may appear.
        for forbidden in ('mass_storage', 'rndis', 'mtp', 'adb', 'uvc', 'hid'):
            self.assertNotIn(forbidden, HELPER_CODE.lower(), forbidden)

    def test_the_network_function_is_the_one_deliberate_exception(self):
        # Narrowed on 2026-09-25: NCM/ECM is allowed, because it is the transport
        # ssh and adb are reached over, but ONLY behind all of these conditions.
        text = HELPER_CODE
        self.assertIn('ncm | ecm', text, 'only ncm and ecm are accepted')

        # (a) off unless the flag file exists
        self.assertIn("NET_CONF=${GTS9_USB_NET_CONF:-/etc/gts9-usb-net}", text)
        for fn in ('setup_network', 'configure_network'):
            self.assertRegex(
                text, rf"{fn}\(\) \{{\n\t\[ -n \"\$net_kind\" \] \|\| return 0",
                f'{fn} must be a no-op with no flag file')

        # (b) any failure drops the function and keeps the console
        self.assertIn('net_drop', text)
        bind = re.search(r'if ! echo "\$udc" > "\$GADGET/UDC".*?\nfi', text, re.S)
        self.assertIsNotNone(bind, 'the UDC bind block is missing')
        self.assertIn('net_drop', bind.group(0),
                      'a failed bind must retry without the network function')

        # (c) no second gadget, and no block device
        self.assertNotIn('usb_gadget/g1', text)
        for forbidden in ('/dev/mmcblk', 'mkfs', 'fsck', 'dd '):
            self.assertNotIn(forbidden, text, forbidden)

    def test_helper_cannot_touch_the_root_filesystem(self):
        # The console must never depend on - or be able to disturb - the TF
        # card, the UFS or the misc partition.
        for forbidden in ('/dev/mmcblk', '/dev/sd', 'misc', 'blkid', 'mkfs',
                          'fsck', 'mount /', 'dd '):
            self.assertNotIn(forbidden, HELPER_CODE, forbidden)

    def test_panel_independence_of_the_usb_path(self):
        # Nothing in the USB console path may reference DRM, the framebuffer,
        # tty1 or the panel: either channel has to survive the other failing.
        for forbidden in ('/sys/class/graphics', 'ana38407', 'tty1', 'fb0'):
            self.assertNotIn(forbidden, HELPER_CODE, forbidden)
            self.assertNotIn(forbidden, UNIT, forbidden)

    def test_failure_is_reported_and_does_not_block_boot(self):
        started = time.monotonic()
        result = self.run_helper(udc=None, wait='1')
        elapsed = time.monotonic() - started
        self.assertEqual(result.returncode, 1)
        self.assertLess(elapsed, 10, 'the UDC wait must stay bounded')
        fields = self.record_fields()
        self.assertEqual(fields['debian_failure'], 'usb-acm-failed')
        self.assertEqual(fields['debian_stage'], 'usb-acm-failed')
        self.assertIn('no USB device controller', result.stderr)

    def test_success_is_recorded_in_the_boot_record(self):
        self.run_helper()
        fields = self.record_fields()
        self.assertEqual(fields['debian_stage'], 'usb-acm-ready')
        self.assertEqual(fields['debian_stage_history'], 'usb-acm-ready')
        self.assertEqual(fields['debian_failure'], 'none')

    def test_an_already_bound_gadget_is_not_rebuilt(self):
        self.run_helper()
        marker = (self.gadget / 'strings' / '0x409' / 'serialnumber')
        original = marker.read_text()
        marker.write_text('changed-by-test\n')
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('already bound', result.stdout)
        # The existing gadget was left exactly as it was.
        self.assertEqual(marker.read_text(), 'changed-by-test\n')
        self.assertEqual(original, 'gts9wifi-0001\n')

    def test_service_is_oneshot_and_never_required_by_the_boot_target(self):
        self.assertIn('Type=oneshot', UNIT)
        self.assertIn('ExecStart=/usr/libexec/gts9-usb-acm', UNIT)
        self.assertIn('After=local-fs.target', UNIT)
        self.assertIn('Before=serial-getty@ttyGS0.service', UNIT)
        self.assertNotIn('Requires=', UNIT)
        self.assertNotIn('Before=multi-user.target', UNIT)
        self.assertNotIn('reboot', UNIT)
        self.assertNotIn('panic', UNIT)
        self.assertIn('WantedBy=multi-user.target', UNIT)

    def test_helper_has_no_bash_only_features(self):
        for bashism in ('[[', 'declare ', 'local '):
            self.assertNotIn(bashism, HELPER_CODE, bashism)


if __name__ == '__main__':
    unittest.main()
