"""createprofile.xex's AddXboxLive.xur (a half-width Guide page, OpenType 1):
the large wait cursor and one status line, shown while the profile is saved,
signed in and updated (and, for Join Xbox Live, while the network is checked).

Writes into the Guide asset folder:
  axl_page.png          the half Guide with the page, no status text, no cursor
  axl_legends_a.png / axl_legends_b.png   its A (no caption, dimmed) and B
                        ("Back") legends: they move by -435 / -432 in FullToHalf
  axl_legends_xy.png    its X/Y legends (dimmed; they stay put in FullToHalf)
  axl_spin_<t>.png      the wait cursor (skin visual Loading_Large) at frame t,
                        cropped; frames 36-85 of its loop equal frame 36
  axl.txt               text status <x> <y> <w> <h> <size> <ascent> <line_h> <style> <color>
                        spin <t> <x> <y> <w> <h>     where axl_spin_<t>.png goes
                        spin_frames <n>              loop length (frames)
"""
import numpy as np
import skia

import make_guide_assets as G
import xui_render as X

SCENE = "cp_AddXboxLive.xui"
LOOP = 86        # Loading_Large's timelines end at frame 85 and it loops
LAST_MOVE = 36   # every light holds its value from frame 36 on


def to_array(img):
    return img.toarray(colorType=skia.kRGBA_8888_ColorType,
                       alphaType=skia.kUnpremul_AlphaType).astype(np.int16)


def save_crop(arr, box, name):
    x0, y0, x1, y1 = box
    crop = np.ascontiguousarray(arr[y0:y1, x0:x1].astype(np.uint8))
    skia.Image.fromarray(crop, colorType=skia.kRGBA_8888_ColorType,
                         alphaType=skia.kUnpremul_AlphaType).save(str(G.OUT / name), skia.kPNG)


def main():
    G.apply_runtime_state()
    k = X.SUPERSAMPLE * G.SCALE
    no_legends = G.PAGE_HIDE + G.LEGENDS
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    state = {"statusText": {"NavTabForward": "\x01status"}}

    # the page without the cursor, capturing the status line's box (every
    # part: the cursor's frames are cropped against it)
    X.CAPTURE = {}
    base_img = X.render_guide(G.OPEN, SCENE, None, hide=no_legends, scale=G.SCALE,
                              app_state=dict(state, waitCursorControl={"Show": "false"}))
    cap, X.CAPTURE = X.CAPTURE, None
    if G.unit("page"):
        G.save(base_img, "axl_page.png")
        e = cap["status"]
        s = e["sx"] / k
        G.emit(f"text status {e['tx'] / k:.4f} {e['ty'] / k:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f} "
               f"{e['size_px'] * s:.4f} {e['ascent'] * s:.4f} {e['line_h'] * s:.4f} "
               f"{e['style']} {e['color']:08X}")

    # legends, split: A and B move with the frame in FullToHalf (by -435 and
    # -432 units, hudbkgnd 120-145), X and Y stay
    if G.unit("legends_a"):
        G.save(X.render_guide(G.OPEN, SCENE, hide=only_legends + ("Legend_X", "Legend_Y", "Legend_B"),
                              scale=G.SCALE, app_state=state), "axl_legends_a.png")
    if G.unit("legends_b"):
        G.save(X.render_guide(G.OPEN, SCENE, hide=only_legends + ("Legend_X", "Legend_Y", "Legend_A"),
                              scale=G.SCALE, app_state=state), "axl_legends_b.png")
    if G.unit("legends_xy"):
        G.save(X.render_guide(G.OPEN, SCENE, hide=only_legends + ("Legend_A", "Legend_B"),
                              scale=G.SCALE, app_state=state), "axl_legends_xy.png")

    # the wait cursor at each frame of its loop
    base = to_array(base_img)
    real_apply = X.apply_timelines
    for t in range(LAST_MOVE + 1):
        if not G.unit(f"spin_{t}"):
            continue

        def at_frame(visual, st, t=t):
            if visual.id == "Loading_Large":
                return X.timelines_at(visual, t)
            return real_apply(visual, st)
        X.apply_timelines = at_frame
        try:
            X.CAPTURE = {}
            arr = to_array(X.render_guide(G.OPEN, SCENE, None, hide=no_legends,
                                          scale=G.SCALE, app_state=state))
            X.CAPTURE = None
        finally:
            X.apply_timelines = real_apply
        diff = np.abs(arr - base).max(axis=2) > 0
        ys, xs = np.nonzero(diff)
        if not len(xs):
            G.emit(f"spin {t} 0 0 0 0")
            continue
        box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
        save_crop(arr, box, f"axl_spin_{t}.png")
        G.emit(f"spin {t} {box[0] / G.SCALE:.4f} {box[1] / G.SCALE:.4f} "
               f"{(box[2] - box[0]) / G.SCALE:.4f} {(box[3] - box[1]) / G.SCALE:.4f}")
        print("frame", t, box, flush=True)
    if G.unit("frames"):
        G.emit(f"spin_frames {LOOP}")
    lines = G.finish("axl.txt")
    print("\n".join(lines[:2]))


if __name__ == "__main__":
    G.run(main, "axl.txt")
