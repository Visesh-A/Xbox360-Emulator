"""adis.py <module> <start hex> <end hex> - disasm with import thunks named
(xam/xboxkrnl ordinals from xenia's export tables)."""
import re
import sys
import capstone
from pathlib import Path

D = Path(__file__).parent / "dumps2858"
MODS = {"xam": (0x81870000, "xam_2858.bin"), "createprofile": (0x90100000, "createprofile_2858.bin"), "vk": (0x917E0000, "vk_2858.bin"),
        "gamerprofile": (0x90100000, "gamerprofile_2858.bin"), "dash": (0x92000000, "dash_2858.bin"), "hud": (0x91440000, "hud_2858.bin"), "signin": (0x90100000, "signin_2858.bin"), "mmp": (0x90100000, "minimediaplayer_2858.bin"), "mkt": (0x90100000, "marketplace_2858.bin")}
X = Path(__file__).resolve().parents[1] / "xenia-canary" / "src" / "xenia" / "kernel"


def table(p):
    names = {}
    for m in re.finditer(r"XE_EXPORT\(\w+,\s*0x([0-9A-Fa-f]+),\s*(\w+)", p.read_text()):
        names[int(m.group(1), 16)] = m.group(2)
    return names


XAM = table(next(X.rglob("xam_table.inc")))
KRNL = table(next(X.rglob("xboxkrnl_table.inc")))
m = sys.argv[1]
base, f = MODS[m]
d = (D / f).read_bytes()
words = [int.from_bytes(d[i:i + 4], "big") for i in range(0, len(d) - 3, 4)]
thunks = {}
libs = {}
for i in range(len(words) - 3):
    w0, w1, w2 = words[i], words[i + 1], words[i + 2]
    if w0 >> 24 == 0x01 and w1 >> 24 == 0x02 and (w0 & 0xFFFF) == (w1 & 0xFFFF) and w2 == 0x7D6903A6:
        lib = (w0 >> 16) & 0xFF
        libs.setdefault(lib, 0)
        libs[lib] += 1
        thunks[base + i * 4] = (lib, w0 & 0xFFFF)
# which lib index is xam: the one whose ordinals name XamAppLoad at 0x244
def name(a):
    lib, o = thunks[a]
    # lib 0 = xam, lib 1 = xboxkrnl (in the title modules' import libraries)
    return f"{['xam', 'krnl'][lib]}#{o:X} " + ((XAM, KRNL)[lib].get(o) or "?")
s, e = int(sys.argv[2], 16), int(sys.argv[3], 16)
md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
md.skipdata = True
for ins in md.disasm(d[s - base:e - base], s):
    note = ""
    if ins.mnemonic == "bl":
        t = int(ins.op_str, 16)
        if t in thunks:
            note = "  ; " + name(t)
    print(f"  {ins.address:08X}: {ins.mnemonic:8} {ins.op_str}{note}")
