"""mdis.py <module> <hex addr> [n]  - capstone disasm of one 2858 dump
(module as in fastref.py: createprofile, vk, gamerprofile, xam, hud, dash)."""
import sys
import capstone
from pathlib import Path

D = Path(__file__).parent / "dumps2858"
MODS = {"xam": (0x81870000, "xam_2858.bin"), "hud": (0x91440000, "hud_2858.bin"),
        "dash": (0x92000000, "dash_2858.bin"), "createprofile": (0x90100000, "createprofile_2858.bin"),
        "vk": (0x917E0000, "vk_2858.bin"), "gamerprofile": (0x90100000, "gamerprofile_2858.bin")}

m, a = sys.argv[1], int(sys.argv[2], 16)
n = int(sys.argv[3]) if len(sys.argv) > 3 else 120
base, f = MODS[m]
with open(D / f, "rb") as fh:
    fh.seek(a - base)
    code = fh.read(n * 4)
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
for i in md.disasm(code, a):
    print(f"  {i.address:08X}: {i.mnemonic:8} {i.op_str}")
