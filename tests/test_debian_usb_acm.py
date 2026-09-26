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

    def test_creates_exactly_one_acm_function(self):
        """One serial port, not two.

        Until 2026-09-26 there were two because their roles were split: acm.usb0
        was the login shell and acm.usb1 the kernel printk console, since a gadget
        serial console takes its port's IN endpoint and one port cannot be both.

        Both consoles are gone, so the second port had no purpose left - it
        existed only to be the port printk registered on (it was created second so
        u_serial handed it line 1).  It is removed, and exactly one serial port
        remains so a terminal program still has a wired endpoint that does not
        depend on the network function having bound.

        This must stay a single port: a second serial port appearing again means
        something is trying to put a console back on the gadget.
        """
        self.run_helper()
        functions = sorted(p.name for p in (self.gadget / 'functions').iterdir())
        self.assertEqual(functions, ['acm.usb0'])
        links = sorted(p.name for p in (self.gadget / 'configs' / 'c.1').iterdir()
                       if p.is_symlink())
        self.assertEqual(links, ['acm.usb0'])
        # The node it lands on is /dev/ttyGS0: gserial_alloc_line() hands out the
        # lowest free line, so acm.usb0 must be the first serial function created
        # and the only one.  Compare against the *call* to setup_network, not its
        # definition, which appears earlier in the file.
        text = HELPER.read_text()
        create0 = text.index('mkdir -p "$GADGET/functions/acm.usb0"')
        self.assertNotIn('mkdir -p "$GADGET/functions/acm.usb1"', text)
        call = text.index('\nsetup_network\n')
        self.assertLess(create0, call,
                        'acm.usb0 must be created before the network function, so '
                        'it keeps /dev/ttyGS0')

    def test_an_upgraded_gadget_drops_the_retired_port(self):
        """The live gadget is rebuilt, because configfs cannot edit a bound one.

        An upgraded rootfs keeps the gadget the previous install built, and that
        gadget has acm.usb1 in its configuration.  configfs refuses to remove a
        function from a bound gadget, so the helper has to unbind, remove the
        function and let the normal path rebuild - otherwise the second port
        survives the upgrade forever and the removal is only true for new installs.
        """
        self.run_helper()  # builds the gadget
        # Simulate the old layout: put acm.usb1 back and leave the gadget bound.
        (self.gadget / 'functions' / 'acm.usb1').mkdir()
        (self.gadget / 'configs' / 'c.1' / 'acm.usb1').symlink_to(
            self.gadget / 'functions' / 'acm.usb1')
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.gadget / 'functions' / 'acm.usb1').exists(),
                         'the retired port must not survive an upgrade')
        self.assertFalse((self.gadget / 'configs' / 'c.1' / 'acm.usb1').exists())
        # ... and the remaining port still came back and bound.
        self.assertTrue((self.gadget / 'functions' / 'acm.usb0').is_dir())
        self.assertEqual((self.gadget / 'UDC').read_text().strip(), 'a600000.usb')

    def test_the_remaining_port_is_not_made_a_console(self):
        """The one surviving port is forced OFF, never on.

        This used to assert 0 on the shell port and 1 on the console port.  The
        gadget kernel console is the measured cause of the boot stall - a userspace
        write() to /dev/console blocks in n_tty_write() while nothing drains the
        port (docs/BOOT_CONSOLE_BLOCK.md) - and the kernel is now built without
        CONFIG_U_SERIAL_CONSOLE, so the configfs attribute does not exist on a
        current kernel.

        The write is kept, and forces 0, so that running this script against an
        OLDER kernel (a recovery image, a rollback) also leaves no console on the
        gadget.  Nothing may set 1 again.
        """
        text = HELPER.read_text()
        self.assertIn('echo 0 > "$GADGET/functions/acm.usb0/console"', text)
        self.assertNotIn('echo 1 >', text)
        self.assertIn('[ -e "$GADGET/functions/acm.usb0/console" ]', text)
        self.assertIn('clear_console', text)
        # No function may be addressed that no longer exists.
        self.assertNotIn('$GADGET/functions/acm.usb1/console', text)

    def test_the_network_transport_ships_in_the_overlay(self):
        # /etc/gts9-usb-net used to be created by hand on the tablet.  With the
        # serial consoles gone it is the only way in, so a rootfs that lacks it is
        # unreachable - it must come from the overlay.
        net_conf = ROOT / 'rootfs-overlay' / 'etc' / 'gts9-usb-net'
        self.assertTrue(net_conf.is_file(), 'the ssh transport config must ship')
        # Comments and blanks are allowed; the first real line is the directive.
        line = next(ln for ln in net_conf.read_text().splitlines()
                    if ln.strip() and not ln.lstrip().startswith('#'))
        kind, addr = line.split()
        self.assertIn(kind, ('ncm', 'ecm'))
        # The host reaches this address with no configuration of its own.
        self.assertTrue(addr.startswith('169.254.'), addr)
        # ... and the helper must actually skip the comment header.
        helper = HELPER.read_text()
        self.assertIn("'#'*", helper)

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
