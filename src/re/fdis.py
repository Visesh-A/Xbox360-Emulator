"""fdis.py <hex addr> [n]  - quick capstone disasm over 2858 hud/xam/dash dumps."""
import sys, struct, capstone
from pathlib import Path
D = Path(__file__).parent / "dumps2858"
MODS = [(0x81870000, "xam_2858.bin"), (0x91440000, "hud_2858.bin"), (0x92000000, "dash_2858.bin")]
a = int(sys.argv[1], 16); n = int(sys.argv[2]) if len(sys.argv) > 2 else 120
for base, f in MODS:
    size = (D / f).stat().st_size
    if base <= a < base + size:
        with open(D / f, "rb") as fh:
            fh.seek(a - base); code = fh.read(n * 4)
        break
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
for i in md.disasm(code, a):
    print(f"  {i.address:08X}: {i.mnemonic:8} {i.op_str}")
