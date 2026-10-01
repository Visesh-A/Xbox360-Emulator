"""Compares what setup built with the reference setup (manifests/expected.sha256)
or, with --write, records the current files as the reference.

  python verify.py            check
  python verify.py --write    (maintainer) rewrite manifests/expected.sha256
"""
import hashlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).parent / "manifests" / "expected.sha256"
# what setup builds
SCOPE = ["1888.FS", "xenia-dash/content", "xenia-dash/guide", "xenia-dash/gamerpics",
         "xenia-bootanim/xenia_canary.exe", "xenia-bootanim/content",
         "src/re/guide_art_2858", "src/re/fonts/XenonCLatin_1888.ttf", "src/re/vk_keys.json"]
# not built by setup: reference photos used while matching the real console
SKIP_PREFIXES = ["xenia-dash/guide/ref_"]


def files():
    for s in SCOPE:
        p = ROOT / s
        for f in ([p] if p.is_file() else sorted(x for x in p.rglob("*") if x.is_file())):
            rel = f.relative_to(ROOT).as_posix()
            if not any(rel.startswith(x) for x in SKIP_PREFIXES):
                yield rel, f


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if "--write" in sys.argv:
        lines = [f"{sha256(f)}  {rel}" for rel, f in files()]
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"{len(lines)} files recorded")
        return 0
    expected = {}
    for line in MANIFEST.read_text(encoding="utf-8").splitlines():
        h, rel = line.split("  ", 1)
        expected[rel] = h
    have = dict(files())
    missing = sorted(set(expected) - set(have))
    extra = sorted(set(have) - set(expected))
    differ = sorted(rel for rel in set(expected) & set(have) if sha256(have[rel]) != expected[rel])
    for title, names in (("missing", missing), ("differs", differ), ("not in the reference", extra)):
        for n in names[:50]:
            print(f"   {title}: {n}")
        if len(names) > 50:
            print(f"   ... {len(names) - 50} more {title}")
    ok = not missing and not differ
    print(f"   {len(expected) - len(missing) - len(differ)} of {len(expected)} files identical"
          + ("" if ok else " - NOT identical"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
