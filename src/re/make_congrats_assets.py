"""createprofile.xex's "Save Gamer Profile" page (Congratulations.xur, a
full-width Guide page) for a new profile: one image per focused button, with
the meta panel the scene's timeline shows for it (Normal = Done,
EndDoneToEditProfile = Customize Profile, EndEditProfileToGetLive = Join Xbox
Live), and where the gamertag and the gamer picture go (congrats.txt):
    text gamertag <x> <y> <w> <h> <size> <ascent> <line_h> <style> <color>
    image tile <x> <y> <w> <h>
    button <id> <image> <up> <down>
and its legends alone (save_legends_a / _b / _xy.png).
"""
import make_guide_assets as G
import xui_render as X

SCENE = "cp_Congratulations.xui"
PANELS = {"doneButton": "doneMetaPanel", "editProfileButton": "editProfileMetaPanel",
          "getLiveButton": "getLiveMetaPanel"}


def raw_text(label):
    """A label's text straight from the scene file (the converter garbles
    U+2022 bullets)."""
    d = (X.ART / "createprofile" / "Congratulations.xur").read_bytes()
    starts = {"getLiveMetaPanel": "When you save your gamer profile and join Xbox Live, you can:"}
    i = d.find(starts[label].encode("utf-16be"))
    out = []
    while True:
        c = int.from_bytes(d[i:i + 2], "big")
        if c == 0 or i + 2 > len(d):
            break
        out.append(chr(c))
        i += 2
    return "".join(out)


def main():
    G.apply_runtime_state()
    root = X.cached_canvas(X.ART / "xui" / SCENE).children[0]
    k = X.SUPERSAMPLE * G.SCALE
    lines = []
    live = raw_text("getLiveMetaPanel")
    # the XUR string runs on to the next one; keep its own lines
    live = live[:live.find("content") + len("content")]
    for focus, panel in PANELS.items():
        # the timeline keys both Opacity and Show
        state = {p: {"Opacity": "1" if p == panel else "0",
                     "Show": "true" if p == panel else "false"} for p in PANELS.values()}
        state["getLiveMetaPanel"]["NavTabForward"] = live
        state["gamerTagText"] = {"NavTabForward": "\x01gamertag"}
        state["gamerTileImage"] = {"ImagePath": "\x01tile"}
        X.CAPTURE = {}
        img = X.render_guide(G.FULL, SCENE, focus, hide=G.PAGE_HIDE, scale=G.SCALE,
                             app_state=state)
        cap, X.CAPTURE = X.CAPTURE, None
        G.save(img, f"congrats_{focus}.png")
        print(focus, sorted(cap))
        if not lines:
            for name, e in sorted(cap.items()):
                s = e["sx"] / k
                x, y, w, h = e["tx"] / k, e["ty"] / k, e["w"] * s, e["h"] * s
                if e["kind"] == "text":
                    lines.append(f"text {name} {x:.4f} {y:.4f} {w:.4f} {h:.4f} {e['size_px'] * s:.4f} "
                                 f"{e['ascent'] * s:.4f} {e['line_h'] * s:.4f} {e['style']} {e['color']:08X}")
                else:
                    lines.append(f"image {name} {x:.4f} {y:.4f} {w:.4f} {h:.4f}")
    # its legends alone, for hudbkgnd HalfToFull (75-119: A and B move from
    # their half positions by +435 / +432, X and Y stay) when AddXboxLive
    # goes back to this page
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    for name, hide in (("a", ("Legend_X", "Legend_Y", "Legend_B")),
                       ("b", ("Legend_X", "Legend_Y", "Legend_A")),
                       ("xy", ("Legend_A", "Legend_B"))):
        G.save(X.render_guide(G.FULL, SCENE, hide=only_legends + hide, scale=G.SCALE),
               f"save_legends_{name}.png")
    for focus in PANELS:
        n = root.find(focus)
        lines.append(f"button {focus} congrats_{focus} {n.props.get('NavUp') or '-'} "
                     f"{n.props.get('NavDown') or '-'}")
    lines.append(f"default {root.props.get('DefaultFocus')}")
    (G.OUT / "congrats.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
