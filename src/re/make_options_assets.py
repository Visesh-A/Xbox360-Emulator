"""hud.xex's Personal Settings (btnOptions' PressPath Options.xur) and the
scenes its buttons open, as half-width Guide pages (OpenType 1, legends
Select / Back, trans_FadeOut / trans_FadeIn between them):

  opt       Options.xur (OptionsScene, init 9144AC80): HUD state 6 (signed
            out) disables Voice, Vibration, Themes and Active Downloads; state
            9 (a profile without an Xbox Live account) disables Online Status
            (message 0x7D3 = the control's Enabled flag, xam 81926524)
  optvib    OptionsController.xur: chkVibration (profile setting 0x10040003)
  optnot    OptionsNotifications.xur: chkShow / chkSound (XNotifyUIGetOptions)
  optonl    OptionsOnline.xur: the four presence radios
  optvoice  OptionsVoice.xur: sliderVolume (0-10), chkMute, three radios

Each page is a base image (everything but its controls) and a layer per
control state, each control rendered alone and cropped (the overlay shrinks a
layer with the base's own sampling grid, so they line up):
  button   n f nd        (normal, focus, normal disabled)
  check    n f nc fc     (the Check states when checked)
  slider   n0..n10 f0..f10

Writes into the Guide asset folder:
  <page>_base.png, <page>_<control>_<state>.png, opt_legends_a/b/xy.png
  options.txt:
    page <page> <scene> <default focus>
    order <page> <control ids in child order>
    ctrl <page> <id> <kind> <up> <down>
    layer <page> <id> <state> <x0> <y0>     (crop origin, image pixels)
"""
import numpy as np
import skia

import make_guide_assets as G
import make_signedin_assets as S
import xui_render as X

PAGES = {
    "opt": ("Options.xui", [("btnOnlineStatus", "button"), ("btnVoice", "button"),
                            ("btnController", "button"), ("btnNotifications", "button"),
                            ("btnPersonalization", "button"), ("btnDownloads", "button"),
                            ("btnTurnOff", "button")]),
    "optvib": ("OptionsController.xui", [("chkVibration", "check")]),
    "optnot": ("OptionsNotifications.xui", [("chkShow", "check"), ("chkSound", "check")]),
    "optonl": ("OptionsOnline.xui", [("radbtnOnline", "check"), ("radbtnAway", "check"),
                                     ("radbtnBusy", "check"), ("radbtnAppearOffline", "check")]),
    "optvoice": ("OptionsVoice.xui", [("sliderVolume", "slider"), ("chkMute", "check"),
                                      ("radbtnPlayHeadset", "check"), ("radbtnPlayTV", "check"),
                                      ("radbtnPlayBoth", "check")]),
}
STATES = {"button": ["n", "f", "nd"], "check": ["n", "f", "nc", "fc"],
          "slider": [f"{s}{v}" for s in "nf" for v in range(11)]}


def all_ids(node, out):
    for c in node.children:
        if c.id:
            out.append(c.id)
        all_ids(c, out)
    return out


def ancestors(root, target):
    path = []

    def walk(n):
        if n.id == target:
            return True
        for c in n.children:
            if walk(c):
                path.append(n.id)
                return True
        return False

    walk(root)
    return set(path)


def crop(img):
    a = img.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
    ys, xs = np.nonzero(a[:, :, 3])
    if len(xs) == 0:
        return None, 0, 0
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    return img.makeSubset(skia.IRect.MakeLTRB(int(x0), int(y0), int(x1), int(y1))), int(x0), int(y0)


def main():
    G.apply_runtime_state()
    lines = []
    no_legends = G.PAGE_HIDE + G.LEGENDS
    layer_hide = G.CONTENT_HIDE + G.LEGENDS
    for page, (scene, ctrls) in PAGES.items():
        root = X.cached_canvas(X.ART / "xui" / scene).children[0]
        ids = [c for c, _ in ctrls]
        everything = all_ids(root, [])
        # the base: the scene without its controls
        base_state = {c: {"Show": "false"} for c in ids}
        G.save(X.render_guide(G.OPEN, scene, None, hide=no_legends, scale=G.SCALE,
                              app_state=base_state), f"{page}_base.png")
        # XUI focus rules (make_signedin_assets.nav_graph), every control enabled
        nav = S.nav_graph(scene, {}, {}, set(ids))
        default = root.props.get("DefaultFocus") or ""
        default = default.split("\\")[-1]
        if default not in ids:
            # a group (radgrpOnlineState) or none: XUI's first focusable child
            default = next((c for c in ids if c in all_ids(root.find(default), [])), ids[0]) \
                if default and root.find(default) is not None else ids[0]
        lines.append(f"page {page} {scene} {default}")
        # the controls in the scene's child order: where XUI's initial focus
        # goes when the default is disabled (nav_graph's focus_into)
        lines.append(f"order {page} " + " ".join(e for e in everything if e in ids))
        for c, kind in ctrls:
            lines.append(f"ctrl {page} {c} {kind} {nav[c]['up'] or '-'} {nav[c]['down'] or '-'}")
            keep = ancestors(root, c) | {c}
            for s in STATES[kind]:
                st = {e: {"Show": "false"} for e in everything if e not in keep}
                props = {}
                if "d" in s[1:]:
                    props["Enabled"] = "false"
                if "c" in s[1:]:
                    props["_checked"] = "true"
                if kind == "slider":
                    props["Value"] = s[1:]
                st[c] = props
                img = X.render_guide(G.OPEN, scene, c if s[0] == "f" else None, hide=layer_hide,
                                     scale=G.SCALE, app_state=st)
                sub, x0, y0 = crop(img)
                if sub is None:
                    continue
                name = f"{page}_{c}_{s}.png"
                G.save(sub, name)
                lines.append(f"layer {page} {c} {s} {x0} {y0}")
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    for part, hide in G.LEGEND_PARTS:
        G.save(X.render_guide(G.OPEN, "Options.xui", hide=only_legends + hide, scale=G.SCALE),
               f"opt_legends_{part}.png")
    (G.OUT / "options.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(l for l in lines if not l.startswith("layer")))


if __name__ == "__main__":
    main()
