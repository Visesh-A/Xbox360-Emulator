"""Message box assets for any text (XamShowMessageBoxUI from a game or the
dashboard): the ErrorHUD with xam's XuiMessageBox<buttons + 1> visual rendered
without its texts and icon, one image per focused button, plus where each text
and the icon go (msgbox.txt). The overlay fills them in at run time with the
console font, using the same rules as xui_render.draw_text.

  msgbox <buttons> <focus> <name> text <x> <y> <w> <h> <size> <ascent>
         <line_h> <style> <color>
  msgbox <buttons> <focus> icon image <x> <y> <w> <h>

Units: canvas units of the image (its left edge is canvas x ERROR_X), size =
font pixel size in those units, color = ARGB."""
import shutil

import make_guide_assets as G
import xui_render as X

ICONS = {"error": "ico_32x_error.png", "warning": "ico_32x_warning.png",
         "alert": "ico_32x_alert.png"}


def find_art(name):
    for root in (X.ART, X.ART.parent / "guide_art_2858", X.ART.parent / "art2858"):
        hits = [p for p in root.rglob("*") if p.name.lower() == name.lower()]
        if hits:
            return hits[0]
    raise SystemExit(f"missing {name}")


def main():
    G.apply_runtime_state()
    lines = []
    k = X.SUPERSAMPLE * G.SCALE  # device pixels per canvas unit
    for n in (1, 2, 3):
        scene = G.message_box("\x01title", "\x01text", [f"\x01button{i}" for i in range(n)])
        scene.find("Icon").props["ImagePath"] = "\x01icon"
        for focus in range(n):
            X.CAPTURE = {}
            img = X.render_guide(G.ERROR, None, f"Button{focus}", hide=("GamerTag",), scale=G.SCALE,
                                 error_scene=scene, size=(G.ERROR_W, 770), origin_x=G.ERROR_X)
            captured, X.CAPTURE = X.CAPTURE, None
            G.save(img, f"msgbox{n}_f{focus}.png")
            for name, e in sorted(captured.items()):
                assert e["skew"] == (0.0, 0.0) and abs(e["sx"] - e["sy"]) < 1e-6, (name, e)
                s = e["sx"] / k
                x, y, w, h = e["tx"] / k, e["ty"] / k, e["w"] * s, e["h"] * s
                if e["kind"] == "text":
                    lines.append(f"msgbox {n} {focus} {name} text {x:.4f} {y:.4f} {w:.4f} {h:.4f} "
                                 f"{e['size_px'] * s:.4f} {e['ascent'] * s:.4f} {e['line_h'] * s:.4f} "
                                 f"{e['style']} {e['color']:08X}")
                else:
                    lines.append(f"msgbox {n} {focus} {name} image {x:.4f} {y:.4f} {w:.4f} {h:.4f}")
            print(n, focus, sorted(captured))
    (G.OUT / "msgbox.txt").write_text("\n".join(lines) + "\n")
    for kind, file in ICONS.items():
        shutil.copy(find_art(file), G.OUT / f"msgbox_icon_{kind}.png")
    font = X.Path(X.__file__).parent / "fonts" / "XenonCLatin_1888.ttf"
    shutil.copy(font, G.OUT / "XenonCLatin.ttf")
    print("wrote", len(lines), "entries")


if __name__ == "__main__":
    main()
