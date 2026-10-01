"""Dump the hudbkgnd frame scene's figures: transforms and point bounds vs box."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import xui_render as X  # noqa: E402

root = X.load_canvas(X.ART / "xui" / "xam_hudbkgnd.xui").children[0]
anim = {tid for tid, _, _ in root.timelines}


def bounds(points):
    vals = [float(x) for x in points.strip(",").split(",") if x != ""]
    n = int(vals[0])
    pts = [vals[1 + 7 * i:1 + 7 * i + 7] for i in range(n)]
    ax = [p[0] for p in pts]; ay = [p[1] for p in pts]
    cx = ax + [p[2] for p in pts] + [p[4] for p in pts]
    cy = ay + [p[3] for p in pts] + [p[5] for p in pts]
    return n, (min(ax), min(ay), max(ax), max(ay)), (min(cx), min(cy), max(cx), max(cy)), pts


def walk(n, d=0):
    p = n.props
    extra = ""
    if n.cls == "XuiFigure" and p.get("Points"):
        cnt, ab, cb, pts = bounds(p["Points"])
        extra = (f" pts={cnt} closed={p.get('Closed')} anchorbox=({ab[0]:.1f},{ab[1]:.1f})-({ab[2]:.1f},{ab[3]:.1f})"
                 f" ctrlbox=({cb[0]:.1f},{cb[1]:.1f})-({cb[2]:.1f},{cb[3]:.1f})"
                 f" stroke={'y' if isinstance(p.get('Stroke'), dict) else 'n'} fill={(p.get('Fill') or {}).get('FillType') if isinstance(p.get('Fill'), dict) else None}")
    print("  " * d + f"{n.cls} '{n.id}'{' [anim]' if n.id in anim else ''} pos={p.get('Position')} size={p.get('Width')}x{p.get('Height')}"
          f" rot={p.get('Rotation')} scale={p.get('Scale')} pivot={p.get('Pivot')} op={p.get('Opacity')}" + extra)
    for c in n.children:
        walk(c, d + 1)


target = sys.argv[1] if len(sys.argv) > 1 else "graphic-blade"
node = root.find(target) if target != "ROLV" else None
visual = node.props.get("Visual") if node else None
print("scene node", target, "visual", visual)
skin = X.load_canvas(X.ART / "xui" / "skin.xui")
vis = {c.id: c for c in skin.children if c.cls == "XuiVisual"}
v = vis.get(visual or ("ringOfLight_Group" if target == "ROLV" else target))
if v is None:
    walk(node or root)
else:
    anim = {tid for tid, _, _ in v.timelines}
    print("frames", v.frames)
    walk(v)
    for tid, props, keys in v.timelines:
        print("  TL", tid, props, [(k[0], k[1], k[2]) for k in keys][:6])
