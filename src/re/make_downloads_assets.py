"""Personal Settings > Active Downloads: hud's btnDownloads (9144AB10)
calls XamShowMarketplaceUI(user, 0xA); xam (818EE4D8) sends 0x2100A to
marketplace.xex, which for types 8-0xA skips its Xbox Live checks (90107F34)
and opens ActiveDownloads.xur (CActiveDownloadsScene, half width).

Its list (901133A0) asks XamBackgroundDownloadGetItems; with no downloads it
hides lstDownloads, shows txtNoDownloads ("Your active downloads will be
listed here.") and clears the scene's LegendA (90113028 with no text), so A
is a dimmed icon; B "Back" and X "Cancel All" stay.

Writes into the Guide asset folder:
  optdl_base.png              the page
  dl_legends_a/b/xy.png       its legends
"""
import make_guide_assets as G
import xui_render as X

SCENE = "mkt_ActiveDownloads.xui"
LEGENDS = {"A": "", "B": "Back", "X": "Cancel All", "Y": ""}


def main():
    G.apply_runtime_state()
    no_legends = G.PAGE_HIDE + G.LEGENDS
    state = {"lstDownloads": {"Show": "false"}, "txtNoDownloads": {"Show": "true"}}
    G.save(X.render_guide(G.OPEN, SCENE, None, hide=no_legends, scale=G.SCALE,
                          app_state=state, legends=LEGENDS), "optdl_base.png")
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    for part, hide in G.LEGEND_PARTS:
        G.save(X.render_guide(G.OPEN, SCENE, hide=only_legends + hide, scale=G.SCALE,
                              legends=LEGENDS), f"dl_legends_{part}.png")


if __name__ == "__main__":
    main()
