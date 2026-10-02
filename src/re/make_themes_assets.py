"""Personal Settings > Themes (hud.xex), half-width Guide pages:

  optskin   SkinSelect.xur, SkinsList (9144ED48): Customize (Strings 12),
            Xbox 360 (Default) (6), Carbon (7), Glass (9), then installed
            themes (none here); after enumerating, the list and "Select a
            theme." show (9144CEF0)
  optcust   OptionsPersonalization.xur: CustomizeList's items (Dashboard Trim,
            Guide Background; Camera Effect is removed while XUsbcamGetState
            finds no camera, 9144D1B8)
  opttrim   DashStyleSelect.xur, StyleList: Default Trim (11), Carbon Trim
            (8), Glass Trim (10)
  opttile   TileSelect.xur, TileList (9144EE50): Custom Color (13), Default
            (14), then the seven tiles sorted by name (9144D500): Bubblegum,
            Dew, Pearl, Smoke, Stone, Tangerine, Wood; 7 rows show (349 / 45)
            and the list scrolls; PreviewId shows the focused tile
  optcolor  ColorSelect.xur: three sliders 10-255 and the colour's preview

Rows are XuiButton visuals (XuiList / list_Common's control_ListItem, 420 x
45) at the list's place, one layer per row per slot it can show in.

Writes into the Guide asset folder (in options.txt's format, themes.txt):
  page / layer lines; "row <page> <list id> <rows> <visible>"
  "rect <page> <name> x y w h" (units): the colour preview
  "text <page> <name> ..." (MessageBoxItem): the sliders' values
"""
import copy
import os

import make_guide_assets as G
import make_options_assets as O
import xui_render as X

S = G.STRINGS
TILES = sorted([(S[0], "Bubbles.png"), (S[17], "H2O.png"), (S[35], "Pearl.png"), (S[1], "Carbon.png"),
                (S[36], "Sahara.png"), (S[16], "Fiber.png"), (S[49], "Wood.png")])
LISTS = {
    # page: (scene, list id, rows, visible, shown, hidden)
    "optskin": ("SkinSelect.xui", "SkinsListId", [S[12], S[6], S[7], S[9]], 9,
                ("SkinsListId", "txtSelectSkin"), ("txt_Enumerating", "ProgressAnim")),
    "optcust": ("OptionsPersonalization.xui", "CustomizeList", ["Dashboard Trim", "Guide Background"], 4,
                (), ()),
    "opttrim": ("DashStyleSelect.xui", "StyleListId", [S[11], S[8], S[10]], 11, (), ()),
    "opttile": ("TileSelect.xui", "TileListId", [S[13], S[14]] + [t[0] for t in TILES], 7, (), ()),
}
K = X.SUPERSAMPLE * G.SCALE
# A Guide look (render_guide_look.py): only the images with the Guide
# background (the pages' bases and legends); the controls' layers and
# themes.txt are the default's (they have no background)
LOOK = bool(os.environ.get("GUIDE_BACKGROUND"))
ROW_H = 45.0


def row_node(template, x, y, text, rid):
    n = copy.deepcopy(template)
    n.cls = "XuiButton"
    n.id = rid
    n.children = []
    n.props = {"Id": rid, "Width": "420.000000", "Height": "45.000000",
               "Position": f"{x},{y},0.000000", "Visual": "XuiButton", "NavTabForward": text}
    return n


def main():
    G.apply_runtime_state()
    no_legends = G.PAGE_HIDE + G.LEGENDS
    layer_hide = G.CONTENT_HIDE + G.LEGENDS
    for page, (scene, lid, rows, visible, shown, hidden) in LISTS.items():
        root = copy.deepcopy(X.cached_canvas(X.ART / "xui" / scene).children[0])
        lst = root.find(lid)
        lx, ly, _ = X.vec(lst.props.get("Position"))
        st = {e: {"Show": "true"} for e in shown}
        st.update({e: {"Show": "false"} for e in hidden})
        base_st = dict(st, **{lid: {"Show": "false"}})
        if G.unit(f"{page}_base"):
            G.save(X.render_guide(G.OPEN, root, None, hide=no_legends, scale=G.SCALE,
                                  app_state=base_st), f"{page}_base.png")
            G.emit(f"page {page} {scene} -")
            G.emit(f"row {page} {lid} {len(rows)} {visible}")
        if LOOK:
            rows, max_top = [], 0
        template = root.find("btnA")
        everything = O.all_ids(root, [])
        if not LOOK:
            max_top = max(0, len(rows) - visible)
        for r, text in enumerate(rows):
            for slot in sorted({r - top for top in range(max_top + 1) if 0 <= r - top < visible}):
                rid = f"row{r}s{slot}"
                for s in ("n", "f"):
                    if not G.unit(f"{page}_{rid}_{s}"):
                        continue
                    node = row_node(template, lx, ly + slot * ROW_H, text, rid)
                    root.children.append(node)
                    hide_all = {e: {"Show": "false"} for e in everything}
                    img = X.render_guide(G.OPEN, root, rid if s == "f" else None, hide=layer_hide,
                                         scale=G.SCALE, app_state=hide_all)
                    root.children.remove(node)
                    sub, x0, y0 = O.crop(img)
                    G.save(sub, f"{page}_{rid}_{s}.png")
                    G.emit(f"layer {page} {rid} {s} {x0} {y0}")
        if max_top > 0:
            # the list's scroll ends (its visual's control_ScrollUp / Down),
            # each alone: the list drawn without its template item
            for part, other in (("control_ScrollUp", "control_ScrollDown"),
                                ("control_ScrollDown", "control_ScrollUp")):
                if not G.unit(f"{page}_{part}"):
                    continue
                X.EXTRA_VISUAL_OVERRIDES = {lst.props.get("Visual") or "XuiList": {
                    "control_ListItem": {"Show": "false"}, other: {"Show": "false"}}}
                hide_all = {e: {"Show": "false"} for e in everything if e != lid}
                img = X.render_guide(G.OPEN, root, None, hide=layer_hide, scale=G.SCALE,
                                     app_state=hide_all)
                X.EXTRA_VISUAL_OVERRIDES = {}
                sub, x0, y0 = O.crop(img)
                if sub is not None:
                    G.save(sub, f"{page}_{part}_n.png")
                    G.emit(f"layer {page} {part} n {x0} {y0}")
        if page == "opttile" and not LOOK:
            # PreviewId: the focused row's tile (rows 2..: TILES; row 1, the
            # default background)
            prev = root.find("PreviewId")
            for r in range(1, len(rows)):
                if not G.unit(f"opttile_preview{r}"):
                    continue
                fill = dict(prev.props.get("Fill") or {})
                if r == 1:
                    fill = {}
                else:
                    fill.update({"FillType": "4", "FillColor": "0xffffffff",
                                 "TextureFileName": TILES[r - 2][1]})
                hide_all = {e: {"Show": "false"} for e in everything if e != "PreviewId"}
                hide_all["PreviewId"] = {"Fill": fill} if fill else {}
                img = X.render_guide(G.OPEN, root, None, hide=layer_hide, scale=G.SCALE,
                                     app_state=hide_all)
                sub, x0, y0 = O.crop(img)
                if sub is not None:
                    G.save(sub, f"opttile_preview{r}_n.png")
                    G.emit(f"layer opttile preview{r} n {x0} {y0}")
        only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
        for part, hide in G.LEGEND_PARTS:
            if G.unit(f"{page}_legends_{part}"):
                G.save(X.render_guide(G.OPEN, root, hide=only_legends + hide, scale=G.SCALE),
                       f"{page}_legends_{part}.png")

    # ColorSelect
    scene = "ColorSelect.xui"
    root = copy.deepcopy(X.cached_canvas(X.ART / "xui" / scene).children[0])
    sliders = ["sliderRed", "sliderGreen", "sliderBlue"]
    everything = O.all_ids(root, [])
    if G.unit("optcolor_base"):
        G.save(X.render_guide(G.OPEN, root, None, hide=no_legends, scale=G.SCALE,
                              app_state={**{s: {"Show": "false"} for s in sliders},
                                         "PreviewId": {"Show": "false"}}), "optcolor_base.png")
        G.emit(f"page optcolor {scene} sliderRed")
    if LOOK:
        only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
        for part, hide in G.LEGEND_PARTS:
            G.save(X.render_guide(G.OPEN, root, hide=only_legends + hide, scale=G.SCALE),
                   f"optcolor_legends_{part}.png")
        print("look: bases and legends only")
        return
    # the preview's box and each value's text box (captured)
    if G.unit("optcolor_capture"):
        cap_root = copy.deepcopy(root)
        prev = cap_root.find("PreviewId")
        prev.cls = "XuiImage"
        prev.props["ImagePath"] = "\x01cpreview"
        X.CAPTURE = {}
        X.render_guide(G.OPEN, cap_root, None, hide=no_legends, scale=G.SCALE,
                       app_state={s: {"_columns": {1: f"\x01val_{s}"}} for s in sliders})
        cap, X.CAPTURE = X.CAPTURE, None
        e = cap["cpreview"]
        s_ = e["sx"] / K
        G.emit(f"rect optcolor cpreview {e['tx'] / K:.4f} {e['ty'] / K:.4f} "
               f"{e['w'] * s_:.4f} {e['h'] * s_:.4f}")
        for s in sliders:
            G.emit(O_item(f"val_{s}", cap[f"val_{s}"]))
    # each slider without its bar and value (its label, panel, focus look)
    for s in sliders:
        for state in ("n", "f"):
            if not G.unit(f"optcolor_{s}_{state}"):
                continue
            X.EXTRA_VISUAL_OVERRIDES = {"XuiSlider": {"SliderBody": {"Show": "false"},
                                                      "Text_Slider": {"Show": "false"}}}
            st = {e: {"Show": "false"} for e in everything if e != s}
            img = X.render_guide(G.OPEN, root, s if state == "f" else None, hide=layer_hide,
                                 scale=G.SCALE, app_state=st)
            X.EXTRA_VISUAL_OVERRIDES = {}
            sub, x0, y0 = O.crop(img)
            G.save(sub, f"optcolor_{s}_{state}.png")
            G.emit(f"layer optcolor {s} {state} {x0} {y0}")
    # the bar (SliderBody) at each of its 101 frames, on sliderRed; the
    # overlay places it under the other sliders by their offset (89 units)
    for state in ("n", "f"):
        for frame in range(101):
            if not G.unit(f"optcolor_bar_{state}{frame}"):
                continue
            X.EXTRA_VISUAL_OVERRIDES = {"XuiSlider": {e: {"Show": "false"} for e in (
                "BG_panel", "XuiNineGrid1", "Text_Slider", "text_Label", "Diabled")}}
            st = {e: {"Show": "false"} for e in everything if e != "sliderRed"}
            st["sliderRed"] = {"RangeMin": "0", "RangeMax": "100", "Value": str(frame)}
            img = X.render_guide(G.OPEN, root, "sliderRed" if state == "f" else None,
                                 hide=layer_hide, scale=G.SCALE, app_state=st)
            X.EXTRA_VISUAL_OVERRIDES = {}
            sub, x0, y0 = O.crop(img)
            if sub is None:
                continue
            G.save(sub, f"optcolor_bar_{state}{frame}.png")
            G.emit(f"layer optcolor bar {state}{frame} {x0} {y0}")
    if G.unit("optcolor_sliderpos"):
        for s in sliders:
            y = X.vec(root.find(s).props.get("Position"))[1]
            G.emit(f"sliderpos optcolor {s} {y:.4f}")
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    for part, hide in G.LEGEND_PARTS:
        if G.unit(f"optcolor_legends_{part}"):
            G.save(X.render_guide(G.OPEN, root, hide=only_legends + hide, scale=G.SCALE),
                   f"optcolor_legends_{part}.png")
    lines = G.finish("themes.txt")
    print("\n".join(l for l in lines if not l.startswith("layer")))


def O_item(name, e):
    s = e["sx"] / K
    return (f"text optcolor {name} {e['tx'] / K:.4f} {e['ty'] / K:.4f} {e['w'] * s:.4f} "
            f"{e['h'] * s:.4f} {e['size_px'] * s:.4f} {e['ascent'] * s:.4f} "
            f"{e['line_h'] * s:.4f} {e['style']} {e['color']:08X}")


if __name__ == "__main__":
    G.run(main, "themes.txt")
