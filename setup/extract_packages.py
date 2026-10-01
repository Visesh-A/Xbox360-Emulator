"""Extracts the XUI resource packages ('XUIZ') from the patched 2858 module
images (src/re/dumps2858/<module>_2858.bin) into art2858/2858/<module>; a
module with several packages gets <module>0, <module>1, ...

  python extract_packages.py <dumps dir> <out dir>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src" / "re"))
import xzp_extract  # noqa: E402

MODULES = ["hud", "huduiskin", "xam", "minimediaplayer", "signin", "createprofile",
           "vk", "gamerprofile", "marketplace"]


def packages(buf):
    """Offsets of the real packages: 'XUIZ' with a parseable table."""
    found, i = [], buf.find(b"XUIZ")
    while i >= 0:
        try:
            xzp_extract.parse(buf[i:])
            found.append(i)
        except Exception:
            pass
        i = buf.find(b"XUIZ", i + 4)
    return found


def main():
    dumps, out = Path(sys.argv[1]), Path(sys.argv[2])
    for module in MODULES:
        path = dumps / f"{module}_2858.bin"
        offsets = packages(path.read_bytes())
        if not offsets:
            raise SystemExit(f"{path}: no XUI package")
        for n, offset in enumerate(offsets):
            name = module if len(offsets) == 1 else f"{module}{n}"
            xzp_extract.extract(str(path), offset, str(out / name))


if __name__ == "__main__":
    main()
