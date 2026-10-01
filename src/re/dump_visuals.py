"""Dump the skin visuals used by the Guide scenes: named frames, element tree, timelines."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xui_render as X  # noqa: E402

skin = X.load_canvas(X.ART / "xui" / "skin.xui")
vis = {c.id: c for c in skin.children if c.cls == "XuiVisual"}
used = set()
scenes = sys.argv[1:] or ["MainMenuSignedOut.xui", "InfoMessage.xui"]
for sc in scenes:
    root = X.load_canvas(X.ART / "xui" / sc)

    def walk(n):
        v = n.props.get("Visual")
        print(sc, n.cls, n.id, "visual=", v, "pos=", n.props.get("Position"),
              "size=", n.props.get("Width"), n.props.get("Height"))
        if v:
            used.add(v)
        elif n.cls in X.CONTROL_CLASSES:
            used.add(n.cls)
        for c in n.children:
            walk(c)
    walk(root.children[0])

for v in sorted(used):
    n = vis.get(v) or vis.get({"XuiNavButton": "XuiButton"}.get(v, ""))
    if not n:
        print("MISSING visual", v)
        continue
    print("\n=== visual", v, "->", n.id, "size", n.props.get("Width"), n.props.get("Height"))
    print(" frames:", sorted(n.frames.items(), key=lambda kv: kv[1]))

    def tree(n, d=1):
        for c in n.children:
            p = c.props
            print("  " * d + f"{c.cls} {c.id} pos={p.get('Position')} size={p.get('Width')}x{p.get('Height')}"
                  f" op={p.get('Opacity')} show={p.get('Show')} anchor={p.get('Anchor')} blend={p.get('BlendMode')}")
            tree(c, d + 1)
    tree(n)
    for tid, props, keys in n.timelines:
        print("  TL", tid, props, [(k[0], k[1], k[2]) for k in keys])
