"""The Guide's Select Music (hud action 5: XamAppLoad("minimediaplayer.xex")),
as full-width Guide pages (the app's scenes are OpenType 2, trans_FadeOut /
trans_FadeIn between them), for a console whose hard drive has no music:

  mus579   579_SelectMediaSource (MediaSourceSelectScene, init 90104A58):
           XMPGetMediaSources (0x7002B, xam 81A410F8) lists the sources in
           state 4; the hard drive's slot (81A47198) is in state 4 whenever
           XboxHardwareInfo reports a hard disk, music or not. One row,
           "Hard Drive" (Strings 6, ico_32x_HD_black, 90104260). LegendY
           "Play All Music" while a source row is focused (901047D8); LegendX
           "Return Control to Game" (90104B88).
  mus570   570_MusicLibrary: Play All and the five categories.
  mus572*  572_SelectMediaContainer for Albums / Artists / Saved Playlists /
           Genres, mus576 576_SelectSong for Songs: with nothing found
           (901051F8) the list, count and loading label are hidden, Play All
           disabled and labelNoResultsText shows the category's "No ... found."
           (Strings 8-12); LegendY is cleared (no row, 90106488).
  musplay  BeginPlayback: "Please wait" (with nothing to play the query ends
           at once and the app unloads, back to the Guide, 90108458).

Writes into the Guide asset folder, in options.txt's format:
  <page>_base.png, <page>_<control>_<state>.png, <page>_legends_a/b/xy.png
  music.txt (ctrl lines also carry left / right: <up> <down> <left> <right>)
"""
import copy

import make_guide_assets as G
import make_options_assets as O
import make_signedin_assets as S
import xui_render as X
import xus

STR = xus.load(X.ART / "mmp" / "Strings.xus")
LIB_BUTTONS = ["btnPlayAll", "btnAlbums", "btnArtists", "btnPlaylists", "btnAllSongs", "btnGenres"]
# category page: (scene, header string, "No ... found." string)
CATEGORIES = {
    "mus572al": ("mmp_572_SelectMediaContainer.xui", 0, 8),
    "mus572ar": ("mmp_572_SelectMediaContainer.xui", 1, 9),
    "mus572pl": ("mmp_572_SelectMediaContainer.xui", 17, 11),
    "mus572ge": ("mmp_572_SelectMediaContainer.xui", 5, 10),
    "mus576": ("mmp_576_SelectSong.xui", 28, 12),
}


def legends_of(root, overrides=None):
    lg = {k[-1]: v for k, v in root.props.items() if k.startswith("Legend") and len(k) == 7}
    lg.update(overrides or {})
    return lg


def save_legends(page, scene, legends):
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    for part, hide in G.LEGEND_PARTS:
        G.save(X.render_guide(G.FULL, scene, hide=only_legends + hide, scale=G.SCALE,
                              legends=legends), f"{page}_legends_{part}.png")


def main():
    G.apply_runtime_state()
    lines = []
    no_legends = G.PAGE_HIDE + G.LEGENDS
    layer_hide = G.CONTENT_HIDE + G.LEGENDS

    # Music Sources: listSources shown as its one row (List_standard's
    # control_ListItem visual, btn_standard, 420 x 45) at the list's place
    root = copy.deepcopy(X.cached_canvas(X.ART / "xui" / "mmp_579_SelectMediaSource.xui").children[0])
    lst = root.find("listSources")
    lst.cls = "XuiButton"
    lst.props["Visual"] = "btn_standard"
    lst.props["Height"] = "45.000000"
    lst.props["NavTabForward"] = STR[6]
    lst.props["ImagePath"] = "ico_32x_HD_black.png"
    hide = {"scnDetectedIPod": {"Show": "false"}, "labelNoMediaSourcesText": {"Show": "false"}}
    G.save(X.render_guide(G.FULL, root, None, hide=no_legends, scale=G.SCALE,
                          app_state={**hide, "listSources": {"Show": "false"}}), "mus579_base.png")
    everything = O.all_ids(root, [])
    lines.append("page mus579 mmp_579_SelectMediaSource.xui listSources")
    lines.append("order mus579 listSources")
    lines.append("ctrl mus579 listSources button - -")
    for s in ("n", "f"):
        st = {e: {"Show": "false"} for e in everything if e != "listSources"}
        img = X.render_guide(G.FULL, root, "listSources" if s == "f" else None, hide=layer_hide,
                             scale=G.SCALE, app_state=st)
        sub, x0, y0 = O.crop(img)
        G.save(sub, f"mus579_listSources_{s}.png")
        lines.append(f"layer mus579 listSources {s} {x0} {y0}")
    save_legends("mus579", root, legends_of(root))

    # Music Library: its buttons (sceneButtonContainer's and Play All)
    scene = "mmp_570_MusicLibrary.xui"
    root = X.cached_canvas(X.ART / "xui" / scene).children[0]
    everything = O.all_ids(root, [])
    G.save(X.render_guide(G.FULL, scene, None, hide=no_legends, scale=G.SCALE,
                          app_state={b: {"Show": "false"} for b in LIB_BUTTONS}), "mus570_base.png")
    nav = S.nav_graph(scene, {}, {}, set(LIB_BUTTONS))
    lines.append(f"page mus570 {scene} btnPlayAll")
    lines.append("order mus570 " + " ".join(e for e in everything if e in LIB_BUTTONS))
    for b in LIB_BUTTONS:
        lines.append(f"ctrl mus570 {b} button {nav[b]['up'] or '-'} {nav[b]['down'] or '-'} "
                     f"{nav[b]['left'] or '-'} {nav[b]['right'] or '-'}")
        keep = O.ancestors(root, b) | {b}
        for s in ("n", "f"):
            st = {e: {"Show": "false"} for e in everything if e not in keep}
            img = X.render_guide(G.FULL, scene, b if s == "f" else None, hide=layer_hide,
                                 scale=G.SCALE, app_state=st)
            sub, x0, y0 = O.crop(img)
            G.save(sub, f"mus570_{b}_{s}.png")
            lines.append(f"layer mus570 {b} {s} {x0} {y0}")
    save_legends("mus570", scene, legends_of(root))

    # the categories with nothing found
    for page, (scene, header, none) in CATEGORIES.items():
        root = X.cached_canvas(X.ART / "xui" / scene).children[0]
        st = {"listItems": {"Show": "false"}, "labelItemCount": {"Show": "false"},
              "labelLoadingText": {"Show": "false"}, "labelLoadingAnimation": {"Show": "false"},
              "btnPlayAll": {"Enabled": "false"},
              "labelHeader": {"NavTabForward": STR[header]},
              "labelNoResultsText": {"Show": "true", "NavTabForward": STR[none]}}
        G.save(X.render_guide(G.FULL, scene, None, hide=no_legends, scale=G.SCALE, app_state=st),
               f"{page}_base.png")
        lines.append(f"page {page} {scene} -")
        save_legends(page, scene, legends_of(root, {"Y": ""}))

    # BeginPlayback: "Please wait"
    scene = "mmp_BeginPlayback.xui"
    root = X.cached_canvas(X.ART / "xui" / scene).children[0]
    G.save(X.render_guide(G.FULL, scene, None, hide=no_legends, scale=G.SCALE), "musplay_base.png")
    lines.append(f"page musplay {scene} -")
    save_legends("musplay", scene, legends_of(root))

    (G.OUT / "music.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(l for l in lines if not l.startswith("layer")))


if __name__ == "__main__":
    main()
