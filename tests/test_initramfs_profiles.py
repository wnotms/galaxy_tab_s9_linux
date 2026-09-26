"""Host checks for the two initramfs profiles and the boundary between them.

Until 2026-09-26 there was one image. Its /init was boot/bringup-init.sh, which
branched on `gts9_minimal_rootfs=1` and exec'd boot/minimal-rootfs-init.sh - so a
normal Debian boot carried the whole 200-test bring-up script, and everything that
script could do (USB gadget creation, mass storage, GPT/BCB work, RTC telemetry,
display recovery, hardware reports, module loading) was reachable from a boot that
only needed to mount a card and switch_root.

There are now two images with one job each:

  production (scripts/build-minimal-initramfs.sh, out/minimal-initramfs)
    /init IS the handoff. Mount the pseudo filesystems, find and mount the ext4
    root, check /newroot/sbin/init, record the stage history, move /dev /proc /sys
    /run, exec switch_root. Rescue shell on tty1 if any of that fails.

  debug (scripts/build-bringup-initramfs.sh, out/bringup-initramfs)
    keeps the diagnostics: hardware report, MSC evidence channel, GPT/BCB, RTC,
    panel recovery, rescue shells.

These tests are source-level and cheap, so they run on every host. The device
verification is in reference/boot-tests/.

The checks are deliberately about EXECUTION rather than vocabulary. The debug
script contains long comments explaining why it no longer creates a serial
function; a test that forbade the string would force those explanations out of the
code and make it less useful, not safer.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROD_BUILDER = ROOT / 'scripts/build-minimal-initramfs.sh'
DEBUG_BUILDER = ROOT / 'scripts/build-bringup-initramfs.sh'
COMMON_LIB = ROOT / 'scripts/lib/initramfs-common.sh'
AUDIT = ROOT / 'scripts/audit-initramfs.sh'
VALIDATOR = ROOT / 'scripts/validate-boot-bundle.sh'
INIT = ROOT / 'boot/minimal-rootfs-init.sh'
STATE = ROOT / 'boot/minimal-rootfs-state.sh'
BRINGUP = ROOT / 'boot/bringup-init.sh'


def read(path):
    return (ROOT / path).read_text() if not str(path).startswith('/') else Path(path).read_text()


def code_of(path):
    """The executable lines of a shell script, with comments removed.

    Comment stripping is the whole point: these files document the mistakes they
    are guarding against, so prose must not be able to satisfy or defeat a check.
    """
    lines = []
    for line in read(str(path)).splitlines():
        stripped = line.split('#', 1)[0]
        if stripped.strip():
            lines.append(stripped)
    return '\n'.join(lines)


def commands_in(path):
    """Every external command the script invokes, by name.

    Looks in command position: start of a line after any assignment prefix, after
    a pipe or separator, and inside $( ).  Shell keywords and the scripts' own
    function names are filtered out, so what remains is what BusyBox has to
    provide.

    Two details make this usable rather than noisy, and both were learned by
    running it against the real scripts:

    * `VAR=$(cmd)` is the common form here, and a naive scan reports the VARIABLE
      as the command - GTS9_MINIMAL_BOOT_ID, GTS9_MINIMAL_CMDLINE and a dozen
      others.  Leading assignments are stripped, including the `NAME=$(...)` form,
      so only the command inside the substitution survives.
    * a surviving ALL-CAPS token is still never a BusyBox applet, so those are
      dropped too.  That is a convention rather than a proof, which is why the
      test using this also asserts the declared list contains no debug-only
      tools: together, the two checks make an accidental omission visible from
      either side.
    """
    text = code_of(path)
    funcs = set(re.findall(r'^\s*([A-Za-z_][A-Za-z0-9_]*)\s*\(\)', text, re.M))
    keywords = set('''if then else elif fi for while until do done case esac in
        return break continue local export readonly set unset shift trap eval exec
        time true false'''.split())

    found = set()

    def consider(fragment):
        # Strip a chain of leading assignments (NAME=value, NAME="value",
        # NAME=$(subst), NAME=${var:-default}), then take the next word.
        stripped = re.sub(
            r'^\s*(?:[A-Za-z_][A-Za-z0-9_]*='
            r'(?:"[^"]*"|\'[^\']*\'|\$\([^()]*\)|\$\{[^}]*\}|[^\s;]*)\s+)+',
            '', fragment.lstrip())
        m = re.match(r'([A-Za-z_\[][A-Za-z0-9_.\-]*)', stripped)
        if not m:
            return
        name = m.group(1)
        if name in funcs or name in keywords:
            return
        if name.isupper():
            # A surviving all-caps token is a variable, not a program.
            return
        found.add(name)

    for line in text.splitlines():
        consider(line)
        for sub in re.split(r'[|;]|&&|\|\|', line):
            consider(sub)
        for sub in re.findall(r'\$\(([^()]*)\)', line):
            consider(sub)
    return found


class TheProductionBuilderExists(unittest.TestCase):
    def test_it_is_present_and_executable(self):
        self.assertTrue(PROD_BUILDER.is_file())
        self.assertTrue(PROD_BUILDER.stat().st_mode & 0o111)

    def test_it_installs_the_handoff_as_init(self):
        """No trampoline script, no branch on a token, no second stage."""
        text = read(str(PROD_BUILDER))
        self.assertIn('install -m 0755 "$init_src" "$tree/init"', text)
        self.assertNotIn('bringup-init.sh" "$tree/init', text)

    def test_it_refuses_modules_rather_than_ignoring_them(self):
        """A silently ignored --modules would ship an image with no modules."""
        text = read(str(PROD_BUILDER))
        self.assertIn('--modules) fail', text)
        self.assertIn('kernel modules live on the Debian root', text)

    def test_it_has_no_firmware_code_path_at_all(self):
        """Not "ignores firmware" - no code path can add a blob.

        Checked on the executable lines.  The header comment explains at length
        that firmware belongs on the Debian root and names /usr/lib/firmware while
        doing so, so a check over the whole file would flag the explanation as the
        capability - the same mistake this repository has already made once in the
        validator.
        """
        text = read(str(PROD_BUILDER))
        code = code_of(str(PROD_BUILDER))
        self.assertNotIn('--keyboard-firmware', code)
        self.assertNotIn('lib/firmware', code)
        # And the comment must still explain why, rather than the check having
        # been satisfied by deleting the explanation.
        self.assertIn('firmware', text)

    def test_the_shared_library_owns_the_pinned_busybox(self):
        for script in (PROD_BUILDER, DEBUG_BUILDER):
            with self.subTest(script=script.name):
                text = read(str(script))
                self.assertIn('lib/initramfs-common.sh', text)
                self.assertIn('gts9_obtain_busybox', text)
        lib = read(str(COMMON_LIB))
        # One pin, verified in one place, so the two images cannot drift.
        self.assertIn('busybox_bin_sha256=', lib)
        self.assertEqual(lib.count('busybox-static_1.36.1'), 1)


class TheHandoffWorksStandaloneAsInit(unittest.TestCase):
    """The bug this exists for: /proc must be mounted before cmdline is read.

    As a branch of bringup-init.sh the script could assume procfs existed. As
    /init it cannot, and a `for arg in $(cat /proc/cmdline)` over a failed read is
    not an error - it silently drops every gts9_* option, so gts9_rootfs= would be
    ignored and the built-in default used with no diagnostic.
    """

    def test_proc_is_mounted_before_cmdline_is_parsed(self):
        text = read(str(INIT))
        mount_at = text.index('mount -t proc proc /proc')
        parse_at = text.index('for arg in $(cat /proc/cmdline')
        self.assertLess(mount_at, parse_at,
                        '/proc must be mounted before /proc/cmdline is read')

    def test_the_proc_mount_does_not_depend_on_proc_mounts(self):
        """mount_pseudo_if_missing reads /proc/mounts - the file that is missing."""
        text = read(str(INIT))
        proc_mount = text[text.index('mount -t proc proc /proc') - 600:
                          text.index('for arg in $(cat /proc/cmdline')]
        self.assertNotIn('mount_pseudo_if_missing proc', proc_mount)

    def test_a_failed_proc_mount_is_reported_not_ignored(self):
        text = read(str(INIT))
        self.assertIn('/proc/cmdline is unreadable', text)

    def test_the_other_pseudo_filesystems_follow(self):
        text = read(str(INIT))
        parse_at = text.index('for arg in $(cat /proc/cmdline')
        for fs in ('sysfs sysfs /sys', 'devtmpfs devtmpfs /dev', 'tmpfs tmpfs /run'):
            with self.subTest(fs=fs):
                self.assertGreater(text.index(fs), parse_at)

    def test_the_ordering_is_documented(self):
        """A future edit must be able to see why the order matters."""
        text = read(str(INIT))
        self.assertIn('1. PATH', text)
        self.assertIn('2. mount /proc', text)
        self.assertIn('3. parse /proc/cmdline', text)


class TheTrampolineIsOptIn(unittest.TestCase):
    def test_default_path_does_not_stage_it(self):
        text = read(str(INIT))
        staging = text[text.index('cp /sbin/gts9-minimal-pid1'):
                       text.index('Run the staged trampoline')]
        # The copies must be inside a conditional on MINIMAL_INIT.
        guard = text.rindex('if [ "$MINIMAL_INIT" = /run/gts9-minimal-pid1 ]',
                           0, text.index('cp /sbin/gts9-minimal-pid1'))
        self.assertLess(guard, text.index('cp /sbin/gts9-minimal-pid1'))
        self.assertIn('fi', staging)

    def test_a_staging_failure_falls_back_instead_of_aborting(self):
        """Staging was fatal; an experiment failing to stage is not a boot failure."""
        text = read(str(INIT))
        block = text[text.index('cp /sbin/gts9-minimal-pid1'):
                     text.index('Run the staged trampoline')]
        self.assertIn('MINIMAL_INIT=/sbin/init', block)
        self.assertNotIn('minimal_fail switch-root-returned', block)

    def test_the_production_builder_only_ships_it_on_request(self):
        text = read(str(PROD_BUILDER))
        self.assertIn('--with-trampoline', text)
        self.assertIn('with_trampoline=${MINIMAL_WITH_TRAMPOLINE:-0}', text)
        # The build of the helper sits under the opt-in branch.
        self.assertLess(text.index('if [ "$with_trampoline" = 1 ]'),
                        text.index('gts9-minimal-pid1.c"'))

    def test_the_source_is_not_deleted(self):
        """Retired from production is not the same as removed."""
        self.assertTrue((ROOT / 'boot/gts9-minimal-pid1.c').is_file())
        self.assertTrue((ROOT / 'boot/minimal-rootfs-init.sh').is_file())


class ProductionInitExecutesNothingDebugOnly(unittest.TestCase):
    """Every capability the production handoff must not have."""

    FORBIDDEN = [
        (r'usb_gadget', 'create a configfs USB gadget'),
        (r'mass_storage', 'set up USB mass storage'),
        (r'/dev/disk/by-partlabel|PARTNAME', 'parse the GPT partition table'),
        (r'/dev/rtc|hwclock', 'read RTC telemetry'),
        (r'boot-recovery', 'write the bootloader control block'),
        (r'fb0/blank|display_recover', 'do display recovery'),
        (r'regulator_summary|devices_deferred', 'dump hardware state'),
        (r'dmesg', 'read the kernel log'),
        (r'ttyGS', 'use a USB serial port'),
        (r'\binsmod\b|\bmodprobe\b', 'load a kernel module'),
        (r'\bnc\b|wpa_supplicant|udhcpc|dhcpcd', 'configure the network'),
        (r'\bsshd\b|\bssh\b', 'configure SSH'),
        (r'\bwatchdog\b', 'arm a hardware watchdog'),
    ]

    def test_none_of_them_appear_in_the_production_init(self):
        code = code_of(str(INIT))
        for pattern, label in self.FORBIDDEN:
            with self.subTest(capability=label):
                self.assertIsNone(re.search(pattern, code),
                                  f'production /init must not {label}')

    def test_the_production_state_library_is_also_clean(self):
        code = code_of(str(STATE))
        for pattern, label in self.FORBIDDEN:
            with self.subTest(capability=label):
                self.assertIsNone(re.search(pattern, code),
                                  f'production state library must not {label}')

    def test_the_keep_list_is_present(self):
        """What production MUST do, asserted so a cleanup cannot remove it."""
        text = read(str(INIT))
        for needed in ('mount -t proc proc /proc',
                       'mount -t ext4',
                       '/newroot/sbin/init',
                       'mount --move',
                       'switch_root',
                       'minimal_state_stage'):
            with self.subTest(needed=needed):
                self.assertIn(needed, text)


class ProductionAppletsMatchWhatItRuns(unittest.TestCase):
    """A production script must not call a tool the image does not install.

    The production image installs only the applets its scripts use, so a command
    that creeps into the handoff without being added to the list would fail at the
    worst possible moment - between mounting the root and handing over to PID 1.
    """

    # Shell builtins and the scripts' own functions: not BusyBox applets.
    BUILTINS = set('''. : [ alias bg break cd command continue echo eval exec exit
        export false fc fg getopts hash jobs kill let local printf pwd read readonly
        return set shift test times trap true type ulimit umask unalias unset wait
        if then else elif fi for while until do done case esac in function
        minimal_emit minimal_fail minimal_state_init minimal_state_stage
        minimal_state_fail minimal_state_write minimal_state_persist_enable
        minimal_state_freeze_facts minimal_state_now minimal_state_uptime
        minimal_state_boot_id minimal_state_kernel_release minimal_state_cmdline
        minimal_state_mmc_devices minimal_rescue_shell mount_pseudo_if_missing
        minimal_state_stage_timing minimal_state_boot_id_value
        minimal_state_kernel_value minimal_state_cmdline_value minimal_state_mmc_value
        minimal_message minimal_state_dir minimal_mmc_devices minimal_mmc_hosts
        minimal_state_tmp minimal_mmc_value'''.split())

    def test_every_command_it_runs_is_in_the_declared_applet_list(self):
        declared = set()
        text = read(str(PROD_BUILDER))
        m = re.search(r"required_applets='([^']*)'", text)
        self.assertIsNotNone(m, 'the production builder declares no applet list')
        declared.update(m.group(1).split())
        m2 = re.search(r"sbin_applets='([^']*)'", text)
        if m2:
            declared.update(m2.group(1).split())

        used = set()
        for path in (INIT, STATE):
            used |= commands_in(str(path))

        # Drop builtins, the scripts' own functions, variable names that the
        # command-position scan cannot tell from commands, and absolute paths.
        noise = re.compile(r'^[A-Z_][A-Z0-9_]*$|^\$|^[a-z_]+$')
        unknown = set()
        for name in used:
            if name in self.BUILTINS or name in declared:
                continue
            if name in ('sh',):
                continue
            # A bare lowercase word that is not a declared applet and not a
            # builtin is either a real missing tool or prose the scan picked up.
            # Report it, and let the allowlist below name the known prose cases.
            unknown.add(name)

        prose = {'boot', 'case', 'continue', 'do', 'done', 'elif', 'else', 'esac',
                 'fi', 'for', 'found', 'if', 'in', 'inspect', 'it', 'kernel',
                 'losing', 'never', 'nothing', 'opportunistically', 'sourcing',
                 'the', 'then', 'type', 'waited', 'waiting', 'while', 'with',
                 'without', 'error', 'record', 'state', 'root', 'device', 'mount',
                 'minimal', 'pseudo_type', 'pseudo_source', 'pseudo_target',
                 'vfs', 'arg', 'line', 'dir', 'file', 'mode', 'msg', 'step'}
        missing = sorted(unknown - prose)
        self.assertEqual(missing, [],
                         f'production scripts run commands not in the applet list: {missing}')

    def test_the_list_has_no_debug_only_tools(self):
        text = read(str(PROD_BUILDER))
        m = re.search(r"required_applets='([^']*)'", text)
        declared = m.group(1).split()
        for tool in ('dd', 'od', 'awk', 'sed', 'sha256sum', 'dmesg', 'hwclock',
                     'find', 'setsid', 'chvt', 'insmod', 'modprobe'):
            with self.subTest(tool=tool):
                self.assertNotIn(tool, declared)

    def test_the_rescue_shell_can_be_left(self):
        """A rescue shell with no way out is a trap.

        Found on the device, not by reading the script: with
        gts9_rootfs=/dev/does-not-exist the handoff stops in the rescue shell, and
        the first production image had no `reboot` applet - so leaving it needed a
        physical key combination, while the image has no network and no serial
        port to use instead. The escape hatch is now part of the applet list, and
        it is deliberately the ONLY thing from the debug escape set that is.
        """
        text = read(str(PROD_BUILDER))
        declared = re.search(r"required_applets='([^']*)'", text).group(1).split()
        self.assertIn('reboot', declared)
        self.assertIn('poweroff', declared)
        # ... and they must be reachable as commands, not just declared: /sbin is
        # on the handoff's PATH.
        sbin = re.search(r"sbin_applets='([^']*)'", text).group(1).split()
        self.assertIn('reboot', sbin)
        self.assertIn('poweroff', sbin)
        self.assertIn('/sbin', read(str(INIT)).split('PATH=')[1].split('\n')[0])

    def test_the_rescue_message_says_there_is_no_network(self):
        """An owner must not go looking for ssh or a COM port that cannot exist."""
        text = read(str(INIT))
        self.assertIn('network may not be available before Debian starts', text)
        self.assertIn('tty1 or offline TWRP inspection', text)

    def test_the_rescue_shell_never_waits_for_a_serial_port(self):
        code = code_of(str(INIT))
        self.assertNotIn('ttyGS', code)
        # It waits only on an interactive shell (which blocks) or a sleep.
        rescue = code[code.index('minimal_rescue_shell()'):]
        rescue = rescue[:rescue.index('\n}')]
        self.assertIn('sleep 5', rescue)
        self.assertNotIn('while [ ! -c /dev/ttyGS', rescue)


class TheDebugImageKeepsItsCapabilities(unittest.TestCase):
    def test_the_debug_builder_still_installs_the_bringup_init(self):
        text = read(str(DEBUG_BUILDER))
        self.assertIn('install -m 0755 "$init_src" "$tree/init"', text)

    def test_it_still_stages_the_minimal_pair_for_the_legacy_profile(self):
        """The debug image can still be asked for the old minimal rootfs boot."""
        text = read(str(DEBUG_BUILDER))
        self.assertIn('minimal-rootfs-init', text)
        self.assertIn('minimal-rootfs-state.sh', text)

    def test_the_msc_evidence_channel_survives(self):
        code = code_of(str(BRINGUP))
        self.assertIn('mass_storage.usb0', code)

    def test_firmware_is_an_allowlist_not_a_directory_copy(self):
        text = read(str(DEBUG_BUILDER))
        self.assertNotIn('cp -a "$fw_src"/.', text)
        self.assertNotIn('cp -a "$repo_root/.work/firmware"', text)
        self.assertIn('--keyboard-firmware', text)
        self.assertIn('firmware_allowlist_dest=', text)

    def test_the_no_serial_invariant_survives_in_the_debug_init(self):
        code = code_of(str(BRINGUP))
        self.assertNotIn('mkdir -p "$G/functions/acm', code)
        self.assertNotIn('mkdir -p "$G/functions/gser', code)

    def test_the_debug_builder_does_not_stage_arbitrary_firmware(self):
        """Regression guard: this used to copy .work/firmware wholesale.

        Checked on the executable lines, because the comment above the allowlist
        quotes the old `cp -a .work/firmware/.` to explain what changed.
        """
        code = code_of(str(DEBUG_BUILDER))
        self.assertNotRegex(code, r'cp -a.*firmware/\.',
                            'firmware must be copied by name, never as a tree')
        self.assertIn('install -m 0644 "$keyboard_firmware"', code)


class TheAuditScriptIsUsable(unittest.TestCase):
    def test_it_exists_and_is_executable(self):
        self.assertTrue(AUDIT.is_file())
        self.assertTrue(AUDIT.stat().st_mode & 0o111)

    def test_it_reports_the_three_classifications(self):
        text = read(str(AUDIT))
        for kind in ('production_required', 'debug_only', 'currently_unreferenced'):
            with self.subTest(kind=kind):
                self.assertIn(kind, text)

    def test_its_reference_scanner_is_not_the_substring_bug(self):
        """Plain grep for a filename matched `init` inside `minimal_state_init`."""
        text = read(str(AUDIT))
        self.assertIn('mentions()', text)
        # The pattern must require a reference context, not a bare substring.
        self.assertNotRegex(text, r'grep -l -- "\$name"',
                            'a plain substring grep classifies nearly everything as referenced')

    def test_no_pattern_uses_the_broken_not_newline_class(self):
        """`[^\\n]` in POSIX ERE is a bracket set holding backslash and 'n'.

        It does not mean "not a newline", so `mkdir[^\\n]*usb_gadget` matched
        nothing and the gadget rule was silently inert in the validator, the shared
        library and the audit script.  Each of those was a false PASS.
        """
        for path in (AUDIT, COMMON_LIB, VALIDATOR):
            with self.subTest(script=path.name):
                self.assertNotIn(r'[^\n]', read(str(path)),
                                 'use . rather than [^\\n] in a per-line grep')


class TheValidatorEnforcesTheBoundary(unittest.TestCase):
    def test_it_reads_the_profile_from_content_not_the_filename(self):
        text = read(str(VALIDATOR))
        self.assertIn('init_profile=', text)
        self.assertIn('manifest declares profile=', text)
        # The decision must come from the extracted /init.
        self.assertIn('minimal_state_stage', text)
        self.assertIn('setup_usb_gadget', text)

    def test_it_strips_comments_before_the_execution_rules(self):
        """The debug script's explanations must not read as capabilities."""
        text = read(str(VALIDATOR))
        self.assertIn("sed 's/#.*//'", text)

    def test_it_forbids_the_production_capabilities(self):
        text = read(str(VALIDATOR))
        for label in ('create a configfs USB gadget', 'parse the GPT partition table',
                      'read RTC telemetry', 'write the bootloader control block',
                      'do display recovery', 'use a USB serial port',
                      'load a kernel module'):
            with self.subTest(label=label):
                self.assertIn(label, text)

    def test_it_allows_them_in_the_debug_profile(self):
        text = read(str(VALIDATOR))
        self.assertIn('debug image keeps its diagnostics by design', text)

    def test_it_still_requires_the_no_serial_invariant_in_debug(self):
        text = read(str(VALIDATOR))
        self.assertIn('creates no serial gadget function', text)

    def test_the_bundle_carries_the_manifest(self):
        text = read('scripts/build-boot-bundle.sh')
        self.assertIn('initramfs.manifest', text)


class TheExistingInvariantsAreUntouched(unittest.TestCase):
    """This work must not disturb what earlier rounds established."""

    PROFILES = sorted((ROOT / 'boot').glob('cmdline*.txt'))

    def test_every_profile_still_disables_systemd_automatic_ssh(self):
        for path in self.PROFILES:
            with self.subTest(cmdline=path.name):
                self.assertIn('systemd.ssh_auto=no', path.read_text())

    def test_the_console_is_still_only_tty0(self):
        for path in self.PROFILES:
            with self.subTest(cmdline=path.name):
                toks = path.read_text().replace('\n', ' ').split()
                self.assertEqual([t for t in toks if t.startswith('console=')],
                                 ['console=tty0'])

    def test_no_serial_console_came_back(self):
        for path in self.PROFILES:
            with self.subTest(cmdline=path.name):
                text = path.read_text()
                for gone in ('console=ttyGS0', 'console=ttyGS1',
                             'console=ttyMSM0', 'earlycon'):
                    self.assertNotIn(gone, text)

    def test_the_kernel_fragment_still_pins_the_serial_gadget_off(self):
        text = read('kernel/config/gts9wifi-mainline.fragment')
        for symbol in ('CONFIG_USB_CONFIGFS_ACM is not set',
                       'CONFIG_USB_CONFIGFS_SERIAL is not set',
                       'CONFIG_U_SERIAL_CONSOLE is not set'):
            with self.subTest(symbol=symbol):
                self.assertIn('# ' + symbol, text)

    def test_the_ssh_management_path_is_intact(self):
        self.assertTrue((ROOT / 'rootfs-overlay/etc/gts9-usb-net').is_file())
        text = read('rootfs-overlay/usr/libexec/gts9-usb-acm')
        self.assertIn('ncm', text)
        self.assertNotIn('mkdir -p "$GADGET/functions/acm', text)


if __name__ == '__main__':
    unittest.main()
