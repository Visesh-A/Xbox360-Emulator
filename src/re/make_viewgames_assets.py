"""gamerprofile.xex's View Games screens, as full-width Guide pages:

  820_GameShowcaseMe.xur   "All Games": the titles played (MeGameList, visual
                           List_twoline-icon_RightGS): icon (column 3), name
                           (0, title +0x28), "%1!u! of %2!u! Achievements"
                           (2, 0x27: earned +8, possible +4), gamerscore earned
                           (1, "%u", +0x10); none: noGamesText. Y: its hidden
                           yButton's PressPath GamerscoreMoreInfo.xur
  821-2_GameAchievStatsMe  the title's achievements (AchievementsList,
                           List_twoline-icon_RightGSIcon): name or "Secret"
                           (a locked one without flag 8), "Unlocked %s" /
                           "Unlocked" / "Locked", gamerscore or "--", its
                           picture or unearnedAchievement.png; header = the
                           title, sortOrderText (0x45 by date, Y: 0x44 by
                           gamerscore), achievementCountText (0x7)
  828_AchievDetails        name / gamerscore / description (secret: "Secret",
                           "--", string 5), picture, header = the title

Writes into the Guide asset folder:
  gpgames.png / gpgames_none.png, gpachs.png / gpachs_none.png, gpachd.png,
  gpgsinfo.png
  gp_grow_<v>_<state>.png   a list row of variant v (0 games, 1 achievements)
  viewgames.txt             where the texts and pictures go (units)
"""
import skia

import make_guide_assets as G
import xui_render as X

K = X.SUPERSAMPLE * G.SCALE


def page_item(name, e):
    s = e["sx"] / K
    if e["kind"] == "text":
        return (f"text {name} {e['tx'] / K:.4f} {e['ty'] / K:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f} "
                f"{e['size_px'] * s:.4f} {e['ascent'] * s:.4f} {e['line_h'] * s:.4f} "
                f"{e['style']} {e['color']:08X}")
    return f"image {name} {e['tx'] / K:.4f} {e['ty'] / K:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f}"


def local_item(name, e):
    if e["kind"] == "text":
        return (f"text {name} {e['tx']:.4f} {e['ty']:.4f} {e['w']:.4f} {e['h']:.4f} "
                f"{e['size_px']:.4f} {e['ascent']:.4f} {e['line_h']:.4f} {e['style']} {e['color']:08X}")
    return f"image {name} {e['tx']:.4f} {e['ty']:.4f} {e['w']:.4f} {e['h']:.4f}"


def render(scene, state, name=None, capture=False, focus=None):
    X.CAPTURE = {} if capture else None
    img = X.render_guide(G.FULL, scene, focus, hide=G.PAGE_HIDE, scale=G.SCALE, app_state=state)
    cap, X.CAPTURE = X.CAPTURE, None
    if name:
        G.save(img, name)
    return cap


def main():
    G.apply_runtime_state()
    lines = []
    # 820
    render("gp_820_GameShowcaseMe.xui", {"gameList": {"Show": "false"}, "noGamesText": {"Show": "false"}},
           "gpgames.png")
    render("gp_820_GameShowcaseMe.xui", {"gameList": {"Show": "false"}, "noGamesText": {"Show": "true"}},
           "gpgames_none.png")
    # 821: its texts at run time
    st = {"achievementList": {"Show": "false"}, "noAchievementsText": {"Show": "false"},
          "headerText": {"NavTabForward": "\x01ach_header"},
          "sortOrderText": {"NavTabForward": "\x01ach_sort"},
          "achievementCountText": {"NavTabForward": "\x01ach_count"}}
    cap = render("gp_821-2_GameAchievStatsMe.xui", st, "gpachs.png", capture=True)
    lines += [page_item(n, e) for n, e in sorted(cap.items())]
    st["noAchievementsText"] = {"Show": "true"}
    render("gp_821-2_GameAchievStatsMe.xui", st, "gpachs_none.png", capture=True)
    # 828
    st = {"headerText": {"NavTabForward": "\x01det_header"},
          "achievementTitleText": {"NavTabForward": "\x01det_title"},
          "credText": {"NavTabForward": "\x01det_cred"},
          "achievementDescriptionText": {"NavTabForward": "\x01det_desc"},
          "achievementImage": {"ImagePath": "\x01det_image"}}
    cap = render("gp_828_AchievDetails.xui", st, "gpachd.png", capture=True)
    lines += [page_item(n, e) for n, e in sorted(cap.items())]
    render("gp_GamerscoreMoreInfo.xui", {}, "gpgsinfo.png")
    # list rows: control_ListItem 855x70 with a 855x72 visual (anchored: the
    # visual's children move as the renderer moves them for a 70-high item)
    skin = X.cached_canvas(X.ART / "xui" / "skin.xui")
    for v, vis_name in enumerate(("btn_twoline-icon_RightGS", "btn_twoline-icon_RightGSIcon")):
        vis = next(c for c in skin.children if c.id == vis_name)
        vh = float(vis.props.get("Height"))
        for state in ("Normal", "Focus"):
            surf = skia.Surface(int(855 * G.SCALE), int(72 * G.SCALE))
            canvas = surf.getCanvas()
            canvas.clear(skia.ColorTRANSPARENT)
            canvas.scale(G.SCALE, G.SCALE)
            X.Renderer(skin).render_children(canvas, vis, X.Ctx(None), X.apply_timelines(vis, state),
                                             0.0, 70.0 - vh)
            surf.makeImageSnapshot().save(str(G.OUT / f"gp_grow_{v}_{state.lower()}.png"), skia.kPNG)
            ctx = X.Ctx(None)
            ctx.columns = {0: "\x01l1", 1: "\x01l3", 2: "\x01l2", 3: "\x01img"}
            X.CAPTURE = {}
            X.Renderer(skin).render_children(skia.Surface(8, 8).getCanvas(), vis, ctx,
                                             X.apply_timelines(vis, state), 0.0, 70.0 - vh)
            cap, X.CAPTURE = X.CAPTURE, None
            for n, e in sorted(cap.items()):
                lines.append(local_item(f"row{v}_{state.lower()}_{n}", e))
    # the lists: 70-high items; their visual (855x99) puts the scroll ends at
    # its bottom right (Anchor 12)
    for v, (scene, lid, vis_name) in enumerate((
            ("gp_820_GameShowcaseMe.xui", "gameList", "List_twoline-icon_RightGS"),
            ("gp_821-2_GameAchievStatsMe.xui", "achievementList", "List_twoline-icon_RightGSIcon"))):
        node = X.cached_canvas(X.ART / "xui" / scene).children[0].find(lid)
        x, y, _ = X.vec(node.props.get("Position"))
        w, h = float(node.props.get("Width")), float(node.props.get("Height"))
        lines.append(f"list {v} {x:.4f} {y:.4f} {w:.4f} {h:.4f} 70 {int(h // 70)}")
        vis = next(c for c in skin.children if c.id == vis_name)
        dh = h - float(vis.props.get("Height"))
        for cid, name in (("control_ScrollUp", "up"), ("control_ScrollDown", "down")):
            sx, sy, _ = X.vec(vis.find(cid).props.get("Position"))
            # gp_scroll_<name>.png's origin is 40, 30 units before the control's
            lines.append(f"scroll {v} {name} {x + sx - 40:.4f} {y + sy + dh - 30:.4f} 110 100")
    # the strings the lists and pages use (GamerProfile_Custom.xus)
    import xus
    strs = xus.load(X.ART / "gamerprofile" / "GamerProfile_Custom.xus")
    for i in (0x2, 0x3, 0x4, 0x5, 0x6, 0x7, 0x27, 0x2C, 0x44, 0x45):
        t = strs[i].replace("\\", "\\\\").replace("\r", "").replace("\n", "\\n")
        lines.append(f"str {i:x} {t}")
    # a locked achievement's picture (sharedres://unearnedAchievement.png)
    import shutil
    shutil.copy(X.ART / "shrdres" / "unearnedAchievement.png", G.OUT / "gp_unearned.png")
    (G.OUT / "viewgames.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
