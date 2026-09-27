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
        # The network function's config.  It is the ONLY function now, and the
        # helper refuses to bind a gadget that provides no way into the tablet, so
        # a harness without it would exercise a failure path rather than the
        # normal one.
        self.net_conf = self.root / 'gts9-usb-net'
        self.write_net_conf('ncm 169.254.42.1/16')

    def write_net_conf(self, text):
        self.net_conf.write_text(text + '\n')

    def run_helper(self, *args, udc='a600000.usb', wait='2', env=None):
        if udc is not None:
            (self.udc_dir / udc).write_text('')
        environment = dict(os.environ,
                           GTS9_USB_CONFIGFS=str(self.configfs),
                           GTS9_USB_GADGET_DIR=str(self.gadget),
                           GTS9_USB_UDC_DIR=str(self.udc_dir),
                           GTS9_USB_NET_CONF=str(self.net_conf),
                           GTS9_USB_UDC_WAIT_SECONDS=wait,
                           GTS9_USB_IFACE_WAIT_SECONDS='1',
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

    def test_creates_the_verified_gadget_with_no_serial_function(self):
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.gadget / 'idVendor').read_text().strip(), '0x0525')
        self.assertEqual((self.gadget / 'idProduct').read_text().strip(), '0xa4a7')
        self.assertEqual((self.gadget / 'UDC').read_text().strip(), 'a600000.usb')
        # The gadget exists and is bound, and provides the network function that
        # ssh is reached over - and nothing serial.
        self.assertTrue((self.gadget / 'functions' / 'ncm.usb0').is_dir())
        self.assertTrue((self.gadget / 'configs' / 'c.1' / 'ncm.usb0').is_symlink())

    def test_no_serial_function_is_created_at_all(self):
        """The gadget is exactly one function: NCM.

        Three steps got here, and each exposed the next.  The serial *consoles*
        went first (acm.usb1 was the kernel printk console, acm.usb0 carried an
        autologin shell); then acm.usb1, whose only purpose was to be the port
        printk registered on; then acm.usb0, because nothing ever wrote to it,
        nothing held it open, the kernel log did not come out of it, and a login
        is now delivered as an ssh key at install time instead.

        The kernel is built without USB_CONFIGFS_ACM and USB_CONFIGFS_SERIAL, so
        this is not merely a convention: no configfs serial function can be
        created even by hand.  A serial function appearing again would mean a
        capability had returned to a device that deliberately has none.
        """
        self.run_helper()
        functions = sorted(p.name for p in (self.gadget / 'functions').iterdir())
        self.assertEqual(functions, ['ncm.usb0'])
        links = sorted(p.name for p in (self.gadget / 'configs' / 'c.1').iterdir()
                       if p.is_symlink())
        self.assertEqual(links, ['ncm.usb0'])
        text = HELPER.read_text()
        # No serial function may be CREATED.  acm.usb0/acm.usb1 appear only in the
        # migration that removes them from an older install, so the check is for a
        # creation command, not for the string.
        self.assertNotIn('mkdir -p "$GADGET/functions/acm', text)
        self.assertNotIn('mkdir -p "$GADGET/functions/gser', text)
        self.assertIn('retire_serial_ports', text)

    def test_a_missing_network_function_is_fatal(self):
        """Without NCM the gadget provides no way into the tablet at all.

        A serial port used to be the consolation prize; there is none now, so an
        unbuildable network function has to fail loudly rather than bind a gadget
        that nothing can reach.
        """
        text = HELPER.read_text()
        self.assertIn('if [ -z "$net_kind" ]; then', text)
        self.assertIn('fail "no network function', text)

    def test_an_upgraded_gadget_drops_the_serial_ports(self):
        """The live gadget is rebuilt, because configfs cannot edit a bound one.

        An upgraded rootfs keeps the gadget the previous install built, and that
        gadget has acm.usb0 (and possibly acm.usb1) in its configuration.  configfs
        refuses to remove a function from a bound gadget, so the helper has to
        unbind, remove them and let the normal path rebuild - otherwise the serial
        ports survive the upgrade forever and the removal is only true for new
        installs.
        """
        self.run_helper()  # builds the gadget
        # Simulate the old layout: put both serial ports back, bound.
        for fn in ('acm.usb0', 'acm.usb1'):
            (self.gadget / 'functions' / fn).mkdir()
            (self.gadget / 'configs' / 'c.1' / fn).symlink_to(
                self.gadget / 'functions' / fn)
        result = self.run_helper()
        self.assertEqual(result.returncode, 0, result.stderr)
        for fn in ('acm.usb0', 'acm.usb1'):
            self.assertFalse((self.gadget / 'functions' / fn).exists(),
                             f'{fn} must not survive an upgrade')
            self.assertFalse((self.gadget / 'configs' / 'c.1' / fn).exists())
        # ... and the network function came back and bound, which is what the ssh
        # transport needs.
        self.assertTrue((self.gadget / 'functions' / 'ncm.usb0').is_dir())
        self.assertEqual((self.gadget / 'UDC').read_text().strip(), 'a600000.usb')

    def test_no_configfs_console_attribute_is_written(self):
        """Nothing may touch a gadget console attribute any more.

        This used to assert the split: 0 on the shell port, 1 on the console port.
        Then it asserted 0 on the one surviving port.  Now there is no serial port
        at all, so there is no console attribute either, and the kernel is built
        without CONFIG_U_SERIAL_CONSOLE - the attribute is compiled out of f_acm.

        Asserting the absence is the point: any write to a gadget console
        attribute would mean a serial function exists to host it.
        """
        text = HELPER.read_text()
        self.assertNotIn('/console"', text)
        self.assertNotIn('clear_console', text)
        # The only functions named anywhere are the network one and the two the
        # migration removes.
        self.assertIn('retire_serial_ports', text)

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
        for forbidden in ('mass_storage', 'rndis', 'mtp', 'uvc', 'hid'):
            self.assertNotIn(forbidden, HELPER_CODE.lower(), forbidden)

    def test_the_network_function_is_the_only_function(self):
        """NCM is not an "exception" any more - it is the entire gadget.

        This test used to be called "the one deliberate exception" and assert that
        a failed bind *retried without* the network function, keeping the serial
        console as the consolation prize.  There is no console now, so a gadget
        without the network function provides no way into the tablet at all and
        must fail instead.

        What is still forbidden is everything else: mass storage would expose the
        root filesystem, and RNDIS/MTP/UVC/HID/ADB are not needed and are not
        wanted on a device whose only external link is a debug cable.
        """
        text = HELPER_CODE
        self.assertIn('ncm | ecm', text, 'only ncm and ecm are accepted')

        # (a) off unless the flag file exists
        self.assertIn("NET_CONF=${GTS9_USB_NET_CONF:-/etc/gts9-usb-net}", text)
        for fn in ('setup_network', 'configure_network'):
            self.assertRegex(
                text, rf"{fn}\(\) \{{\n\t\[ -n \"\$net_kind\" \] \|\| return 0",
                f'{fn} must be a no-op with no flag file')

        # (b) no network function is fatal, because nothing else provides a login
        self.assertIn('fail "no network function', text)
        # ... and a failed bind must NOT silently continue without it
        bind = re.search(r'if ! echo "\$udc" > "\$GADGET/UDC".*?\nfi', text, re.S)
        self.assertIsNotNone(bind, 'the UDC bind block is missing')
        self.assertIn('fail', bind.group(0),
                      'a failed bind must be fatal now that no serial port is left')
        self.assertNotIn('net_drop', bind.group(0),
                         'there is no fallback function to drop back to')

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

    def adb_fixture(self, ready='1'):
        self.run_helper()
        (self.gadget / 'UDC').write_text('')
        (self.gadget / 'functions/ffs.adb').mkdir()
        (self.gadget / 'functions/ffs.adb/ready').write_text(ready)
        (self.gadget / 'os_desc').mkdir()
        conf = self.root / 'adb.conf'
        conf.write_text('1')
        state = self.root / 'adb.mount-id'
        state.write_text('177')
        holder = self.root / 'holder'
        holder.write_text(str(os.getpid()))
        bindir = self.root / 'bin'
        bindir.mkdir()
        findmnt = bindir / 'findmnt'
        findmnt.write_text('#!/bin/sh\necho 177\n')
        findmnt.chmod(0o755)
        return dict(PATH=str(bindir) + ':' + os.environ['PATH'],
                    GTS9_USB_ADB_CONF=str(conf),
                    GTS9_USB_ADB_STATE=str(state),
                    GTS9_USB_ADB_HOLD=str(holder),
                    GTS9_USB_ADB_WAIT_SECONDS='0')

    def test_ready_adb_shares_ncm_gadget(self):
        env = self.adb_fixture()
        result = self.run_helper(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.gadget / 'configs/c.1/ffs.adb').is_symlink())
        self.assertTrue((self.gadget / 'configs/c.1/ncm.usb0').is_symlink())
        self.assertEqual((self.gadget / 'os_desc/qw_sign').read_text().strip(), 'MSFT100')

    def test_adb_timeout_preserves_network(self):
        env = self.adb_fixture(ready='0')
        result = self.run_helper(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('readiness timed out', result.stderr)
        self.assertFalse((self.gadget / 'configs/c.1/ffs.adb').exists())
        self.assertTrue((self.gadget / 'configs/c.1/ncm.usb0').is_symlink())
        self.assertEqual((self.gadget / 'UDC').read_text().strip(), 'a600000.usb')

    def test_unsafe_mount_is_not_added(self):
        env = self.adb_fixture()
        Path(env['GTS9_USB_ADB_STATE']).write_text('different-mount')
        result = self.run_helper(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.gadget / 'configs/c.1/ffs.adb').exists())

    def test_bound_ncm_is_never_reenumerated_for_adb(self):
        env = self.adb_fixture()
        (self.gadget / 'UDC').write_text('existing-udc')
        result = self.run_helper(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.gadget / 'UDC').read_text(), 'existing-udc')
        self.assertFalse((self.gadget / 'configs/c.1/ffs.adb').exists())

    def test_failed_composite_bind_retries_with_ncm(self):
        env = self.adb_fixture()
        udc = self.gadget / 'UDC'
        udc.unlink()
        udc.symlink_to('/dev/full')
        rm = self.root / 'bin/rm'
        # Model a controller that refuses the composite, but accepts NCM.
        rm.write_text('#!/bin/sh\n/bin/rm "$@"\n'
                      'case "$*" in *configs/c.1/ffs.adb*)\n'
                      '/bin/rm "$GTS9_USB_GADGET_DIR/UDC"\n'
                      ': > "$GTS9_USB_GADGET_DIR/UDC";; esac\n')
        rm.chmod(0o755)
        # Avoid cat on /dev/full in the already-bound probe.
        cat = self.root / 'bin/cat'
        cat.write_text('#!/bin/sh\n[ "$1" = "$GTS9_USB_GADGET_DIR/UDC" ] && exit 0\nexec /bin/cat "$@"\n')
        cat.chmod(0o755)
        result = self.run_helper(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('retrying NCM only', result.stderr)
        self.assertFalse((self.gadget / 'configs/c.1/ffs.adb').exists())
        self.assertTrue((self.gadget / 'configs/c.1/ncm.usb0').is_symlink())
        self.assertEqual(udc.read_text().strip(), 'a600000.usb')

    def test_prepare_mounts_safely_and_does_not_reuse_unknown_mount(self):
        env = self.adb_fixture()
        env.update(GTS9_USB_CONFIGFS=str(self.configfs),
                   GTS9_USB_GADGET_DIR=str(self.gadget),
                   GTS9_USB_ADB_FFS=str(self.root / 'ffs'),
                   GTS9_ADBD_BINARY='/bin/true')
        bindir = self.root / 'bin'
        mounted = self.root / 'mounted'
        mountpoint = bindir / 'mountpoint'
        mountpoint.write_text(f'#!/bin/sh\ntest -f "{mounted}"\n')
        mountpoint.chmod(0o755)
        mount = bindir / 'mount'
        mount.write_text(f'#!/bin/sh\necho "$*" > "{mounted}"\n')
        mount.chmod(0o755)
        prepare = OVERLAY / 'libexec/gts9-usb-adb-prepare'
        def run():
            return subprocess.run(['sh', str(prepare)], env=dict(os.environ, **env),
                                  text=True, capture_output=True)
        self.assertEqual(run().returncode, 0)
        self.assertIn('-o no_disconnect=1 adb', mounted.read_text())
        self.assertEqual(Path(env['GTS9_USB_ADB_STATE']).read_text().strip(), '177')
        Path(env['GTS9_USB_ADB_STATE']).unlink()
        self.assertIn('existing mount was not prepared safely', run().stderr)
        self.assertFalse(Path(env['GTS9_USB_ADB_STATE']).exists())
        (self.gadget / 'UDC').write_text('live-udc')
        self.assertIn('bound gadget unchanged', run().stdout)
        self.assertEqual((self.gadget / 'UDC').read_text(), 'live-udc')

    def test_adbd_starts_between_prepare_and_bind_and_keeps_tcp(self):
        unit = (OVERLAY / 'lib/systemd/system/gts9-adbd.service').read_text()
        directives = code_only(unit)
        self.assertIn('After=local-fs.target gts9-usb-adb-prepare.service', directives)
        self.assertNotIn('gts9-usb-acm.service', directives)
        self.assertNotIn('network.target', directives)
        self.assertIn('Environment=ADBD_PORT=5555', directives)
        self.assertIn('After=local-fs.target gts9-usb-adb-prepare.service gts9-adbd.service', UNIT)

    def test_daemon_restart_cannot_reset_an_active_composite(self):
        env = self.adb_fixture()
        guard = OVERLAY / 'libexec/gts9-adbd-can-start'
        def allowed():
            return subprocess.run(['sh', str(guard)], capture_output=True,
                env=dict(os.environ, GTS9_USB_GADGET_DIR=str(self.gadget))).returncode == 0
        self.assertTrue(allowed())
        self.assertEqual(self.run_helper(env=env).returncode, 0)
        self.assertFalse(allowed())
        (self.gadget / 'UDC').write_text('')
        self.assertTrue(allowed())
        (self.gadget / 'configs/c.1/ffs.adb').unlink()
        (self.gadget / 'UDC').write_text('ncm-only')
        self.assertTrue(allowed())

    def test_missing_holder_keeps_ncm_only(self):
        env = self.adb_fixture()
        Path(env['GTS9_USB_ADB_HOLD']).unlink()
        result = self.run_helper(env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.gadget / 'configs/c.1/ffs.adb').exists())

    def test_holder_keeps_ep0_open_without_writing(self):
        env = self.adb_fixture()
        ffs = self.root / 'ffs'
        ffs.mkdir()
        ep0 = ffs / 'ep0'
        ep0.write_text('descriptors-unchanged')
        holder = subprocess.Popen(['sh', str(OVERLAY / 'libexec/gts9-usb-adb-hold')],
            env=dict(os.environ, **env, GTS9_USB_GADGET_DIR=str(self.gadget),
                     GTS9_USB_ADB_FFS=str(ffs)))
        try:
            for _ in range(100):
                if Path(f'/proc/{holder.pid}/fd/3').resolve() == ep0:
                    break
                time.sleep(.01)
            self.assertEqual(Path(f'/proc/{holder.pid}/fd/3').resolve(), ep0)
            self.assertEqual(ep0.read_text(), 'descriptors-unchanged')
        finally:
            holder.terminate()
            holder.wait(timeout=3)

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
