"""Fast lis+lo reference / bl caller search over 2858 dumps (numpy).
usage: fastref.py refs:<hex>|callers:<hex> ... [--mods hud,xam]"""
import sys, numpy as np
from pathlib import Path
D = Path(__file__).parent / "dumps2858"
MODS = {"xam": (0x81870000, "xam_2858.bin"), "hud": (0x91440000, "hud_2858.bin"),
        "dash": (0x92000000, "dash_2858.bin"), "huduiskin": (0x91440000, "huduiskin_2858.bin"),
        "createprofile": (0x90100000, "createprofile_2858.bin"), "vk": (0x917E0000, "vk_2858.bin"),
        "gamerprofile": (0x90100000, "gamerprofile_2858.bin"), "signin": (0x90100000, "signin_2858.bin"), "mmp": (0x90100000, "minimediaplayer_2858.bin"), "mkt": (0x90100000, "marketplace_2858.bin")}
args = sys.argv[1:]
mods = ["hud", "xam"]
if "--mods" in args:
    i = args.index("--mods"); mods = args[i + 1].split(","); del args[i:i + 2]
imgs = {m: (MODS[m][0], np.frombuffer((D / MODS[m][1]).read_bytes()[: (Path(D / MODS[m][1]).stat().st_size // 4) * 4], ">u4").astype(np.int64)) for m in mods}

def func_start(w, idx):
    for j in range(idx, max(idx - 8000, 0), -1):
        if w[j] == 0x7D8802A6: return j
    return None

for a in args:
    kind, v = a.split(":"); t = int(v, 16)
    for m, (base, w) in imgs.items():
        hits = []
        if kind == "refs":
            lo = t & 0xFFFF; slo = lo - 0x10000 if lo & 0x8000 else lo
            hi = ((t - slo) >> 16) & 0xFFFF
            cand = np.nonzero(((w >> 26) == 15) & (((w >> 16) & 31) == 0) & ((w & 0xFFFF) == hi))[0]
            for c in cand:
                rd = (w[c] >> 21) & 31
                for k in range(1, 12):
                    if c + k >= len(w): break
                    w2 = int(w[c + k]); op = w2 >> 26
                    if op in (14, 32, 34, 36, 38, 40, 44, 58, 62, 48, 50, 52, 54) and ((w2 >> 16) & 31) == rd and (w2 & 0xFFFF) == lo:
                        hits.append(c + k); break
        else:
            idx = np.arange(len(w))
            bl = ((w >> 26) == 18) & ((w & 3) == 1)
            disp = w & 0x03FFFFFC
            disp = np.where(disp & 0x02000000, disp - 0x04000000, disp)
            hits = list(np.nonzero(bl & (base + idx * 4 + disp == t))[0])
        for h in hits:
            f = func_start(w, h)
            print(f"{a} {m}: {base + 4 * h:08X} in fn {base + 4 * f if f is not None else 0:08X}")
