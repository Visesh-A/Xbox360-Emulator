"""The on-screen keyboard (vk.xex Keyboard.xur, a full-width Guide page) as
createprofile.xex shows it for a new profile's name: gamertag mode (VKBD 0x4,
vk's key table: keys whose mask lacks 0x4 are disabled, XUI message 0x7D3).

Writes into the Guide asset folder:
  kbd_base.png            the page, no key focused, without its texts
  kbd_focus_<key>.png     each enabled key's focused look (crop, see kbd.txt)
  kbd_caret.png           the edit box's caret (XuiCaret visual), cursor at 0
  kbd.txt                 layout (canvas units of the page, like msgbox.txt):
    text <name> <x> <y> <w> <h> <size> <ascent> <line_h> <style> <color>
        name: title, prompt, edit, cap.<key> (normal), capf.<key> (focused)
    focus <key> <x> <y> <w> <h>       where kbd_focus_<key>.png goes
    caret <dx> <dy> <w> <h>           kbd_caret.png, from the edit text's origin at the cursor
    key <key> <char> <enabled>        char: lowercase code point, 0 = special
    nav <key> <up> <down> <left> <right>   ('-' = none), disabled keys skipped
    default <key>
"""
import json
import os
import re

import numpy as np
import skia

import make_guide_assets as G
import xui_render as X

SCENE = "cp_Keyboard.xui"
MODE = 0x4  # VKBD latin gamertag (createprofile.xex passes 0x20000004)


def key_table():
    keys = json.load(open(X.Path(__file__).parent / "vk_keys.json", encoding="utf-8"))
    return {k["id"]: k for k in keys if not k["id"].startswith("Key.a")}


def scene_keys():
    root = X.cached_canvas(X.ART / "xui" / SCENE).children[0]
    out = {}

    def walk(n):
        if n.id and n.id.startswith("Key."):
            out[n.id] = n
        for c in n.children:
            walk(c)
    walk(root)
    return root, out


def enabled_keys(table, nodes):
    return {k: bool(table[k]["sets"][0]["mask"] & MODE) if k in table else True for k in nodes}


def nav_graph(root, nodes, enabled):
    """XUI: a disabled control is passed over in the same direction."""
    def nav(k, d):
        seen = set()
        cur = k
        while True:
            nxt = nodes[cur].props.get("Nav" + d)
            if not nxt or nxt not in nodes or nxt in seen:
                return None
            if enabled[nxt]:
                return nxt
            seen.add(nxt)
            cur = nxt
    return {k: {d: nav(k, d) for d in ("Up", "Down", "Left", "Right")} for k in nodes if enabled[k]}


def to_array(img):
    return img.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType).astype(np.int16)


def save_crop(arr, box, name):
    x0, y0, x1, y1 = box
    crop = np.ascontiguousarray(arr[y0:y1, x0:x1].astype(np.uint8))
    skia.Image.fromarray(crop, colorType=skia.kRGBA_8888_ColorType,
                         alphaType=skia.kUnpremul_AlphaType).save(str(G.OUT / name), skia.kPNG)


def text_line(name, e, k):
    s = e["sx"] / k
    x, y, w, h = e["tx"] / k, e["ty"] / k, e["w"] * s, e["h"] * s
    return (f"text {name} {x:.4f} {y:.4f} {w:.4f} {h:.4f} {e['size_px'] * s:.4f} "
            f"{e['ascent'] * s:.4f} {e['line_h'] * s:.4f} {e['style']} {e['color']:08X}")


def main():
    G.apply_runtime_state()
    table = key_table()
    root, nodes = scene_keys()
    enabled = enabled_keys(table, nodes)
    state = {k: {"NavTabForward": f"\x01cap.{k}"} for k in nodes}
    for k, on in enabled.items():
        if not on:
            state[k]["Enabled"] = "false"
    state["Text_Header"] = {"NavTabForward": "\x01title"}
    state["XuiText1"] = {"NavTabForward": "\x01prompt"}
    state["XuiEdit1"] = {"NavTabForward": "\x01edit"}
    # the caret belongs to the edit box's visual; drawn by the overlay
    skin = X.cached_canvas(X.ART / "xui" / "skin.xui")
    caret = next(c for c in skin.children if c.id == "scr_Edit").find("Caret")
    k = X.SUPERSAMPLE * G.SCALE
    common = dict(hide=G.PAGE_HIDE, scale=G.SCALE, app_state=state)

    def render(focus, caret_shown):
        caret.props["Show"] = "true" if caret_shown else "false"
        X.CAPTURE = {}
        img = X.render_guide(G.FULL, SCENE, focus, **common)
        cap, X.CAPTURE = X.CAPTURE, None
        return to_array(img), cap

    # KBD_PART "i/n" (render_guide_look.py): only every n-th focused key's
    # image from i, no kbd.txt (the layout does not change with the Guide
    # background); part 0 also makes the base and the caret
    part, parts = (int(v) for v in os.environ.get("KBD_PART", "0/1").split("/"))
    lines = []
    base, cap = render(None, False)
    if part == 0:
        G.save(skia.Image.fromarray(base.astype(np.uint8), colorType=skia.kRGBA_8888_ColorType,
                                    alphaType=skia.kUnpremul_AlphaType), "kbd_base.png")
    for name, e in sorted(cap.items()):
        lines.append(text_line(name, e, k))
    # The caret: skin visual "XuiCaret" (bar + glow, Normal = shown), placed
    # by scr_Edit's Caret element relative to its text presenter.
    edit_visual = next(c for c in skin.children if c.id == "scr_Edit")
    presenter = next(c for c in edit_visual.children if c.cls == "XuiTextPresenter")
    px, py, _ = X.vec(presenter.props.get("Position"))
    cx, cy, _ = X.vec(caret.props.get("Position"))
    visual = next(c for c in skin.children if c.id == "XuiCaret")
    margin = 8
    surf = skia.Surface(int((20 + 2 * margin) * G.SCALE), int((30 + 2 * margin) * G.SCALE))
    canvas = surf.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(G.SCALE, G.SCALE)
    canvas.translate(margin, margin)
    r = X.Renderer(skin)
    r.render_children(canvas, visual, X.Ctx(None), X.apply_timelines(visual, "Normal"))
    arr = to_array(surf.makeImageSnapshot())
    ys, xs = np.nonzero(arr[:, :, 3] > 0)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    if part == 0:
        save_crop(arr, box, "kbd_caret.png")
    # offset of the crop from the text presenter's origin, canvas units
    ox = cx - px + box[0] / G.SCALE - margin
    oy = cy - py + box[1] / G.SCALE - margin
    lines.append(f"caret {ox:.4f} {oy:.4f} {(box[2] - box[0]) / G.SCALE:.4f} "
                 f"{(box[3] - box[1]) / G.SCALE:.4f}")
    for i, key in enumerate(k for k in sorted(nodes) if enabled[k]):
        if i % parts != part:
            continue
        arr, cap = render(key, False)
        diff = np.abs(arr - base).max(axis=2) > 0
        ys, xs = np.nonzero(diff)
        if len(xs):
            box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
            safe = re.sub(r"[^A-Za-z0-9]", lambda m: f"_{ord(m.group()):02X}", key)
            save_crop(arr, box, f"kbd_focus_{safe}.png")
            lines.append(f"focus {key} {box[0] / G.SCALE:.4f} {box[1] / G.SCALE:.4f} "
                         f"{(box[2] - box[0]) / G.SCALE:.4f} {(box[3] - box[1]) / G.SCALE:.4f} {safe}")
        e = cap.get(f"cap.{key}")
        if e:
            lines.append(text_line(f"capf.{key}", e, k))
        print("focus", key, flush=True)
    for key in sorted(nodes):
        ch = table[key]["sets"][0]["text"] if key in table else ""
        code = ord(ch) if ch and len(ch) == 1 else 0
        lines.append(f"key {key} {code} {int(enabled[key])}")
    for key, dirs in sorted(nav_graph(root, nodes, enabled).items()):
        lines.append(f"nav {key} " + " ".join(dirs[d] or "-" for d in ("Up", "Down", "Left", "Right")))
    lines.append(f"default {root.props.get('DefaultFocus')}")
    if parts > 1:
        print("part", part, "of", parts, "done")
        return
    (G.OUT / "kbd.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("wrote", len(lines), "lines")


if __name__ == "__main__":
    main()
