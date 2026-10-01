"""gamerprofile.xex's screens for an offline profile, as full-width Guide pages
(OpenType 2), each with xam's gamercard control (gamercrd GamerCard.xur)
hosted in its gamerCard element:

  gpcard   GamerCardScene.xur (XamShowGamerCardUI, mode 0; init 9010CC98:
           meOffline group shown for an offline profile)
  gpedit   808_EditProfile.xur (mode 3 / Edit Gamer Profile; init 90106B80:
           offline group, wait cursor hidden)
  gpeditp  807_EditGamerTile.xur (Gamer Picture; its metapanel text per
           focused button, 90105E28: strings 0x0A, 0x0B, 0x1F, 0x09)
  gppics   809_ChangeGamerTile.xur (the 12 FFFE07D1 pictures in its list,
           90117C24; focus starts on the first)
  gppers   ChangePersonalTile.xur (807's Change Personal Picture, PressPath):
           the same list filler (90117E80) and grid; A writes the personal
           picture (90105990, XamWriteGamerTileEx type 2)

807 (init 90106030) unlinks Take Personal Picture unless XCONFIG_CONSOLE
CAMERA_SETTINGS has 0x4000 (a Vision camera was connected) or XUsbcamGetState
says one is now: on this console it is not there.

The card control (xam 819B6B20 / 819B7BC8) for an offline profile: the
offline base scene; motto, country, top text and status empty. The extended
panel shows on GamerCardScene's big card; 807 sets ShowExtendedPanel false,
and the user's reference frames of 808 / 809 show the basic card only.

Writes into the Guide asset folder:
  <page>_<button>.png   the page with that button focused (text items blank)
  <page>.png            gppics: the page without list items
  gp_cell_normal.png / gp_cell_focus.png   the tile grid's item (btn_tileGrid)
  gamerprofile.txt:
    page <page> <default button>
    text <page> <name> <x> <y> <w> <h> <size> <ascent> <line_h> <style> <color>
    image <page> <name> <x> <y> <w> <h>
    button <page> <id> <up> <down>
    panel <page> <button> <string key>          (807's metapanel text)
    cells <x0> <y0> <dx> <dy> <cols> <count> <tile dx> <tile dy> <cell w> <cell h>
  gamerprofile_strings.txt: <key> <text> (GamerProfile_Custom.xus)
"""
import re

import numpy as np
import skia

import make_guide_assets as G
import xui_render as X
import xus

EMBED = {"gamerCard": "gc_GamerCard.xui"}
STR = xus.load(X.ART / "gamerprofile" / "GamerProfile_Custom.xus")


def card_state(extended):
    s = {
        "offlineBaseScene": {"Show": "true"}, "onlineBaseScene": {"Show": "false"},
        "extendedScene": {"Show": "true" if extended else "false"},
        "gamerTagText": {"NavTabForward": "\x01gamertag"},
        "credText": {"NavTabForward": "\x01cred"},
        "titlesPlayedText": {"NavTabForward": "\x01titles"},
        "achievementsText": {"NavTabForward": "\x01achievements"},
        "gamerTileImage": {"ImagePath": "\x01tile"},
    }
    if extended:
        s.update({
            "titleText": {"NavTabForward": "\x01ext_title"},
            "mottoText": {"NavTabForward": ""}, "countryText": {"NavTabForward": ""},
            "topText1Line": {"NavTabForward": ""}, "bottomText": {"NavTabForward": ""},
        })
        for i in range(1, 5):
            s[f"achievement{i}Image"] = {"ImagePath": f"\x01ach{i}"}
    return s


PAGES = {
    "gpcard": dict(scene="gp_GamerCardScene.xui", group="meOfflineButtonGroup",
                   hide_groups=("meOnlineButtonGroup",), extended=True,
                   extra={"autoSignInButton": {"NavTabForward": "\x01autosignin"}}),
    "gpedit": dict(scene="gp_808_editProfile.xui", group="offlineButtonGroup",
                   hide_groups=("onlineButtonGroup", "waitCursorControl"), extended=False, extra={}),
    "gpeditp": dict(scene="gp_807_EditGamerTile.xui", group=None, hide_groups=("capturePictureButton",),
                    extended=False, extra={"Text2": {"Show": "false"}}),
    "gppics": dict(scene="gp_809_ChangeGamerTile.xui", group=None,
                   hide_groups=("waitCursorControl", "gamerTileList"), extended=False, extra={}),
    "gppers": dict(scene="gp_ChangePersonalTile.xui", group=None,
                   hide_groups=("waitCursorControl", "gamerTileList"), extended=False, extra={}),
}
EDITP_PANEL = {"changeGamerTileButton": 0x0A, "changePersonalTileButton": 0x0B,
               "downloadTilesButton": 0x1F, "capturePictureButton": 0x09}


def buttons_of(root, group):
    node = root.find(group) if group else root
    out = []
    for c in node.children:
        if c.cls in ("XuiButton", "XuiNavButton") and c.id:
            out.append(c)
    return out


def text_line(page, name, e, k):
    s = e["sx"] / k
    if e["kind"] == "text":
        return (f"text {page} {name} {e['tx'] / k:.4f} {e['ty'] / k:.4f} {e['w'] * s:.4f} "
                f"{e['h'] * s:.4f} {e['size_px'] * s:.4f} {e['ascent'] * s:.4f} "
                f"{e['line_h'] * s:.4f} {e['style']} {e['color']:08X}")
    return f"image {page} {name} {e['tx'] / k:.4f} {e['ty'] / k:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f}"


def main():
    G.apply_runtime_state()
    k = X.SUPERSAMPLE * G.SCALE
    lines, strings = [], {}
    for page, p in PAGES.items():
        root = X.cached_canvas(X.ART / "xui" / p["scene"]).children[0]
        state = card_state(p["extended"])
        for h in p["hide_groups"]:
            state[h] = {"Show": "false"}
        state.update(p["extra"])
        btns = ([b for b in buttons_of(root, p["group"]) if b.id not in p["hide_groups"]]
                if page not in ("gppics", "gppers") else [])
        default = (root.find(p["group"]).props.get("DefaultFocus") if p["group"]
                   else root.props.get("DefaultFocus"))
        lines.append(f"page {page} {default}")
        captured = False
        for b in btns or [None]:
            st = {kk: dict(v) for kk, v in state.items()}
            if page == "gpeditp" and b is not None:
                st["Text1"] = {"NavTabForward": STR[EDITP_PANEL[b.id]]}
                lines.append(f"panel {page} {b.id} s{EDITP_PANEL[b.id]:02x}")
            X.CAPTURE = {}
            img = X.render_guide(G.FULL, p["scene"], b.id if b else None, hide=G.PAGE_HIDE,
                                 scale=G.SCALE, app_state=st, embeds=EMBED)
            cap, X.CAPTURE = X.CAPTURE, None
            G.save(img, f"{page}_{b.id}.png" if b else f"{page}.png")
            if not captured:
                for name, e in sorted(cap.items()):
                    lines.append(text_line(page, name, e, k))
                captured = True
            print(page, b.id if b else "-", flush=True)
        ids = {b.id for b in btns}
        for b in btns:
            # an unlinked neighbour is no longer there to move to
            up, down = b.props.get("NavUp"), b.props.get("NavDown")
            lines.append(f"button {page} {b.id} {up if up in ids else '-'} "
                         f"{down if down in ids else '-'}")
    # legends alone (all four scenes: A "Select", B "Back"), for the slides
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    for name, hide in (("a", ("Legend_X", "Legend_Y", "Legend_B")),
                       ("b", ("Legend_X", "Legend_Y", "Legend_A")),
                       ("xy", ("Legend_A", "Legend_B"))):
        G.save(X.render_guide(G.FULL, PAGES["gpcard"]["scene"], hide=only_legends + hide,
                              scale=G.SCALE), f"gp_legends_{name}.png")
    # the tile grid: List_tileGrid's items (btn_tileGrid, 105 x 103 cells) from
    # the list's origin (145, 100), 3 columns in its 446 width: the scene's
    # divider lines (x 240 / 345 / 450, y 195.6 / 298.7 / 401.7) fall in the
    # gaps between the cells' 87 x 83 panels
    skin = X.cached_canvas(X.ART / "xui" / "skin.xui")
    item = next(c for c in skin.children if c.id == "btn_tileGrid")
    for state, name in (("Normal", "gp_cell_normal"), ("Focus", "gp_cell_focus")):
        surf = skia.Surface(int(105 * G.SCALE), int(104 * G.SCALE))
        canvas = surf.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        canvas.scale(G.SCALE, G.SCALE)
        X.Renderer(skin).render_children(canvas, item, X.Ctx(None), X.apply_timelines(item, state))
        surf.makeImageSnapshot().save(str(G.OUT / f"{name}.png"), skia.kPNG)
    presenter = item.find("XuiImagePresenter2")
    tx, ty, _ = X.vec(presenter.props.get("Position"))
    lines.append(f"cells 145 100 105 103 3 12 {tx} {ty} 105 104")
    for key, idx in (("enable", 0x23), ("disable", 0x1D), ("editname", 0x22), ("s43", 0x43),
                     ("s0a", 0x0A), ("s0b", 0x0B), ("s1f", 0x1F), ("s09", 0x09)):
        strings[key] = STR[idx]
    (G.OUT / "gamerprofile.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (G.OUT / "gamerprofile_strings.txt").write_text(
        "\n".join(f"{kk} " + v.replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n")
                  for kk, v in strings.items()) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
