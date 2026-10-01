"""Disassemble functions in dumped Xbox 360 system modules (PowerPC, big endian).

Labels calls using:
  - the real xam.xex export table (ordinal -> address, names from Xenia's xam_table.inc)
  - import thunks listed in a Xenia log (thunk address -> imported function name)

usage: dis.py <log> <addr> [<addr> ...] [--max N]
"""
import re
import struct
import sys
from pathlib import Path

import capstone

RE_DIR = Path(r"G:\Emulators\Xbox360\xenia-re")
XAM_TABLE = Path(r"G:\Emulators\Xbox360\src\xenia-canary\src\xenia\kernel\xam\xam_table.inc")
MODULES = {  # name: (base, dump file)
    "xam": (0x81870000, Path(__file__).parent / "dumps2858" / "xam_2858.bin"),
    "hud": (0x91440000, Path(__file__).parent / "dumps2858" / "hud_2858.bin"),
}
XAM_EXPORT_TABLE = 0x81A9C0D4

images = {n: (b, f.read_bytes()) for n, (b, f) in MODULES.items() if f.exists()}


def read(addr, size):
    for base, data in images.values():
        if base <= addr < base + len(data):
            off = addr - base
            return data[off:off + size]
    return None


def u32(addr):
    b = read(addr, 4)
    return struct.unpack(">I", b)[0] if b else None


labels = {}

# xam exports
xam_names = {}
for m in re.finditer(r"XE_EXPORT\(xam,\s+0x([0-9A-F]+), (\w+)", XAM_TABLE.read_text()):
    xam_names[int(m.group(1), 16)] = m.group(2)
# xex2_export_table: magic[3], modulenumber[2], version[3], imagebaseaddr,
# count, base, ordOffset[count]
t = XAM_EXPORT_TABLE
image_hi, count, ord_base = u32(t + 0x20), u32(t + 0x24), u32(t + 0x28)
for i in range(count):
    off = u32(t + 0x2C + 4 * i)
    if off:
        addr = (image_hi << 16) + off
        labels[addr] = "xam!" + xam_names.get(ord_base + i, f"ord_{ord_base + i:03X}")


def load_thunks(log_path):
    module = None
    for line in Path(log_path).read_text(errors="replace").splitlines():
        m = re.search(r"Module \\Device\\.*\\(\w+)\.xex:", line)
        if m:
            module = m.group(1)
            continue
        m = re.match(r"\s+F [0-9A-F]{8} ([0-9A-F]{8}) [0-9A-F]{3} \(\s*\d+\) (?:!!| ) (\S+)", line)
        if m and module in ("xam", "hud"):
            labels.setdefault(int(m.group(1), 16), f"{module}->{m.group(2)}")


md = capstone.Cs(capstone.CS_ARCH_PPC, capstone.CS_MODE_32 | capstone.CS_MODE_BIG_ENDIAN)
md.detail = False


def disasm(addr, max_ins=200):
    code = read(addr, max_ins * 4)
    if code is None:
        print(f"{addr:08X}: not in any dump")
        return
    print(f"\n==== {addr:08X} {labels.get(addr, '')}")
    for ins in md.disasm(code, addr):
        note = ""
        if ins.mnemonic in ("bl", "b", "bla") and ins.op_str.startswith("0x"):
            tgt = int(ins.op_str, 16)
            note = "  ; " + labels.get(tgt, "")
        print(f"  {ins.address:08X}: {ins.mnemonic:8} {ins.op_str}{note}")
        if ins.mnemonic in ("blr",) or (ins.mnemonic == "b" and ins.address != addr):
            if ins.mnemonic == "blr":
                break


def find_constant(module, value):
    """Addresses where `lis rX, hi` is followed within 4 insns by `ori rX, rX, lo`."""
    base, data = images[module]
    hi, lo = (value >> 16) & 0xFFFF, value & 0xFFFF
    hits = []
    for off in range(0, len(data) - 20, 4):
        w = struct.unpack_from(">I", data, off)[0]
        if (w >> 26) == 15 and ((w >> 16) & 0x1F) == 0 and (w & 0xFFFF) == hi:  # lis
            rd = (w >> 21) & 0x1F
            for k in range(1, 5):
                w2 = struct.unpack_from(">I", data, off + 4 * k)[0]
                # ori rA, rS, lo  (rS field = bits 21..25)
                if (w2 >> 26) == 24 and ((w2 >> 21) & 0x1F) == rd and (w2 & 0xFFFF) == lo:
                    hits.append(base + off)
                    break
    return hits


def find_callers(target):
    """All `bl target` instructions in every dump."""
    hits = []
    for base, data in images.values():
        for off in range(0, len(data), 4):
            w = struct.unpack_from(">I", data, off)[0]
            if (w >> 26) == 18 and (w & 3) == 1:  # bl (AA=0, LK=1)
                disp = w & 0x03FFFFFC
                if disp & 0x02000000:
                    disp -= 0x04000000
                if base + off + disp == target:
                    hits.append(base + off)
    return hits


def find_refs(target):
    """`lis rX, hi` followed within 8 insns by a D-form op on rX with the low half
    (addi/lwz/stw/lbz/stb/lhz/sth/ld/std...) that together address `target`."""
    hits = []
    lo = target & 0xFFFF
    slo = lo - 0x10000 if lo & 0x8000 else lo
    hi = ((target - slo) >> 16) & 0xFFFF
    for base, data in images.values():
        for off in range(0, len(data) - 36, 4):
            w = struct.unpack_from(">I", data, off)[0]
            if (w >> 26) != 15 or ((w >> 16) & 0x1F) != 0 or (w & 0xFFFF) != hi:
                continue
            rd = (w >> 21) & 0x1F
            for k in range(1, 9):
                w2 = struct.unpack_from(">I", data, off + 4 * k)[0]
                op = w2 >> 26
                ra = (w2 >> 16) & 0x1F
                if op in (14, 32, 34, 36, 38, 40, 44, 58, 62, 48, 50, 52, 54) and \
                        ra == rd and (w2 & 0xFFFF) == lo:
                    hits.append(base + off + 4 * k)
                    break
    return hits


def find_andi(module, mask):
    """`andi. rA, rS, mask` instructions (bit tests)."""
    base, data = images[module]
    return [base + off for off in range(0, len(data), 4)
            if (struct.unpack_from(">I", data, off)[0] >> 26) == 28 and
            (struct.unpack_from(">I", data, off)[0] & 0xFFFF) == mask]


def find_bit_tests(module, bit):
    """rlwinm forms that isolate a single bit (LSB numbering)."""
    base, data = images[module]
    ppc = 31 - bit
    hits = []
    for off in range(0, len(data), 4):
        w = struct.unpack_from(">I", data, off)[0]
        if (w >> 26) != 21:
            continue
        sh, mb, me = (w >> 11) & 31, (w >> 6) & 31, (w >> 1) & 31
        if (sh == 0 and mb == ppc and me == ppc) or \
                (mb == 31 and me == 31 and sh == (32 - bit) % 32 and bit != 0):
            hits.append(base + off)
    return hits


def containing_function(addr):
    """Walk back to the closest 'mflr r12' (function prologue)."""
    a = addr
    for _ in range(4000):
        if u32(a) == 0x7D8802A6:  # mflr r12
            return a
        a -= 4
    return None


if __name__ == "__main__":
    args = sys.argv[1:]
    max_ins = 200
    if "--max" in args:
        i = args.index("--max")
        max_ins = int(args[i + 1])
        del args[i:i + 2]
    load_thunks(args[0])
    for a in args[1:]:
        if a.startswith("bit:"):  # bit:<module>:<bit index, LSB=0>
            _, mod, val = a.split(":")
            seen = {}
            for hit in find_bit_tests(mod, int(val)):
                seen.setdefault(containing_function(hit), []).append(hit)
            for fn, hs in sorted(seen.items(), key=lambda x: x[0] or 0):
                print(f"function {fn or 0:08X} {labels.get(fn, '')}: {' '.join(f'{h:08X}' for h in hs)}")
            continue
        if a.startswith("andi:"):  # andi:<module>:<hex mask>
            _, mod, val = a.split(":")
            seen = {}
            for hit in find_andi(mod, int(val, 16)):
                seen.setdefault(containing_function(hit), []).append(hit)
            for fn, hs in sorted(seen.items(), key=lambda x: x[0] or 0):
                print(f"function {fn or 0:08X} {labels.get(fn, '')}: {' '.join(f'{h:08X}' for h in hs)}")
            continue
        if a.startswith("refs:"):  # refs:<hex addr of global>
            seen = {}
            for hit in find_refs(int(a[5:], 16)):
                fn = containing_function(hit)
                seen.setdefault(fn, []).append(hit)
            for fn, hs in sorted(seen.items(), key=lambda x: x[0] or 0):
                name = labels.get(fn, "") if fn else ""
                print(f"function {fn or 0:08X} {name}: {' '.join(f'{h:08X}' for h in hs)}")
            continue
        if a.startswith("callers:"):  # callers:<hex addr>
            for hit in find_callers(int(a[8:], 16)):
                fn = containing_function(hit)
                name = labels.get(fn, "") if fn else ""
                print(f"{hit:08X} in function {fn or 0:08X} {name}")
            continue
        if a.startswith("const:"):  # const:<module>:<hex value>
            _, mod, val = a.split(":")
            for hit in find_constant(mod, int(val, 16)):
                fn = containing_function(hit)
                name = labels.get(fn, "") if fn else ""
                print(f"{hit:08X} in function {fn or 0:08X} {name}")
            continue
        if a.startswith("find:"):
            key = a[5:].lower()
            for addr, name in sorted(labels.items()):
                if key in name.lower():
                    print(f"{addr:08X} {name}")
            continue
        disasm(int(a, 16), max_ins)
