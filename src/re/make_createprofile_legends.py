"""Legends alone for the createprofile pages the Guide frame slides between
(hudbkgnd HalfToFull / FullToHalf move A and B, X and Y stay):
  gts_legends_a / _b / _xy.png   CreateGamerProfile.xur (GamerTagScene, half
                                 width, nothing shown but its legends: B
                                 "Back"; A, X, Y without captions, dimmed)
  kbd_legends_a / _b / _xy.png   vk.xex's Keyboard.xur (full width)
Save Gamer Profile's are in make_congrats_assets.py, AddXboxLive's in
make_addxboxlive_assets.py."""
import make_guide_assets as G
import xui_render as X

ONLY_LEGENDS = G.CONTENT_HIDE + ("AppHostElementId",)
PARTS = (("a", ("Legend_X", "Legend_Y", "Legend_B")),
         ("b", ("Legend_X", "Legend_Y", "Legend_A")),
         ("xy", ("Legend_A", "Legend_B")))


def main():
    G.apply_runtime_state()
    for prefix, frame, scene in (("gts", G.OPEN, "cp_CreateGamerProfile.xui"),
                                 ("kbd", G.FULL, "cp_Keyboard.xui")):
        for name, hide in PARTS:
            G.save(X.render_guide(frame, scene, hide=ONLY_LEGENDS + hide, scale=G.SCALE),
                   f"{prefix}_legends_{name}.png")
            print(prefix, name, flush=True)


if __name__ == "__main__":
    main()
