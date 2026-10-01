"""Extract an Xbox 360 XUI package (magic 'XUIZ').

Layout (big endian):
  0x00 'XUIZ'  0x04 u32 version  0x08 u32 total size  0x0C u32 0
  0x10 u32 table size  0x14 u16 file count
  then per file: u32 size, u32 offset, u8 name length (chars), UTF-16BE name
File offsets are relative to the end of the table (0x16 + table size... found by probing).
"""
import struct
import sys
from pathlib import Path


def parse(buf):
    assert buf[:4] == b"XUIZ", buf[:4]
    table_size = struct.unpack_from(">I", buf, 0x10)[0]
    count = struct.unpack_from(">H", buf, 0x14)[0]
    p = 0x16
    entries = []
    for _ in range(count):
        size, off, nlen = struct.unpack_from(">IIB", buf, p)
        p += 9
        name = buf[p:p + 2 * nlen].decode("utf-16-be")
        p += 2 * nlen
        entries.append((name, off, size))
    return table_size, entries, p


def data_base(buf, table_size, entries, table_end):
    """Find where file data begins by checking a PNG entry's signature."""
    candidates = [table_end, 0x10 + table_size, 0x14 + table_size, 0x16 + table_size, 0x18 + table_size]
    pngs = [e for e in entries if e[0].lower().endswith(".png")]
    for base in candidates:
        if pngs and all(buf[base + o:base + o + 4] == b"\x89PNG" for _, o, _ in pngs[:3]):
            return base
    # fall back: first candidate where the first entry looks like XUR/XUS ('XUIB'/'XUIS')
    for base in candidates:
        if buf[base + entries[0][1]:base + entries[0][1] + 3] == b"XUI":
            return base
    raise SystemExit(f"could not locate data base (tried {[hex(c) for c in candidates]})")


def extract(path, offset, out_dir):
    buf = Path(path).read_bytes()[offset:]
    table_size, entries, table_end = parse(buf)
    base = data_base(buf, table_size, entries, table_end)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    for name, off, size in entries:
        dest = out / name.replace("\\", "/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(buf[base + off:base + off + size])
        magic = buf[base + off:base + off + 4]
        print(f"{name:32} {size:8}  {magic!r}")
    print(f"data base 0x{base:X}, {len(entries)} files -> {out}")


if __name__ == "__main__":
    extract(sys.argv[1], int(sys.argv[2], 16), sys.argv[3])
