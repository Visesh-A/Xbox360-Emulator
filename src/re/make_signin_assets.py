"""signin.xex's single-pane sign-in (XamShowSigninUIp(user, 1, 0x10000), from
the Guide's Sign In), as a half-width Guide page:

  signin1.xur  "Sign In", Scene_Pane0 (LogonPane) hosting UserList.xur: the
               console's profiles (UserList, List_SignIn rows btn_SignIn:
               gamertag (column 0, entry +0x190), "Xbox Live" if the profile
               has a Live account else empty (1, +0x1B0, str 16), the device
               "HDD"/"MU" (2, +0x230, str 15 / 38) and the gamer picture (3,
               XamReadImage 0xB)); no profiles: the "No Profiles Found" box
  status.xur   after A on a profile (901088D0): the pane shows the chosen
               profile (SelectedProfile) and "Signing in" (txtStarting)

Writes into the Guide asset folder:
  si_list.png, si_status.png      the page (list rows / profile drawn at run time)
  si_legends_a/b/xy.png
  si_row_normal/focus.png         a list row
  signin.txt                      where things go (units)
"""
import skia

import make_guide_assets as G
import xui_render as X
import xus

K = X.SUPERSAMPLE * G.SCALE
STR = xus.load(X.ART / "xui" / "si_strings.xus")


def item(name, e, k=K, dx=0.0, dy=0.0):
    s = e["sx"] / k
    if e["kind"] == "text":
        return (f"text {name} {e['tx'] / k - dx:.4f} {e['ty'] / k - dy:.4f} {e['w'] * s:.4f} "
                f"{e['h'] * s:.4f} {e['size_px'] * s:.4f} {e['ascent'] * s:.4f} "
                f"{e['line_h'] * s:.4f} {e['style']} {e['color']:08X}")
    return f"image {name} {e['tx'] / k - dx:.4f} {e['ty'] / k - dy:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f}"


def main():
    G.apply_runtime_state()
    lines = []
    no_legends = G.PAGE_HIDE + G.LEGENDS
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    # the list page, its header captured to learn the host's transform
    st = {"listUser": {"Show": "false"}, "labHeader": {"NavTabForward": "\x01hdr"}}
    X.CAPTURE = {}
    X.render_guide(G.OPEN, "si_signin1.xui", None, hide=no_legends, scale=G.SCALE, app_state=st,
                   embeds={"Scene_Pane0": "si_UserList.xui"})
    hdr, X.CAPTURE = X.CAPTURE["hdr"], None
    scale = hdr["sx"] / K                     # host scale (units per scene unit)
    ox, oy = hdr["tx"] / K - 144.0 * scale, hdr["ty"] / K - 44.0 * scale  # labHeader at 144,44
    st["labHeader"] = {}
    G.save(X.render_guide(G.OPEN, "si_signin1.xui", None, hide=no_legends, scale=G.SCALE,
                          app_state=st, embeds={"Scene_Pane0": "si_UserList.xui"}), "si_list.png")
    for part, hide in G.LEGEND_PARTS:
        G.save(X.render_guide(G.OPEN, "si_signin1.xui", hide=only_legends + hide, scale=G.SCALE,
                              app_state=st, embeds={"Scene_Pane0": "si_UserList.xui"}),
               f"si_legends_{part}.png")
    # the list: pane 145,233 + UserList scene 4,0 + listUser 0,0; 418x256,
    # rows (control_ListItem) 405x78
    lx, ly = 145.0 + 4.0, 233.0
    lines.append(f"list {ox + lx * scale:.4f} {oy + ly * scale:.4f} {405 * scale:.4f} {78 * scale:.4f} "
                 f"{int(256 // 78)} {scale:.6f}")
    skin = X.cached_canvas(X.ART / "xui" / "skin.xui")
    vis = next(c for c in skin.children if c.id == "btn_SignIn")
    vw, vh = float(vis.props.get("Width")), float(vis.props.get("Height"))
    for state in ("Normal", "Focus"):
        surf = skia.Surface(int(405 * scale * G.SCALE) + 2, int(80 * scale * G.SCALE) + 2)
        canvas = surf.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        canvas.scale(G.SCALE * scale, G.SCALE * scale)
        X.Renderer(skin).render_children(canvas, vis, X.Ctx(None), X.apply_timelines(vis, state),
                                         405 - vw, 78 - vh)
        surf.makeImageSnapshot().save(str(G.OUT / f"si_row_{state.lower()}.png"), skia.kPNG)
        ctx = X.Ctx(None)
        ctx.columns = {0: "\x01l1", 1: "\x01l2", 2: "\x01l3", 3: "\x01img"}
        X.CAPTURE = {}
        X.Renderer(skin).render_children(skia.Surface(8, 8).getCanvas(), vis, ctx,
                                         X.apply_timelines(vis, state), 405 - vw, 78 - vh)
        cap, X.CAPTURE = X.CAPTURE, None
        for n, e in sorted(cap.items()):
            # row units -> canvas units (the host scale)
            e = dict(e)
            e["tx"], e["ty"], e["sx"] = e["tx"] * scale, e["ty"] * scale, e["sx"] * scale
            lines.append(item(f"row_{state.lower()}_{n}", e, k=1.0))
    # the status pane: the chosen profile and "Signing in"
    st = {"SelectedProfile": {"_columns": {0: "\x01st_l1", 1: "\x01st_l2", 2: "\x01st_l3",
                                           3: "\x01st_img"}},
          "txtWaiting": {"Show": "false"}, "btnStart": {"Show": "false"}}
    X.CAPTURE = {}
    img = X.render_guide(G.OPEN, "si_signin1.xui", None, hide=no_legends, scale=G.SCALE, app_state=st,
                         embeds={"Scene_Pane0": "si_status.xui"})
    cap, X.CAPTURE = X.CAPTURE, None
    G.save(img, "si_status.png")
    lines += [item(n, e) for n, e in sorted(cap.items())]
    for i in (6, 9, 12, 15, 16, 38, 53):
        lines.append(f"str {i} {STR[i]}")
    (G.OUT / "signin.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
