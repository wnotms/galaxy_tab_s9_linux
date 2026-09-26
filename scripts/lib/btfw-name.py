#!/usr/bin/env python3
"""Derive the WCN6855 Bluetooth firmware file names from the controller's own
version words, using the pinned kernel's arithmetic.

This exists so the file names this project stages are *checkable* rather than
asserted. The alternative - copying a name out of a log and hoping the mapping
generalises - is how the wrong rampatch gets shipped for a different ROM.

The arithmetic is transcribed from the pinned tree (Linux v7.2-rc3,
a13c140cc289c0b7b3770bce5b3ad42ab35074aa):

  drivers/bluetooth/btqca.h:51
      #define get_soc_ver(soc_id, rom_ver)  ((le32_to_cpu(soc_id) << 16) | (le16_to_cpu(rom_ver)))

  drivers/bluetooth/btqca.c:795   (the default branch, which WCN6855 takes)
      rom_ver = ((soc_ver & 0x00000f00) >> 0x04) | (soc_ver & 0x0000000f);

  drivers/bluetooth/btqca.c:842   (rampatch, QCA_WCN6855)
      "qca/wcnhpbtfw%02x.tlv"

  drivers/bluetooth/btqca.c:868   (rampatch fallback, if the first load fails)
      "qca/hpbtfw%02x.tlv"

  drivers/bluetooth/btqca.c:934-936  (NVM, QCA_WCN6855)
      stem = "wcnhpnv"; qca_get_nvm_name_by_board(...)

  drivers/bluetooth/btqca.c:734-750 (NVM name shape)
      variant = "g" when (soc_id & QCA_HSP_GF_SOC_MASK) == QCA_HSP_GF_SOC_ID
      rom_ver != 0, bid not in {0, 0xffff}:  qca/<stem><rom_ver><variant>.b<bid>
      rom_ver != 0, bid in {0, 0xffff}:      qca/<stem><rom_ver><variant>.bin

Usage:
  btfw-name.py 0x12110201                 # from the controller version word
  btfw-name.py --soc-id 0x400c1211 --rom-ver 0x0201
  btfw-name.py --dmesg FILE               # parse a saved hci_qca dmesg trace

The board ID is deliberately NOT guessable here: it is only readable from the
controller after the rampatch is loaded, so it is an input, never a default.
Without it the tool prints the NVM name *patterns* and says so.
"""

import argparse
import re
import sys

QCA_HSP_GF_SOC_ID = 0x1200
QCA_HSP_GF_SOC_MASK = 0x0000FF00

# The WCN6855 needs these two; they are the pair the driver tries in order.
RAMPATCH_STEM = "wcnhpbtfw"          # upstream's corrected name
RAMPATCH_STEM_FALLBACK = "hpbtfw"    # the historical name, tried if the first fails
NVM_STEM = "wcnhpnv"


def soc_version(soc_id: int, rom_ver: int) -> int:
    """get_soc_ver() from btqca.h, including its 32-bit truncation."""
    return (((soc_id & 0xFFFFFFFF) << 16) & 0xFFFFFFFF) | (rom_ver & 0xFFFF)


def derived_rom_ver(soc_ver: int) -> int:
    """The default branch of qca_uart_setup(), which WCN6855 takes."""
    return ((soc_ver & 0x00000F00) >> 0x04) | (soc_ver & 0x0000000F)


def is_globalfoundries(soc_id: int) -> bool:
    return (soc_id & QCA_HSP_GF_SOC_MASK) == QCA_HSP_GF_SOC_ID


def names(soc_id: int, rom_ver_raw: int, board_id: int | None = None) -> dict:
    soc_ver = soc_version(soc_id, rom_ver_raw)
    rom = derived_rom_ver(soc_ver)
    variant = "g" if is_globalfoundries(soc_id) else ""

    out = {
        "soc_ver": f"0x{soc_ver:08x}",
        "rom_ver": f"0x{rom:02x}",
        "rom_ver_dec": rom,
        "variant": variant or "(none)",
        "rampatch": f"qca/{RAMPATCH_STEM}{rom:02x}.tlv",
        "rampatch_fallback": f"qca/{RAMPATCH_STEM_FALLBACK}{rom:02x}.tlv",
    }

    if board_id is None:
        out["nvm"] = None
        out["nvm_note"] = (
            "board ID unknown - it is only readable after the rampatch is loaded. "
            f"The driver will ask for qca/{NVM_STEM}{rom:02x}{variant}.bin "
            f"(bid 0/0xffff) or qca/{NVM_STEM}{rom:02x}{variant}.b<bid>."
        )
    elif board_id in (0x0, 0xFFFF):
        out["nvm"] = f"qca/{NVM_STEM}{rom:02x}{variant}.bin"
        out["nvm_note"] = (
            f"board ID {board_id:#06x} means the driver falls back to a generic "
            "NVM with no board suffix."
        )
    else:
        out["nvm"] = f"qca/{NVM_STEM}{rom:02x}{variant}.b{board_id:02x}"
        out["nvm_note"] = f"board-specific NVM for board ID {board_id:#06x}."

    return out


def parse_dmesg(text: str) -> dict:
    """Pull the version words out of a saved hci_qca trace.

    Anchored on btqca's own log strings so a trace from any kernel carrying this
    driver parses, and a missing line is an error rather than a silent default.
    """
    want = {
        "soc_id": r"QCA SOC Version\s*:\s*(0x[0-9a-fA-F]+)",
        "rom_ver": r"QCA ROM Version\s*:\s*(0x[0-9a-fA-F]+)",
        "product_id": r"QCA Product ID\s*:\s*(0x[0-9a-fA-F]+)",
        "patch_ver": r"QCA Patch Version\s*:\s*(0x[0-9a-fA-F]+)",
        "controller": r"QCA controller version\s+(0x[0-9a-fA-F]+)",
    }
    found = {}
    for key, pat in want.items():
        m = re.search(pat, text)
        if m:
            found[key] = int(m.group(1), 16)

    if "soc_id" not in found or "rom_ver" not in found:
        sys.exit(
            "btfw-name: the trace has no 'QCA SOC Version' / 'QCA ROM Version' line.\n"
            "  Those are printed by btqca during qca_uart_setup(); without them the\n"
            "  firmware name cannot be derived and must not be guessed."
        )

    # A board ID may appear in the trace if a previous boot got far enough.
    m = re.search(r"board id[^0-9a-fA-F]*(0x[0-9a-fA-F]+)", text, re.I)
    if m:
        found["board_id"] = int(m.group(1), 16)
    return found


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("version", nargs="?", help="controller version word, e.g. 0x12110201")
    ap.add_argument("--soc-id", help="raw QCA SOC Version word, e.g. 0x400c1211")
    ap.add_argument("--rom-ver", help="raw QCA ROM Version word, e.g. 0x0201")
    ap.add_argument("--board-id", help="board ID from the controller, e.g. 0x0a")
    ap.add_argument("--dmesg", help="file containing a saved hci_qca trace")
    args = ap.parse_args()

    board_id = int(args.board_id, 16) if args.board_id else None

    if args.dmesg:
        with open(args.dmesg, "r", errors="replace") as fh:
            parsed = parse_dmesg(fh.read())
        soc_id = parsed["soc_id"]
        rom_raw = parsed["rom_ver"]
        if board_id is None:
            board_id = parsed.get("board_id")
        print("# parsed from %s" % args.dmesg)
        for k in ("product_id", "soc_id", "rom_ver", "patch_ver", "controller"):
            if k in parsed:
                print(f"#   {k:12s} = 0x{parsed[k]:08x}")
    elif args.soc_id and args.rom_ver:
        soc_id = int(args.soc_id, 16)
        rom_raw = int(args.rom_ver, 16)
    elif args.version:
        # A controller version word is get_soc_ver()'s output: the low 16 bits
        # are the raw ROM version, so both inputs can be recovered exactly.
        soc_ver = int(args.version, 16)
        soc_id = (soc_ver >> 16) & 0xFFFFFFFF
        rom_raw = soc_ver & 0xFFFF
        print(f"# from controller version word 0x{soc_ver:08x}")
        print(f"#   soc_id  = 0x{soc_id:08x}")
        print(f"#   rom_ver = 0x{rom_raw:04x} (raw)")
    else:
        ap.error("give a version word, --soc-id/--rom-ver, or --dmesg FILE")

    info = names(soc_id, rom_raw, board_id)
    print(f"#   soc_ver  = {info['soc_ver']}   (= (soc_id << 16) | rom_ver)")
    print(f"#   rom_ver  = {info['rom_ver']} (derived; this is what names the files)")
    print(f"#   variant  = {info['variant']}"
          f"{'  (GlobalFoundries)' if info['variant'] == 'g' else ''}")
    print()
    print(f"rampatch          : {info['rampatch']}")
    print(f"rampatch fallback : {info['rampatch_fallback']}")
    if info["nvm"]:
        print(f"NVM               : {info['nvm']}")
    else:
        print("NVM               : (unknown until the board ID is read)")
    print(f"# {info['nvm_note']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
