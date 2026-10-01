"""xamexp.py <name|ordinal hex> ... - the address of a xam export in the 2858
memory dump (its XEX export table: magic 48000000 00485645 48000000, then
module numbers, version, image base, count, base ordinal, and the
addresses as offsets from 0x81870000)."""
import re
import struct
import sys
from pathlib import Path

b = (Path(__file__).parent / "dumps2858" / "xam_2858.bin").read_bytes()
i = b.find(struct.pack(">III", 0x48000000, 0x00485645, 0x48000000))
TAB = i + 44
X = Path(__file__).resolve().parents[1] / "xenia-canary" / "src" / "xenia" / "kernel"
NAMES = {m.group(2): int(m.group(1), 16) for m in re.finditer(
    r"XE_EXPORT\(\w+,\s*0x([0-9A-Fa-f]+),\s*(\w+)", next(X.rglob("xam_table.inc")).read_text())}


def addr(o):
    return 0x81870000 + struct.unpack(">I", b[TAB + (o - 1) * 4:TAB + o * 4])[0]


if __name__ == "__main__":
    for a in sys.argv[1:]:
        o = NAMES[a] if a in NAMES else int(a, 16)
        print(f"{a} #{o:X} {addr(o):08X}")
