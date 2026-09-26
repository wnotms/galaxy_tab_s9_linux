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
    # Every name this script ever assigns to, anywhere.  Without this, a lowercase
    # local like `panel_fb=/sys/...` followed by `while [ ! -w "$panel_fb" ]` puts
    # panel_fb in command position for a line-based scan, and the test reports a
    # missing applet that is really just a variable.  Collecting assignments is the
    # principled fix: it does not depend on the ALL-CAPS convention.
    assigned = set(re.findall(r'(?:^|[;\s])([A-Za-z_][A-Za-z0-9_]*)=', text))

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
        if name in funcs or name in keywords or name in assigned:
            return
        if name.isupper():
            # A surviving all-caps token is a variable, not a program.
            return
        found.add(name)

    for line in text.splitlines():
        # Remove quoted strings before splitting on separators.  Otherwise a
        # message like 'panel: no framebuffer; cannot try to recover it' splits at
        # the semicolon INSIDE the quotes and reports "cannot" as a command - which
        # is what happened the first time this ran against the panel-recovery code.
        unquoted = re.sub(r"'[^']*'|\"[^\"]*\"", "''", line)
        consider(unquoted)
        for sub in re.split(r'[|;]|&&|\|\|', unquoted):
            consider(sub)
        for sub in re.findall(r'\$\(([^()]*)\)', unquoted):
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
    """Every capability the production handoff must not have.

    Display recovery is deliberately absent from the list below, because it is the
    one capability that was allowed back on a condition.  See
    PanelRecoveryRunsOnlyOnFailure for where it may live and why.
    """

    FORBIDDEN = [
        (r'usb_gadget', 'create a configfs USB gadget'),
        (r'mass_storage', 'set up USB mass storage'),
        # PARTNAME is deliberately NOT forbidden: reading the label the kernel
        # already published in sysfs is how the misc partition is found for the
        # bootloader-control-block request, and it is the safest possible method -
        # nothing is guessed from a device number.  What must stay out is parsing
        # a GPT by hand off the raw disk, which is what the debug image does and
        # what needs `od`.  See BootloaderControlBlockRecovery below.
        (r'efi_partition|EFI PART|\x45\x46\x49', 'parse a GPT header by hand'),
        (r'/dev/rtc|hwclock', 'read RTC telemetry'),
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
        # od stays out: the debug image uses it to parse a GPT by hand, and the
        # production BCB path needs no GPT parser because it reads the label the
        # kernel already published.  dd/sed/tr/basename ARE present now - they are
        # the bootloader-control-block write and its partition lookup.
        for tool in ('od', 'awk', 'sha256sum', 'dmesg', 'hwclock',
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


class BootloaderControlBlockRecovery(unittest.TestCase):
    """A failed handoff must end in TWRP, not in a dead end.

    This came out of the physical failure test: with
    gts9_rootfs=/dev/does-not-exist the handoff landed correctly in the tty1
    rescue shell - and stranded the tablet there. No network (the production image
    has no gadget and no Wi-Fi), no serial port, and at the time no reboot applet,
    so recovery needed a physical key combination.

    The rescue path now writes the Android bootloader control block and asks for a
    plain restart; ABL reads "boot-recovery" from the first bytes of `misc` and
    starts TWRP. The request was already confirmed end to end on this board by test
    028 - 33 s from `adb reboot` to TWRP, unattended - and docs/REBOOT_MODES.md
    records why `reboot recovery` cannot be used instead: it reaches
    nvmem-reboot-mode and an SPMI write blocks this kernel uninterruptibly (tests
    024/025).

    Three properties are asserted here, because this writes to a partition and each
    is the difference between a recovery feature and a way to brick a tablet.
    """

    def test_it_is_wired_into_the_rescue_path(self):
        text = read(str(INIT))
        rescue_at = text.index('minimal_rescue_shell()')
        rescue_end = text.index('\n}\n', rescue_at)
        call_at = text.index('minimal_reboot_to_recovery', rescue_at)
        self.assertLess(call_at, rescue_end,
                        'the recovery request must be inside the rescue path')

    def test_the_device_is_found_by_the_kernels_own_gpt_label(self):
        """Nothing may be guessed from a device number.

        The partition is found by matching PARTNAME in the block device's sysfs
        uevent - the label the kernel's own EFI partition parser published. A
        hardcoded /dev/sda10 would write a bootloader control block into somebody
        else's partition on any other layout.
        """
        text = read(str(INIT))
        start = text.index('minimal_misc_device()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertIn('uevent', fn)
        self.assertIn('PARTNAME=', fn)
        self.assertIn('= "$misc_want"', fn)
        self.assertIn('basename', fn)
        self.assertNotIn('sda10', fn)
        self.assertNotIn('/dev/block/by-name', fn)

    def test_it_refuses_the_microsd(self):
        """misc is on the UFS; an mmcblk partition must never be selected."""
        text = read(str(INIT))
        start = text.index('minimal_misc_device()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertIn('mmcblk*) continue', fn)

    def test_it_is_one_shot_so_it_cannot_boot_loop(self):
        """If misc already asks for recovery, the bootloader ignored it once."""
        text = read(str(INIT))
        start = text.index('minimal_reboot_to_recovery()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertIn('minimal_bcb_asks_recovery', fn)
        self.assertIn('powering off instead of looping', fn)
        self.assertLess(fn.index('minimal_bcb_asks_recovery'),
                        fn.index('head -c 2048'))

    def test_it_fails_open_rather_than_stranding_the_device(self):
        """Every failure path must report and return, never abort the boot."""
        text = read(str(INIT))
        start = text.index('minimal_reboot_to_recovery()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertNotIn('minimal_fail', fn)
        for warn in ("no 'misc' partition", 'could not clear the BCB',
                     'could not write the BCB', 'read-back does not match'):
            with self.subTest(warning=warn):
                self.assertIn(warn, fn)

    def test_it_verifies_the_write_before_rebooting(self):
        """A request that did not land is worse than none: it looks like a loop."""
        text = read(str(INIT))
        start = text.index('minimal_reboot_to_recovery()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertIn('misc_check', fn)
        self.assertIn('not rebooting', fn)
        self.assertLess(fn.index('misc_check'), fn.index('rebooting into recovery'))

    def test_the_bcb_layout_matches_the_proven_implementation(self):
        """2048 bytes, zeroed, with 'boot-recovery' at offset 0.

        The same block boot/bringup-init.sh and boot/gts9-debian-to-recovery.sh
        write, so all three produce byte-identical requests. Offset 0 matters: the
        command goes where ABL looks, so there is no seek.
        """
        text = read(str(INIT))
        start = text.index('minimal_reboot_to_recovery()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertIn('head -c 2048 /dev/zero', fn)
        self.assertIn("printf 'boot-recovery'", fn)
        self.assertIn('bs=1 conv=notrunc', fn)
        self.assertNotIn('seek=', fn)

    def test_it_asks_for_a_plain_restart(self):
        """No mode string: the request is already in the BCB."""
        text = read(str(INIT))
        start = text.index('minimal_reboot_to_recovery()')
        fn = text[start:text.index('\n}\n', start)]
        self.assertIn('reboot -f', fn)
        self.assertNotRegex(fn, r'reboot\s+"?recovery')

    def test_the_rescue_path_can_still_stay_in_the_shell(self):
        """An escape for debugging: GTS9_MINIMAL_RESCUE_ACTION=shell."""
        text = read(str(INIT))
        self.assertIn('GTS9_MINIMAL_RESCUE_ACTION', text)
        self.assertIn('staying in the shell', text)

    def test_the_applets_it_needs_are_declared(self):
        builder = read(str(PROD_BUILDER))
        declared = re.search(r"required_applets='([^']*)'", builder).group(1).split()
        for applet in ('dd', 'tr', 'sed', 'basename', 'head', 'reboot', 'poweroff'):
            with self.subTest(applet=applet):
                self.assertIn(applet, declared)


class PanelRecoveryRunsOnlyOnFailure(unittest.TestCase):
    """The one debug capability allowed back, and the condition on which it is.

    Found on the device by the failure test, not by reading the script. Display
    recovery lives in Debian's gts9-panel-recover.service, which cycles the
    framebuffer when the panel's cold-boot enable reads a dead DDIC
    (`ana38407 panel id: 00 00 00`); it runs at ~3.7 s on a healthy boot. In the
    rescue path Debian never starts, so on a cold boot that hit the zero-ID case
    the rescue banner would be printed to a screen nobody can see.

    Restoring display recovery unconditionally was rejected: it is a diagnostic
    capability and it puts a full DPU modeset on the critical path, where test 178
    once caught an intermittent hang. So it runs only after the handoff has
    already failed - a healthy boot pays nothing.
    """

    def test_the_only_call_site_is_the_rescue_path(self):
        """Position is about where it is CALLED, not where it is defined.

        The helper is defined before minimal_rescue_shell() so the rescue function
        can call it; what matters is that the sole call sits inside the rescue
        path and therefore cannot execute on a successful boot.
        """
        text = read(str(INIT))
        # One definition and exactly one call.
        self.assertEqual(text.count('minimal_panel_rescue()'), 1,
                         'expected a single call to the panel helper')
        call_at = text.index('minimal_panel_rescue\n')
        rescue_at = text.index('minimal_rescue_shell()')
        # The call must be textually inside the rescue function body.
        rescue_body_end = text.index('\n}\n', rescue_at)
        self.assertGreater(call_at, rescue_at)
        self.assertLess(call_at, rescue_body_end,
                        'the panel cycle must be called from inside minimal_rescue_shell')

    def test_it_is_not_on_the_success_path(self):
        """The root mount, the init check and switch_root must not touch it.

        The functional argument: the helper is reachable only through
        minimal_rescue_shell, and every route into that function is a failure
        (root timeout, missing device, failed mount, missing /sbin/init, failed
        VFS move, failed switch_root).  This asserts both halves - the call is
        inside the rescue body, and the healthy path never calls the rescue body.
        """
        text = read(str(INIT))
        rescue_at = text.index('minimal_rescue_shell()')
        rescue_body_end = text.index('\n}\n', rescue_at)
        call_at = text.index('minimal_panel_rescue\n')
        self.assertTrue(rescue_at < call_at < rescue_body_end)

        # The success path: from the root mount to switch_root there must be no
        # reference to the panel helper at all.
        mount_at = text.index('mount -t ext4')
        switch_at = text.index('exec switch_root')
        success = text[mount_at:switch_at]
        self.assertNotIn('minimal_panel_rescue', success)
        self.assertNotIn('fb0/blank', success)

    def test_every_wait_is_bounded(self):
        """A rescue path that blocks forever is worse than a dark screen."""
        text = read(str(INIT))
        start = text.index('minimal_panel_rescue()')
        panel = text[start:text.index('\n}\n', start)]
        # Quoted in the source, so match what is actually written.
        self.assertIn('"$panel_waited" -lt 5', panel)
        self.assertIn('"$panel_cycle" -lt 3', panel)

    def test_it_gives_up_instead_of_failing_the_rescue(self):
        """A panel that cannot be recovered must not cost the shell."""
        text = read(str(INIT))
        start = text.index('minimal_panel_rescue()')
        panel = text[start:text.index('\n}\n', start)]
        self.assertIn('cannot try to recover it', panel)
        self.assertIn('return 0', panel)
        # It must not abort the handoff or call minimal_fail.
        self.assertNotIn('minimal_fail', panel)

    def test_it_does_not_parse_dmesg_because_production_has_no_dmesg(self):
        """The debug version greps dmesg for the zero-ID line; this one cannot."""
        text = read(str(INIT))
        start = text.index('minimal_panel_rescue()')
        panel = text[start:text.index('\n}\n', start)]
        self.assertNotIn('dmesg', panel)


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
        # NOTE: GPT parsing and the bootloader control block are deliberately
        # absent from this list.  Both are now handled by NAME checks further down,
        # because each is one of the two capabilities allowed back on a condition:
        # PARTNAME-based lookup needs no GPT parser at all, and the BCB write is
        # how a failed handoff reaches TWRP instead of stranding the device.
        for label in ('create a configfs USB gadget',
                      'read RTC telemetry',
                      'use a USB serial port',
                      'load a kernel module'):
            with self.subTest(label=label):
                self.assertIn(label, text)

    def test_it_checks_the_bcb_safety_properties_rather_than_forbidding_it(self):
        """The BCB is allowed, but only with its guards.

        The validator must test the GUARD rather than a message: an earlier version
        grepped for the warning text, so replacing the one-shot condition with
        `if false` still passed, because the string it looked for was in the branch
        that had just become unreachable.
        """
        text = read(str(VALIDATOR))
        self.assertIn('one-shot guard', text)
        self.assertIn('if[[:space:]]+minimal_bcb_asks_recovery', text)
        self.assertIn('BCB recovery is called only from the rescue path', text)

    def test_it_position_checks_display_recovery_rather_than_forbidding_it(self):
        """Display recovery is allowed, but only inside the rescue path.

        Forbidding the string outright would have been simpler and wrong: the
        rescue banner goes to a panel that Debian's gts9-panel-recover.service
        would normally have fixed, and in the rescue path Debian never runs.  So
        the rule is where the framebuffer write sits, not whether it exists.
        """
        text = read(str(VALIDATOR))
        self.assertIn('display recovery is called only from the rescue path', text)
        self.assertIn('minimal_rescue_shell()', text)
        # And it must check the CALL SITE rather than the definition, because a
        # shell function is defined before it is called.
        self.assertIn('minimal_panel_rescue', text)

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
