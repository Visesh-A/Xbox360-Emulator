"""gamerprofile.xex's Game Defaults screens, as full-width Guide pages:

  830_GamerPreferences.xur  the categories (GamerPreferencesList): General,
                            Action, Racing; its metapanel shows the focused
                            one's description
  832_PreferenceCategory.xur  "%s Defaults": the category's settings, each a
                            label and a btn_spinner list (PreferenceValueList,
                            Wrap) of its values; left/right change it, A opens
                            831 (901100A8), rows past the category's count hidden
  831_PreferenceSetting.xur the setting's values (valueList), header = the
                            setting's name, metapanel = its description
                            (901108C0); a 480-high list: 10 rows, scrolling

Data (gamerprofile 2858): categories at 0x901018C8 {name, description,
settings, count}; settings (0x1C each) {name, description, profile setting id,
flags, values, count}; values (0x18 each) {string, 0, XUSER_DATA type, 0,
value, 0}. Strings from GamerProfile_Custom.xus.

Writes into the Guide asset folder:
  gpprefs_<c>.png        830 with category c focused (list rows drawn at run time)
  gpcat_<c>_<r>.png      832 for category c with row r's spinner focused
                         (spinner value texts drawn at run time)
  gpset_<s>.png          831 for setting s (list rows drawn at run time)
  gp_prow_normal/focus.png   a list row (XuiListItem, visual XuiButton, 420x45)
  gp_scroll_up/down.png, gp_scroll_shade_up/down.png   the list's XuiScrollEnds
                         (ScrollMore arrow; the Scrolling state's glow)
  prefs.txt              the data and where everything goes (see write_layout)
"""
import skia

import make_guide_assets as G
import xui_render as X
import xus

STR = xus.load(X.ART / "gamerprofile" / "GamerProfile_Custom.xus")
DUMP = (X.Path(__file__).parent / "dumps2858" / "gamerprofile_2858.bin").read_bytes()
BASE = 0x90100000
ROW_H = 45.0          # XuiList visual's control_ListItem
LIST_X, LIST_Y, LIST_H = 144.0, 102.0, 480.0   # preferenceList / valueList


def w32(a):
    return int.from_bytes(DUMP[a - BASE:a - BASE + 4], "big")


def read_data():
    cats = []
    for i in range(3):
        a = 0x901018C8 + i * 16
        name, desc, recs, count = w32(a), w32(a + 4), w32(a + 8), w32(a + 12) >> 16
        settings = []
        for j in range(count):
            r = recs + j * 0x1C
            vals = []
            for k in range(w32(r + 20) >> 16):
                v = w32(r + 16) + k * 0x18
                vals.append((w32(v + 16), STR[w32(v)]))
            settings.append(dict(name=STR[w32(r)], desc=STR[w32(r + 4)], id=w32(r + 8),
                                 flags=w32(r + 12), values=vals))
        cats.append(dict(name=STR[name], desc=STR[desc], settings=settings))
    return cats


def esc(s):
    return s.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n")


def visual(name):
    skin = X.cached_canvas(X.ART / "xui" / "skin.xui")
    return skin, next(c for c in skin.children if c.id == name)


def capture_text(vis_name, state, text_node=None, pad=(0, 0)):
    """The text item of a visual rendered on its own (units, from its origin)."""
    skin, vis = visual(vis_name)
    surf = skia.Surface(8, 8)
    canvas = surf.getCanvas()
    X.CAPTURE = {}
    overrides = X.apply_timelines(vis, state)
    if text_node:  # a child control's caption (btn_spinner's ListItem)
        overrides.setdefault(text_node, {})["NavTabForward"] = "\x01t"
        ctx = X.Ctx(text_node if state == "Focus" else None)
    else:
        ctx = X.Ctx(None, "\x01t")
    X.Renderer(skin).render_children(canvas, vis, ctx, overrides)
    e, X.CAPTURE = X.CAPTURE["t"], None
    return e


def item_line(key, e):
    return (f"{key} {e['tx']:.4f} {e['ty']:.4f} {e['w'] * e['sx']:.4f} {e['h'] * e['sy']:.4f} "
            f"{e['size_px']:.4f} {e['ascent']:.4f} {e['line_h']:.4f} {e['style']} {e['color']:08X}")


def save_visual(vis_name, state, name, size, origin):
    skin, vis = visual(vis_name)
    surf = skia.Surface(int(size[0] * G.SCALE), int(size[1] * G.SCALE))
    canvas = surf.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(G.SCALE, G.SCALE)
    canvas.translate(*origin)
    X.Renderer(skin).render_children(canvas, vis, X.Ctx(None), X.apply_timelines(vis, state))
    surf.makeImageSnapshot().save(str(G.OUT / f"{name}.png"), skia.kPNG)


def scroll_end(vis_name, name, scale):
    """An XuiScrollEnd's visual: <name>.png its ScrollMore arrow, <name>_shade.png
    its Scrolling glow (xhade1) at its brightest (frame 14; 0 at 4 and 25).
    Returns the images' offset from the control's origin and size (units)."""
    margin, size = (40.0, 30.0), (110.0, 100.0)
    skin, v = visual(vis_name)
    for suffix, ov in (("", X.apply_timelines(v, "ScrollMore")), ("_shade", X.timelines_at(v, 14))):
        if suffix:
            ov.setdefault("XuiImage1", {})["Show"] = "false"
        surf = skia.Surface(int(size[0] * scale * G.SCALE), int(size[1] * scale * G.SCALE))
        cv = surf.getCanvas()
        cv.clear(skia.ColorTRANSPARENT)
        cv.scale(G.SCALE * scale, G.SCALE * scale)
        cv.translate(*margin)
        X.Renderer(skin).render_children(cv, v, X.Ctx(None), ov)
        surf.makeImageSnapshot().save(str(G.OUT / f"{name}{suffix}.png"), skia.kPNG)
    return -margin[0] * scale, -margin[1] * scale, size[0] * scale, size[1] * scale


def main():
    G.apply_runtime_state()
    cats = read_data()
    lines = []
    panel = {"Text2": {"Show": "false"}}
    # 830: the list is drawn at run time
    for c, cat in enumerate(cats):
        st = {"preferenceList": {"Show": "false"}, "Text1": {"NavTabForward": cat["desc"]}, **panel}
        G.save(X.render_guide(G.FULL, "gp_830_GamerPreferences.xui", None, hide=G.PAGE_HIDE,
                                scale=G.SCALE, app_state=st), f"gpprefs_{c}.png")
    # 832: labels and spinners (their texts at run time)
    s_index = 0
    for c, cat in enumerate(cats):
        n = len(cat["settings"])
        for r in range(n):
            st = {"headerText": {"NavTabForward": STR[0x3C].replace("%s", cat["name"])}}
            for i in range(1, 9):
                if i <= n:
                    st[f"setting{i}Label"] = {"NavTabForward": cat["settings"][i - 1]["name"],
                                              "Show": "true"}
                    st[f"setting{i}Value"] = {"Show": "true"}
                else:  # rows past the category's settings are not shown
                    st[f"setting{i}Label"] = {"Show": "false"}
                    st[f"setting{i}Value"] = {"Show": "false"}
            G.save(X.render_guide(G.FULL, "gp_832_PreferenceCategory.xui", f"setting{r + 1}Value",
                                    hide=G.PAGE_HIDE, scale=G.SCALE, app_state=st),
                   f"gpcat_{c}_{r}.png")
    # 831: one page per setting
    for cat in cats:
        for s in cat["settings"]:
            st = {"valueList": {"Show": "false"}, "headerText": {"NavTabForward": s["name"]},
                  "Text1": {"NavTabForward": s["desc"]}, **panel}
            G.save(X.render_guide(G.FULL, "gp_831_PreferenceSetting.xui", None, hide=G.PAGE_HIDE,
                                    scale=G.SCALE, app_state=st), f"gpset_{s_index}.png")
            s_index += 1
    # list rows and spinner texts
    for state in ("Normal", "Focus"):
        save_visual("XuiButton", state, f"gp_prow_{state.lower()}", (420, 45), (0, 0))
        lines.append(item_line(f"rowtext {state.lower()}", capture_text("XuiButton", state)))
        lines.append(item_line(f"spintext {state.lower()}",
                               capture_text("btn_spinner", state, "ListItem")))
    root = X.cached_canvas(X.ART / "xui" / "gp_832_PreferenceCategory.xui").children[0]
    for i in range(1, 9):
        x, y, _ = X.vec(root.find(f"setting{i}Value").props.get("Position"))
        lines.append(f"spin {i - 1} {x:.4f} {y:.4f}")
    # the list's scroll ends: XuiList visual 420x74, both anchored right and
    # bottom (Anchor 12), so in the 480-high list they are 406 lower
    _, lst = visual("XuiList")
    dh = LIST_H - float(lst.props.get("Height"))
    for cid, name in (("control_ScrollUp", "up"), ("control_ScrollDown", "down")):
        node = lst.find(cid)
        x, y, _ = X.vec(node.props.get("Position"))
        ox, oy, w, h = scroll_end(node.props.get("Visual"), f"gp_scroll_{name}", 1.0)
        lines.append(f"scroll {name} {LIST_X + x + ox:.4f} {LIST_Y + y + dh + oy:.4f} {w:.4f} {h:.4f}")
    # btn_spinner's ScrollLeft / ScrollRight (scale 1.3, shown on focus: they
    # fade in over the visual's Focus frames 2-8), from the spinner's origin
    _, spin = visual("btn_spinner")
    for cid, name in (("ScrollLeft", "left"), ("ScrollRight", "right")):
        node = spin.find(cid)
        x, y, _ = X.vec(node.props.get("Position"))
        sc = X.vec(node.props.get("Scale"), (1.0, 1.0, 1.0))[0]
        ox, oy, w, h = scroll_end(node.props.get("Visual"), f"gp_spin_{name}", sc)
        lines.append(f"spinarrow {name} {x + ox:.4f} {y + oy:.4f} {w:.4f} {h:.4f}")
    lines.append(f"list {LIST_X} {LIST_Y} 420 {ROW_H} {int(LIST_H // ROW_H)}")
    for c, cat in enumerate(cats):
        lines.append(f"cat {c} {esc(cat['name'])}")
        for s in cat["settings"]:
            lines.append(f"setting {c} {s['id']:08X} {s['flags']} {esc(s['name'])}")
            for v, t in s["values"]:
                lines.append(f"value {v} {esc(t)}")
    (G.OUT / "prefs.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
