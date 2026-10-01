"""Convert an Xbox 360 system font (.xtt / .xttp, magic 'xttf') to a TrueType file.

Format, read off xam.xex's font loader (819465A0 -> 81946380 -> zlib uncompress):
  0x000  'xttf'
  0x004  0x100-byte signature (checked by xam, not needed here)
  0x104  5 x u32 BE: compressed size, file size, compressed size, uncompressed
         size, version 0x10000
  0x118  zlib stream: an sfnt with cmap/head/hhea/hmtx/name and the Xbox tables
         xchk, xttf, xloc, xglf ('xglf' has no data in the stream: its offset
         is a *file* offset)
  xglf   (file offset from the directory) 4 KB pages, each its own zlib stream
         of TrueType 'glyf' records
  xloc   u32 per glyph (+1): page index << 16 | offset in the decompressed page
The glyph records are standard TrueType, so glyf/loca/maxp/post/OS2 are rebuilt.

  python xtt_to_ttf.py <in.xtt> <out.ttf>
"""
import struct
import sys
import zlib

from fontTools.fontBuilder import FontBuilder  # noqa: F401  (fontTools present)
from fontTools.ttLib import TTFont, newTable
from fontTools.ttLib.tables._g_l_y_f import Glyph


def read_xtt(path):
    raw = open(path, "rb").read()
    assert raw[:4] == b"xttf", "not an xtt font"
    sfnt = zlib.decompressobj().decompress(raw[0x118:])
    num = struct.unpack(">H", sfnt[4:6])[0]
    tables = {}
    for i in range(num):
        tag, _, off, length = struct.unpack(">4sIII", sfnt[12 + 16 * i:28 + 16 * i])
        tables[tag.decode()] = (off, length)
    data = {t: sfnt[o:o + n] for t, (o, n) in tables.items() if t != "xglf"}
    g_off, g_len = tables["xglf"]
    xglf = raw[g_off:g_off + g_len]
    xloc = struct.unpack(">%dI" % (len(data["xloc"]) // 4), data["xloc"])
    pages = {}

    def page(i):
        if i not in pages:
            pages[i] = zlib.decompressobj().decompress(xglf[i * 0x1000:(i + 1) * 0x1000])
        return pages[i]

    glyphs = []
    for g in range(len(xloc) - 1):
        a, b = xloc[g], xloc[g + 1]
        if a == b:
            glyphs.append(b"")
            continue
        pa, oa, pb, ob = a >> 16, a & 0xFFFF, b >> 16, b & 0xFFFF
        glyphs.append(page(pa)[oa:ob if pa == pb else len(page(pa))])
    return data, glyphs


def build_ttf(data, glyphs, out_path):
    # Start from the stream's own standard tables.
    num = len(glyphs)
    tags = ["cmap", "head", "hhea", "hmtx", "name"]
    dirlen = 12 + 16 * len(tags)
    body, entries, off = b"", [], dirlen
    for t in tags:
        blob = data[t]
        pad = (4 - len(blob) % 4) % 4
        entries.append((t, off, len(blob)))
        body += blob + b"\0" * pad
        off += len(blob) + pad
    head = struct.pack(">IHHHH", 0x00010000, len(tags), 0, 0, 0)
    for t, o, n in entries:
        head += struct.pack(">4sIII", t.encode(), 0, o, n)
    import io
    font = TTFont(io.BytesIO(head + body))
    font["hhea"].numberOfHMetrics  # parse
    order = ["glyph%d" % i if i else ".notdef" for i in range(num)]
    font.setGlyphOrder(order)
    # glyf/loca from the decoded records
    glyf = newTable("glyf")
    glyf.glyphs, glyf.glyphOrder = {}, order
    for name, rec in zip(order, glyphs):
        glyf.glyphs[name] = Glyph(rec) if rec else Glyph()
    font["glyf"] = glyf
    font["loca"] = newTable("loca")
    maxp = newTable("maxp")
    maxp.tableVersion = 0x00010000
    for k in ("maxZones", ):
        setattr(maxp, k, 2)
    for k in ("maxPoints", "maxContours", "maxCompositePoints", "maxCompositeContours",
              "maxTwilightPoints", "maxStorage", "maxFunctionDefs", "maxInstructionDefs",
              "maxStackElements", "maxSizeOfInstructions", "maxComponentElements",
              "maxComponentDepth"):
        setattr(maxp, k, 0)
    maxp.numGlyphs = num
    font["maxp"] = maxp
    post = newTable("post")
    post.formatType, post.italicAngle, post.underlinePosition = 3.0, 0, -100
    post.underlineThickness, post.isFixedPitch = 50, 0
    post.minMemType42 = post.maxMemType42 = post.minMemType1 = post.maxMemType1 = 0
    font["post"] = post
    hhea = font["hhea"]
    os2 = newTable("OS/2")
    os2.version = 4
    os2.xAvgCharWidth = int(sum(w for w, _ in font["hmtx"].metrics.values()) / max(1, num))
    os2.usWeightClass, os2.usWidthClass, os2.fsType = 400, 5, 0
    for k in ("ySubscriptXSize", "ySubscriptYSize", "ySubscriptXOffset", "ySubscriptYOffset",
              "ySuperscriptXSize", "ySuperscriptYSize", "ySuperscriptXOffset", "ySuperscriptYOffset",
              "yStrikeoutSize", "yStrikeoutPosition", "sFamilyClass", "ulUnicodeRange1",
              "ulUnicodeRange2", "ulUnicodeRange3", "ulUnicodeRange4", "ulCodePageRange1",
              "ulCodePageRange2", "sxHeight", "sCapHeight", "usDefaultChar", "usBreakChar",
              "usMaxContext"):
        setattr(os2, k, 0)
    from fontTools.ttLib.tables.O_S_2f_2 import Panose
    os2.panose = Panose()
    os2.achVendID = "XBOX"
    os2.fsSelection = 0x40
    cmap = font["cmap"].getBestCmap() or {}
    os2.usFirstCharIndex = min(cmap) if cmap else 0x20
    os2.usLastCharIndex = min(max(cmap), 0xFFFF) if cmap else 0x7E
    os2.sTypoAscender, os2.sTypoDescender = hhea.ascent, hhea.descent
    os2.sTypoLineGap = hhea.lineGap
    os2.usWinAscent, os2.usWinDescent = hhea.ascent, -hhea.descent
    font["OS/2"] = os2
    font["glyf"].compile(font)  # recalc bounds
    # a fixed modification time (that of the first conversion, 2026-09-28) so
    # every conversion gives the same file
    font.recalcTimestamp = False
    font["head"].modified = 3873415571
    font.save(out_path)
    return font


if __name__ == "__main__":
    data, glyphs = read_xtt(sys.argv[1])
    f = build_ttf(data, glyphs, sys.argv[2])
    names = {r.nameID: r.toUnicode() for r in f["name"].names}
    print(sys.argv[2], "glyphs", len(glyphs), "name", names)
