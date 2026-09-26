"""The tablet must not enter systemd's automatic SSH transport paths.

Measured on the SM-X710 on 2026-09-26.  Every boot printed, on tty1 between the
login prompt lines:

    systemd-ssh-generator: Failed to query local AF_VSOCK CID: Cannot assign requested address

Root cause, from systemd v257's own sources rather than from the message text:

* `src/ssh-generator/ssh-generator.c` runs with `arg_auto = true` by default and,
  when `arg_auto` is set, calls `add_vsock_socket()`.
* `add_vsock_socket()` calls `detect_virtualization()` and proceeds only when
  `VIRTUALIZATION_IS_VM(v)`.
* `src/basic/virt.c` `detect_vm_device_tree()` reads
  `/proc/device-tree/hypervisor/compatible` and returns `VIRTUALIZATION_VM_OTHER`
  for anything it does not recognise.  This board's DT has that node
  (`qcom,gunyah-hypervisor-1.0`), so systemd reports `vm-other`.
* `add_vsock_socket()` then calls `vsock_get_local_cid()`.  There is no working
  AF_VSOCK transport here, so the CID ioctl fails with ENOTTY/EADDRNOTAVAIL and
  the generator logs the error and exits 1.

So the warning is not a kernel or systemd defect: Qualcomm's Gunyah hypervisor is
genuinely present under the Android-derived boot chain, and systemd correctly
concludes "this looks like a VM" from the device tree.  What is wrong is the
conclusion that a *physical tablet* wants a host/guest AF_VSOCK SSH transport.
The narrow fix is systemd's own switch for exactly that: `systemd.ssh_auto=no`,
supported since v256 (this tablet runs 257.13).

`systemd.ssh_auto=no` is preferred over masking the generator, because it:
  * expresses the intent ("the generator may exist, but do not auto-bind");
  * does not modify a Debian package file;
  * does not depend on a generator search-path override;
  * keeps its documented meaning across systemd upgrades;
  * leaves `systemd.ssh_listen=` and the `ssh.listen` credential working, should
    an explicit transport ever be wanted.

It does NOT touch `ssh.service` / `/usr/sbin/sshd` / TCP port 22, which is the
tablet's actual management channel.

These tests are source-level on purpose: they run on the host, with no device.
The device-level A/B proof is recorded in docs/SYSTEMD_SSH_GENERATOR_VSOCK.md.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Every profile that reaches a Debian systemd gets the token, so the A/B profiles
# stay comparable to each other and to production.
PROFILES = sorted((ROOT / 'boot').glob('cmdline*.txt'))

# The four byte-pinned profiles the other test modules check by hash.
PINNED = [
    'boot/cmdline.example.txt',
    'boot/cmdline.minimal-rootfs.example.txt',
    'boot/cmdline.poweroff-trace.example.txt',
    'boot/cmdline.boot-trace.example.txt',
]

TOKEN = 'systemd.ssh_auto=no'


def read(path):
    return (ROOT / path).read_text()


def tokens(text):
    return text.replace('\n', ' ').strip().split()


class EveryProfileDisablesAutomaticSSH(unittest.TestCase):
    def test_the_profile_set_is_not_empty(self):
        """A glob that silently matched nothing would pass every test below."""
        self.assertGreaterEqual(len(PROFILES), 11, [p.name for p in PROFILES])

    def test_every_profile_carries_the_switch(self):
        for path in PROFILES:
            with self.subTest(cmdline=path.name):
                toks = tokens(path.read_text())
                self.assertIn(TOKEN, toks)

    def test_it_is_a_boolean_no_and_never_a_guess(self):
        """`ssh_auto=` takes an optional boolean; only `no` disables it.

        Anything else - `0`, `false`, `off`, or a bare `systemd.ssh_auto=` - is
        either a different spelling that systemd may reject or an empty value
        that parses as *yes*, which would leave the warning in place while
        looking like a fix.
        """
        for path in PROFILES:
            with self.subTest(cmdline=path.name):
                for tok in tokens(path.read_text()):
                    if tok.startswith('systemd.ssh_auto='):
                        self.assertEqual(tok, TOKEN)

    def test_no_profile_uses_ssh_listen_to_fake_a_disable(self):
        """`systemd.ssh_listen=` is for ADDING explicit sockets.

        It cannot disable the automatic ones, and a value like `0`/`none` is not
        a documented address - it would be a guess that happens to parse or not.
        Its presence would also mean an explicit transport is wanted, which this
        tablet does not have.
        """
        for path in PROFILES:
            with self.subTest(cmdline=path.name):
                joined = ' '.join(tokens(path.read_text()))
                self.assertNotIn('systemd.ssh_listen', joined)

    def test_the_token_is_possible_for_the_bundle_builder(self):
        """The builder joins lines with spaces; a '#' line would become a token."""
        for path in PROFILES:
            with self.subTest(cmdline=path.name):
                text = path.read_text()
                self.assertNotIn('#', text)
                self.assertTrue(text.endswith('\n'))


class AbProfilesStayComparable(unittest.TestCase):
    """The stall A/B series varies exactly one token between profiles.

    If the baseline gained `systemd.ssh_auto=no` and, say, the skip-GPU profile
    did not, the experiment would vary two things at once and every later
    comparison would be invalid - so this is checked rather than assumed.
    """

    BASE = 'boot/cmdline.stall-ab-baseline.example.txt'
    VARIANTS = {
        'boot/cmdline.stall-ab-no-acd.example.txt': 'msm.disable_acd=1',
        'boot/cmdline.stall-ab-no-gpu.example.txt': 'msm.skip_gpu=1',
        'boot/cmdline.stall-ab-late-deferred.example.txt': 'deferred_probe_timeout=300',
    }

    def test_each_variant_differs_from_the_baseline_by_one_token_plus_the_switch(self):
        base = tokens(read(self.BASE))
        for name, variable in self.VARIANTS.items():
            with self.subTest(cmdline=name):
                got = tokens(read(name))
                # Same tokens except the one variable...
                without_var = [t for t in got if t != variable]
                self.assertEqual(without_var, base,
                                 f'{name} must differ from the baseline only by {variable}')
                # ... and the variable really is the difference.
                self.assertNotIn(variable, base)

    def test_every_ab_profile_shares_the_same_ssh_switch(self):
        for name in [self.BASE, *self.VARIANTS]:
            with self.subTest(cmdline=name):
                self.assertIn(TOKEN, tokens(read(name)))

    def test_the_ssh_switch_is_not_the_variable_under_test(self):
        """It must be in the shared prefix, so it cannot explain a difference."""
        base = tokens(read(self.BASE))
        self.assertIn(TOKEN, base)


class ConsoleInvariantUnchanged(unittest.TestCase):
    """This change must not disturb the no-serial architecture."""

    def test_still_exactly_one_console_and_it_is_the_panel(self):
        for path in PROFILES:
            with self.subTest(cmdline=path.name):
                toks = tokens(path.read_text())
                self.assertEqual([t for t in toks if t.startswith('console=')],
                                 ['console=tty0'])

    def test_no_serial_console_came_back(self):
        for path in PROFILES:
            with self.subTest(cmdline=path.name):
                toks = tokens(path.read_text())
                for gone in ('console=ttyGS0', 'console=ttyGS1', 'console=ttyMSM0',
                             'earlycon', 'ignore_console_null'):
                    self.assertNotIn(gone, toks)
                self.assertFalse([t for t in toks if t.startswith('console=ttyMSM')])
                self.assertFalse([t for t in toks if t.startswith('console=ttyGS')])


class NoVsockOrSerialCapabilityIsReintroduced(unittest.TestCase):
    """Check 5/6/7 of the brief: no VSOCK driver, no serial gadget back."""

    FRAGMENT = 'kernel/config/gts9wifi-mainline.fragment'

    def test_the_fragment_asks_for_no_vsock_driver(self):
        text = read(self.FRAGMENT)
        for symbol in ('CONFIG_VSOCKETS=y', 'CONFIG_VIRTIO_VSOCKETS=y',
                       'CONFIG_VMW_VSOCKETS=y', 'CONFIG_HYPERV_VSOCKETS=y',
                       'CONFIG_VSOCKETS_LOOPBACK=y'):
            with self.subTest(symbol=symbol):
                self.assertNotIn(symbol, text)

    def test_the_fragment_keeps_the_serial_gadget_off(self):
        text = read(self.FRAGMENT)
        for symbol in ('CONFIG_USB_CONFIGFS_ACM is not set',
                       'CONFIG_USB_CONFIGFS_SERIAL is not set',
                       'CONFIG_U_SERIAL_CONSOLE is not set',
                       'CONFIG_SERIAL_QCOM_GENI_CONSOLE is not set'):
            with self.subTest(symbol=symbol):
                self.assertIn('# ' + symbol, text)
        # The GENI port itself stays built in.
        self.assertIn('CONFIG_SERIAL_QCOM_GENI=y', text)
        self.assertIn('CONFIG_NULL_TTY=y', text)

    def test_the_build_still_asserts_the_no_serial_state(self):
        """A cmdline change is not allowed to weaken the build-time gate."""
        text = read('scripts/build-kernel.sh')
        for symbol in ('CONFIG_USB_CONFIGFS_ACM', 'CONFIG_USB_CONFIGFS_SERIAL',
                       'CONFIG_USB_U_SERIAL', 'CONFIG_U_SERIAL_CONSOLE'):
            with self.subTest(symbol=symbol):
                self.assertIn(symbol, text)
        self.assertIn('symbol_state', text)

    def test_no_unit_or_helper_recreates_a_serial_getty(self):
        overlay = ROOT / 'rootfs-overlay'
        for path in sorted(overlay.rglob('*')):
            if not path.is_file():
                continue
            for line in path.read_text(errors='replace').splitlines():
                code = line.split('#', 1)[0]
                if not code.strip():
                    continue
                with self.subTest(file=str(path), line=line.strip()):
                    self.assertNotIn('--autologin', code)
                    self.assertNotRegex(
                        code, r'(^|[|;&(`]|\$\(|\s)(/usr/sbin/|/sbin/)?agetty\s')

    def test_the_ssh_management_path_is_still_present(self):
        """The fix must not have been bought by weakening the way in."""
        self.assertTrue((ROOT / 'rootfs-overlay/etc/gts9-usb-net').is_file())
        self.assertIn('ncm', read('rootfs-overlay/etc/gts9-usb-net'))
        installer = read('scripts/install-debian-rootfs.sh')
        self.assertIn('--ssh-key', installer)
        self.assertIn('authorized_keys', installer)
        gadget = read('rootfs-overlay/usr/libexec/gts9-usb-acm')
        self.assertIn('ncm', gadget)
        # No creation of a serial function.
        self.assertNotIn('mkdir -p "$GADGET/functions/acm', gadget)


class TheDocumentedRootCauseMatchesUpstream(unittest.TestCase):
    """The doc must name the mechanism, not just the message.

    The instruction for this work was explicit that the cause must be measured
    rather than guessed, and that "systemd bug" / "kernel bug" must not be written
    before there is evidence. On this board the evidence is the device tree.
    """

    DOC = 'docs/SYSTEMD_SSH_GENERATOR_VSOCK.md'

    def test_the_document_exists_and_names_the_symptom(self):
        text = read(self.DOC)
        self.assertIn('Failed to query local AF_VSOCK CID', text)
        self.assertIn('Cannot assign requested address', text)

    def test_it_records_the_real_root_cause_chain(self):
        text = read(self.DOC)
        # The device-tree node, which is what makes systemd say vm-other.
        self.assertIn('qcom,gunyah-hypervisor', text)
        self.assertIn('vm-other', text)
        # The generator function that takes the VM path.
        self.assertIn('add_vsock_socket', text)
        # And the file that does the detection.
        self.assertIn('detect_vm_device_tree', text)
        # It must distinguish "a hypervisor exists underneath" from "this instance
        # wants a host/guest AF_VSOCK transport" - that distinction is the whole
        # diagnosis, and writing only the first would justify a wrong fix.
        self.assertIn('hypervisor', text)
        self.assertIn('physical', text)

    def test_it_names_the_switch_and_the_version_that_supports_it(self):
        text = read(self.DOC)
        self.assertIn('systemd.ssh_auto=no', text)
        self.assertIn('257', text)          # the version measured on the tablet
        self.assertIn('v256', text)         # the version that introduced it

    def test_it_records_the_verification_and_the_unchanged_ssh_path(self):
        text = read(self.DOC)
        self.assertIn('ssh.service', text)
        self.assertIn('22', text)
        self.assertIn('ncm.usb0', text)


if __name__ == '__main__':
    unittest.main()
