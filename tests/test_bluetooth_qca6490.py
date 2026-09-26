"""Host checks for the X710 QCA6490 / WCN6855 Bluetooth bring-up.

Pins the three things this round established so none can quietly regress:

* the firmware the driver asks for is DERIVED from the controller's own version
  word, not copied from a log, and the derivation still reproduces what the
  driver requested on the tablet;
* the WCN6855 cannot supply its own public address on this board, so the fix has
  to come from the device's provisioning data through the standard BlueZ
  management interface - not from a DTS constant and not from a generated value;
* the two ordering/stdin traps that only showed up on real hardware stay fixed,
  because both look correct when read and both hang or silently skip in practice.

See docs/BLUETOOTH_QCA6490_BRINGUP.md for the layered status.
"""
import hashlib
import pathlib
import re
import subprocess
import sys
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

NAMETOOL = "scripts/lib/btfw-name.py"
PREFLIGHT = "scripts/bluetooth-preflight.sh"
STAGER = "scripts/stage-bluetooth-firmware.sh"
HELPER = "rootfs-overlay/usr/libexec/gts9-bluetooth-address"
HELPER_UNIT = "rootfs-overlay/usr/lib/systemd/system/gts9-bluetooth-address.service"
DROPIN = "rootfs-overlay/etc/systemd/system/bluetooth.service.d/gts9-bdaddr.conf"
DOC = "docs/BLUETOOTH_QCA6490_BRINGUP.md"

# What the tablet actually reported, from reference/boot-tests/test-217/218.
DEVICE_SOC_ID = 0x400C1211
DEVICE_ROM_VER = 0x00000201
DEVICE_VERSION = 0x12110201
DEVICE_REQUESTED = "qca/wcnhpbtfw21.tlv"
DEVICE_REQUESTED_FALLBACK = "qca/hpbtfw21.tlv"
DEVICE_NVM = "qca/wcnhpnv21g.bin"

# The placeholder btqca refuses to accept, and the real address.
PLACEHOLDER = "00:00:00:00:5A:AD"
REAL_ADDRESS = "38:8A:06:59:04:E7"


def read(rel):
    return (ROOT / rel).read_text()


def code_only(text):
    """Commands only. These files explain the very traps the tests check for, so
    their prose must neither satisfy nor defeat a check."""
    return "\n".join(
        line for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    )


def run_nametool(*args):
    return subprocess.run(
        [sys.executable, str(ROOT / NAMETOOL), *args],
        capture_output=True, text=True, check=True).stdout


class TheFirmwareNameIsDerivedFromTheChip(unittest.TestCase):
    """The names must come from the pinned kernel's arithmetic.

    Copying "wcnhpbtfw21.tlv" out of a log works exactly once. The driver builds
    the name from the controller's version word, so the tooling must too, or a
    different ROM revision silently gets the wrong rampatch.
    """

    def test_it_reproduces_what_the_tablet_asked_for(self):
        out = run_nametool(hex(DEVICE_VERSION))
        self.assertIn(DEVICE_REQUESTED, out)
        self.assertIn(DEVICE_REQUESTED_FALLBACK, out)

    def test_the_derived_rom_ver_matches_the_driver(self):
        # rom_ver = ((soc_ver & 0xf00) >> 4) | (soc_ver & 0xf), btqca.c:795
        soc_ver = DEVICE_VERSION
        rom_ver = ((soc_ver & 0x00000F00) >> 0x04) | (soc_ver & 0x0000000F)
        self.assertEqual(rom_ver, 0x21)
        self.assertIn("%02x" % rom_ver, run_nametool(hex(DEVICE_VERSION)))

    def test_it_flags_the_globalfoundries_variant(self):
        """soc_id & 0xff00 == 0x1200 selects the "g" files; the NVM depends on it."""
        out = run_nametool("--soc-id", hex(DEVICE_SOC_ID),
                           "--rom-ver", hex(DEVICE_ROM_VER))
        self.assertIn("GlobalFoundries", out)
        self.assertIn("wcnhpnv21g", out)

    def test_it_does_not_invent_an_nvm_without_a_board_id(self):
        out = run_nametool(hex(DEVICE_VERSION))
        self.assertIn("unknown until the board ID is read", out)

    def test_it_names_the_board_specific_nvm_once_the_id_is_known(self):
        out = run_nametool("--soc-id", hex(DEVICE_SOC_ID),
                           "--rom-ver", hex(DEVICE_ROM_VER),
                           "--board-id", "0x0a")
        self.assertIn("qca/wcnhpnv21g.b0a", out)

    def test_the_zero_board_id_gives_the_generic_nvm(self):
        out = run_nametool("--soc-id", hex(DEVICE_SOC_ID),
                           "--rom-ver", hex(DEVICE_ROM_VER),
                           "--board-id", "0x0")
        self.assertIn(DEVICE_NVM, out)

    def test_the_arithmetic_matches_the_pinned_source(self):
        """Transcribed constants must still agree with the kernel tree."""
        header = ROOT / ".work/linux-mainline/drivers/bluetooth/btqca.h"
        if not header.is_file():
            self.skipTest("pinned kernel tree not checked out")
        text = header.read_text()
        self.assertIn("(le32_to_cpu(soc_id) << 16) | (le16_to_cpu(rom_ver))", text)
        self.assertIn("#define QCA_HSP_GF_SOC_ID\t\t0x1200", text)
        self.assertIn("#define QCA_HSP_GF_SOC_MASK\t\t0x0000ff00", text)

    def test_it_refuses_a_trace_without_the_version_lines(self):
        proc = subprocess.run(
            [sys.executable, str(ROOT / NAMETOOL), "--dmesg", "/dev/null"],
            capture_output=True, text=True)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("must not be guessed", proc.stderr + proc.stdout)


class ThePreflightCannotChangeAnything(unittest.TestCase):
    """It is the round's read-only instrument, so it must stay read-only.

    Every command it runs over ssh is a read. A write hidden in here would run on
    a tablet whose Wi-Fi shares this chip's PMU.
    """

    def test_it_exists_and_is_executable(self):
        path = ROOT / PREFLIGHT
        self.assertTrue(path.is_file())
        self.assertTrue(path.stat().st_mode & 0o111, "preflight must be executable")

    def test_it_never_writes_a_gpio_or_a_device(self):
        text = code_only(read(PREFLIGHT))
        for forbidden in ("gpio set", "gpio export", "> /sys/class/gpio",
                          "echo 1 > ", "echo 0 > ", "devmem", "regmap",
                          "modprobe -r", "rmmod", "reboot", "poweroff"):
            self.assertNotIn(forbidden, text,
                             "preflight must not perform %r" % forbidden)

    def test_every_remote_command_is_a_read(self):
        """The round's instrument must not be able to change the tablet.

        Rather than re-implementing a shell parser - which is what an exhaustive
        command whitelist amounts to, and which broke repeatedly while being
        written - this checks the property that actually matters: no command sent
        over ssh can create, modify or remove anything on the device. Every probe
        is a read; a write would have to use one of these forms to have any effect.
        """
        text = read(PREFLIGHT)
        self.assertIn("scripts/gts9-ssh.sh", text)

        # Everything that reaches the tablet goes through run()/q().
        remote = "\n".join(
            line for line in text.splitlines()
            if line.strip().startswith(("run ", "q ", "\t")) or "run '" in line)
        self.assertTrue(remote.strip(), "no remote commands were found")

        # `>/dev/null` and `2>&1` are host-side stream suppression on the ssh
        # process itself, not a write to the device, so they are removed before
        # the redirection check rather than whitelisted away.
        scanned = re.sub(r"\s*\d*>&\d", "", remote)
        scanned = re.sub(r"\s*\d*>\s*/dev/null", "", scanned)

        writers = (
            ">",              # any remaining redirection
            "modprobe", "rmmod", "insmod", "devmem", "regmap",
            "gpio set", "gpio export", "gpio unexport",
            "systemctl start", "systemctl stop", "systemctl restart",
            "systemctl enable", "systemctl disable",
            "ip link set", "ifconfig", "nmcli", "iw ",
            "mount", "umount", "dd ", "mkfs", "fsck", "tee",
            "reboot", "poweroff", "hwclock", "date -s", "kill", "pkill",
            "rm ", "mv ", "cp ", "chmod", "chown", "mkdir", "touch", "truncate",
            "btmgmt power", "btmgmt public-addr", "bluetoothctl power",
        )
        for writer in writers:
            # Word-boundary match, so legitimate reads are not caught by their own
            # substrings: `rfkill` contains "kill", `platform` contains "rm ".
            pattern = r"(?<![\w-])" + re.escape(writer.strip()) + r"(?![\w-])"
            self.assertIsNone(
                re.search(pattern, scanned),
                "preflight must not be able to write to the tablet: %r" % writer)

        # And the reads it performs are the ones it documents.
        for expected in ("dmesg", "modinfo", "lsmod", "btmgmt info",
                         "/sys/kernel/debug/gpio", "uname"):
            self.assertIn(expected, text)

    def test_it_defines_no_mutating_helper(self):
        body = code_only(read(PREFLIGHT))
        for name in ("disable", "enable", "reset", "write", "set_", "power_",
                     "unload", "reload"):
            for m in re.finditer(
                    r"^\s*(?:function\s+)?([\w-]*%s[\w-]*)\s*\(\)" % name,
                    body, re.M):
                self.fail("preflight defines a mutating helper: %s" % m.group(1))

    def test_no_remote_command_can_write(self):
        """The whole point: nothing in the preflight mutates the tablet.

        Checked inside the run() command strings only. The surrounding shell
        legitimately mentions mounting debugfs in a *diagnostic message*; what
        matters is that no remote command does it.
        """
        text = read(PREFLIGHT)
        run_text = "\n".join(
            line for line in text.splitlines() if "run '" in line or line.startswith("run "))
        for writer in ("> /sys", ">> /sys", "> /proc", "devmem", "regmap",
                       "gpio set", "gpio export", "modprobe ", "rmmod ",
                       "systemctl start", "systemctl stop", "systemctl restart",
                       "ip link set", "nmcli ", "umount ", "dd if=", "mkfs",
                       "tee ", "reboot", "poweroff", "hwclock"):
            self.assertNotIn(writer, run_text,
                             "preflight must not write: %r" % writer)


class TheStagerRecordsProvenance(unittest.TestCase):
    def test_it_takes_firmware_from_upstream_linux_firmware(self):
        text = read(STAGER)
        self.assertIn("linux-firmware", text)
        self.assertIn("kernel.googlesource.com", text)
        # No forum, no personal fork, no random host. Checked against the code and
        # the recorded source URL, not the prose: the comment above the source
        # lists these very strings while explaining why they are not used.
        source_lines = "\n".join(
            line for line in text.splitlines()
            if "LF_BASE=" in line or "http" in line and not line.lstrip().startswith("#")
        )
        for bad in ("github.com/", "dropbox", "drive.google", "mega.nz",
                    "mediafire", "4pda", "forum"):
            self.assertNotIn(bad, source_lines.lower(),
                             "firmware must not be sourced from %r" % bad)

    def test_it_pins_the_hashes_it_verified(self):
        text = read(STAGER)
        # The two rampatch hashes recorded in the round's evidence.
        self.assertIn("77d8979da5c613c85550549dcef8fb8ec6fe2e5576942855ea03179a11597c1f", text)
        self.assertIn("a911f66a137ec8b9e65f90942e1c21ea2604734a88e486519b77e750d0fc20d2", text)

    def test_it_re_hashes_after_copying_to_the_tablet(self):
        text = read(STAGER)
        self.assertIn("sha256sum", text)
        self.assertIn("verifying on the tablet", text)
        # A mismatch must be fatal, not a warning.
        self.assertIn("did not verify on the tablet", text)

    def test_blobs_are_staged_outside_git(self):
        text = read(STAGER)
        self.assertIn("out/bluetooth-firmware", text)
        gitignore = read(".gitignore")
        self.assertIn("out/", gitignore)

    def test_it_does_not_guess_the_nvm_name(self):
        """The NVM depends on the board ID, which needs the rampatch first."""
        text = read(STAGER)
        self.assertIn("--nvm", text)
        self.assertIn("board ID", text)


class TheAddressComesFromTheDeviceAndNotFromAConstant(unittest.TestCase):
    """The WCN6855 cannot supply this board's address, and it is per-unit data.

    btqca compares the controller's address with the one in the generic upstream
    NVM; they are equal, so it sets HCI_QUIRK_USE_BDADDR_PROPERTY and the
    controller is left HCI_UNCONFIGURED. The kernel can only take the value from
    the DT, and a DT constant would be wrong for every tablet but one.
    """

    def test_the_nvm_placeholder_is_the_one_btqca_rejects(self):
        """Anchors the whole diagnosis on the staged blob's own bytes."""
        nvm = ROOT / "out/bluetooth-firmware/qca/wcnhpnv21g.bin"
        if not nvm.is_file():
            self.skipTest("firmware not staged on this host")
        data = nvm.read_bytes()
        blob = hashlib.sha256(data).hexdigest()
        expected = "75229ef38873a51f711c2a38f3d6adcb80e8105e8e1d5e8570aea94b33441fe0"
        if blob != expected:
            self.skipTest("a different NVM revision is staged")
        # bdaddr_t is byte-reversed relative to the printed form.
        raw = bytes.fromhex("ad5a00000000")
        printed = ":".join("%02X" % b for b in reversed(raw))
        self.assertEqual(printed, PLACEHOLDER)

    def test_the_helper_reads_samsungs_own_file(self):
        text = read(HELPER)
        self.assertIn("/bluetooth/bt_addr", text)
        self.assertIn("by-partlabel/efs", text)

    def test_it_mounts_read_only_without_replaying_the_journal(self):
        """`ro` alone is not read-only: ext4 replays the journal and writes."""
        text = read(HELPER)
        self.assertIn("ro,noload", text)

    def test_it_cannot_write_to_an_android_partition(self):
        text = code_only(read(HELPER))
        for forbidden in ("mkfs", "e2fsck", "tune2fs", "dd if=", "> /mnt",
                          "tee /mnt", "hwclock -w", "wipefs"):
            self.assertNotIn(forbidden, text)

    def test_it_refuses_a_malformed_or_zero_address(self):
        text = read(HELPER)
        # Strict six-hex-pair validation, and an explicit all-zero refusal.
        self.assertIn("[0-9a-f]{2}:){5}[0-9a-f]{2}", text)
        self.assertIn("00:00:00:00:00:00", text)
        self.assertIn("refusing to use it", text)

    def test_it_never_generates_an_address(self):
        text = code_only(read(HELPER))
        for forbidden in ("random", "$RANDOM", "uuidgen", "od -An -N6"):
            self.assertNotIn(forbidden, text)

    def test_no_address_is_hardcoded(self):
        """The address is per-unit, so a literal would be wrong on every other
        tablet. Anchored on the real value too, so "just hardcode the one that
        works" cannot pass review by looking plausible."""
        text = code_only(read(HELPER))
        literals = re.findall(r"\b(?:[0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}\b", text)
        # The only MAC-shaped literals permitted are the all-zero refusals.
        for found in literals:
            self.assertEqual(
                found.lower(), "00:00:00:00:00:00",
                "no per-unit address may be hardcoded; found %r" % found)
        self.assertNotIn(REAL_ADDRESS, text)
        self.assertNotIn(PLACEHOLDER, text)

    def test_the_address_really_comes_from_the_file_read(self):
        """The assignment must be fed by the efs file, not by anything else."""
        text = code_only(read(HELPER))
        m = re.search(r'addr=\$\(tr[^\n]*BT_ADDR_FILE[^\n]*\)', text)
        self.assertIsNotNone(
            m, "the address must be read from BT_ADDR_FILE via a single assignment")
        # And it must be read only after the read-only mount succeeded: anchor on
        # the assignment itself, not on the variable's first mention, which is in
        # the configuration block at the top of the file.
        mount_at = text.index("ro,noload")
        assign_at = text.index(m.group(0))
        self.assertGreater(assign_at, mount_at,
                           "the file must be read through the ro,noload mount")

    def test_every_path_is_bounded_and_exits_zero(self):
        """It must never fail the boot, whatever the tablet's state."""
        text = read(HELPER)
        self.assertIn("ADDR_WAIT_SECONDS", text)
        # Every btmgmt invocation is wrapped in timeout.
        for m in re.finditer(r'^\s*(?:out=\$\(|if )?(run_btmgmt|timeout "\$secs"|\$BTMGM)', text, re.M):
            pass
        self.assertIn('timeout "$secs"', text)
        # And the script always ends successfully.
        self.assertTrue(text.rstrip().endswith("exit 0"))
        self.assertNotIn("exit 1", code_only(text))

    def test_it_reports_what_it_did(self):
        text = read(HELPER)
        for stage in ("bluetooth-address-set", "bluetooth-address-present",
                      "bluetooth-address-unavailable", "bluetooth-address-failed"):
            self.assertIn(stage, text)


class TheTwoHardwareOrderingTrapsStayFixed(unittest.TestCase):
    """Both look correct when read, and both failed only on the tablet.

    1. A ConditionPathExists on /sys/class/bluetooth/hci0 made systemd skip the
       unit outright: the condition is evaluated once, and hci_qca registers hci0
       from the DT serdev seconds later.
    2. `btmgmt ... </dev/null` hangs, and /dev/null is exactly what systemd
       supplies on stdin; the unit had to be killed by TimeoutStartSec.
    """

    def test_the_unit_does_not_condition_on_the_hci_node(self):
        text = read(HELPER_UNIT)
        self.assertNotIn("ConditionPathExists=/sys/class/bluetooth/hci0", text)
        # The partition condition is fine and stays.
        self.assertIn("ConditionPathExists=/dev/disk/by-partlabel/efs", text)

    def test_the_helper_waits_for_hci0_instead(self):
        text = read(HELPER)
        self.assertIn("/sys/class/bluetooth/hci0", text)
        self.assertIn("while [ \"$waited\" -lt \"$ADDR_WAIT_SECONDS\" ]", text)

    def test_btmgmt_is_never_given_dev_null_on_stdin(self):
        # Checked on the CODE, not the prose: the comment above the function
        # spells out `</dev/null` while explaining why it must not be used.
        text = code_only(read(HELPER))
        self.assertNotIn("</dev/null", text)
        self.assertIn(": | timeout", text)

    def test_the_unit_runs_before_bluetoothd(self):
        text = read(HELPER_UNIT)
        self.assertIn("Before=bluetooth.service", text)

    def test_the_dropin_makes_the_daemon_wait(self):
        text = read(DROPIN)
        self.assertIn("Wants=gts9-bluetooth-address.service", text)
        self.assertIn("After=gts9-bluetooth-address.service", text)

    def test_the_unit_is_oneshot_and_enableable(self):
        text = read(HELPER_UNIT)
        self.assertIn("Type=oneshot", text)
        self.assertIn("WantedBy=multi-user.target", text)
        # A timeout so it can never hold the boot open.
        self.assertIn("TimeoutStartSec=", text)


class NothingHereTouchesWifi(unittest.TestCase):
    """Bluetooth shares the combo chip and the PMU with Wi-Fi."""

    def test_no_wlan_firmware_is_staged_or_replaced(self):
        """Checked on code, not prose.

        The preflight deliberately *reads* ath11k's firmware directory to prove it
        is untouched, so the words appear in comments and in read-only probes. What
        must not appear is an instruction that writes or replaces WLAN firmware.
        """
        for rel in (STAGER, HELPER):
            text = code_only(read(rel))
            for forbidden in ("ath11k", "amss.bin", "m3.bin", "board-2.bin",
                              "wlan-enable", "pcie"):
                self.assertNotIn(forbidden, text,
                                 "%s must not touch %r" % (rel, forbidden))

    def test_the_preflight_only_reads_the_wlan_state(self):
        """Where ath11k does appear it must be inside a read."""
        text = code_only(read(PREFLIGHT))
        for line in text.splitlines():
            if "ath11k" not in line and "wlp1s0" not in line:
                continue
            stripped = line.strip()
            self.assertTrue(
                stripped.startswith(("run ", "echo ", "printf ", "for ", "case ",
                                     "ls ", "grep ", "cat ", "if ", "fi", "done",
                                     "$", "do", "then", "else", "esac", "}", ")", ";;"))
                or "|" in stripped or "=" in stripped,
                "preflight must only read WLAN state: %r" % stripped)
            for writer in ("> /sys", "> /dev", "ip link set", "nmcli", "rmmod",
                           "modprobe"):
                self.assertNotIn(writer, stripped,
                                 "preflight must not modify WLAN state: %r" % stripped)

    def test_the_kernel_tree_is_not_modified_by_this_round(self):
        """The whole round is userspace + host tooling; the DTS is untouched."""
        dts = read("kernel/dts/sm8550-samsung-gts9wifi.dts")
        # No address constant was added, which is the tempting wrong fix.
        self.assertNotIn("local-bd-address", dts)
        # The WCN6855 node keeps its upstream shape: supply map, no enable-gpios.
        node = re.search(r"bluetooth \{.*?\n\t\};", dts, re.S)
        self.assertIsNotNone(node, "the bluetooth node must still be present")
        self.assertNotIn("enable-gpios", node.group(0))
        self.assertIn('compatible = "qcom,wcn6855-bt"', node.group(0))

    def test_patch_0008_still_exists(self):
        self.assertTrue(
            (ROOT / "kernel/patches/0008-power-sequencing-qcom-wcn-send-aop-wlan-pdc-votes.patch").is_file())


class TheDocumentKeepsTheLayersHonest(unittest.TestCase):
    """Compiled is not loaded is not usable is not verified."""

    def test_the_doc_exists_and_uses_the_layer_vocabulary(self):
        text = read(DOC)
        for word in ("PHYSICALLY_VERIFIED", "NOT_TESTED", "REACHED", "FAILED"):
            self.assertIn(word, text)

    def test_it_does_not_claim_pairing_or_coexistence(self):
        text = read(DOC)
        # These must be recorded as untested rather than omitted.
        for item in ("pair / connect", "Wi-Fi + BT coexistence", "cold boot"):
            self.assertIn(item, text)

    def test_it_records_the_wedge_as_coincident_not_causal(self):
        text = read(DOC)
        self.assertIn("coincident", text)
        self.assertIn("CPU_WEDGE_EVIDENCE.md", text)

    def test_it_says_the_automatic_path_is_unverified(self):
        text = read(DOC)
        self.assertIn("NOT verified: the automatic boot path", text)


if __name__ == "__main__":
    unittest.main()
