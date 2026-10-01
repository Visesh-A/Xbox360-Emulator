"""Pixel-compare an in-emulator capture of the Guide overlay with the reference.

The capture is the Xenia window's client area with --blades_guide_test="<ms>,<page>,black"
(Guide drawn over an opaque black backdrop). The reference is the Guide rendered
straight from the console's XUI files (menu pages: the full hudbkgnd.xur composite,
not the split layers the overlay ships) or composed from the shipped layers
(dialog pages), over black, box-filtered to the capture's size.

  python guide_pixel_compare.py capture.png <btnSignIn|...|exit_no|off_yes...> [clock] [diff.png]

Reports the overall error and, per tile, the pixel shift that best aligns the
capture with the reference (0,0 everywhere = aligned).
"""
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import make_guide_assets as A  # noqa: E402
import xui_render as X  # noqa: E402

CANVAS_W, CANVAS_H = 1120, 770


def skia_to_pil(img):
    return Image.fromarray(img.toarray(colorType=X.skia.kRGBA_8888_ColorType), "RGBA")


def reference(page, clock):
    A.apply_runtime_state()
    if page == "upsell":
        return skia_to_pil(X.render_guide(A.FULL, "InfoUpsellLive.xui", "btnJoinLive", hide=("GamerTag",),
                                          live_text={"DateTimeTextId": clock}, scale=A.SCALE,
                                          app_state=A.DIALOG_STATE))
    if page.startswith("btn"):
        img = skia_to_pil(X.render_guide(A.OPEN, "MainMenuSignedOut.xui", page, hide=("GamerTag",),
                                         live_text={"DateTimeTextId": clock}, scale=A.SCALE,
                                         app_state=A.MENU_STATE, embeds=A.MENU_EMBEDS))
    else:
        # message boxes (exit_yes, off_no, ...): the ErrorHUD at its settled
        # frame, the whole canvas width it reaches
        kind, choice = page.split("_")
        title, text = {"exit": (A.caption("MainMenuSignedOut.xui", "btnY"), A.EXIT_TEXT),
                       "off": (A.caption("Options.xui", "btnTurnOff"), A.OFF_TEXT)}[kind]
        img = skia_to_pil(X.render_guide(
            A.ERROR, None, "Button0" if choice == "yes" else "Button1", hide=("GamerTag",),
            scale=A.SCALE, error_scene=A.message_box(title, text, [A.YES, A.NO]),
            size=(A.ERROR_X + A.ERROR_W, CANVAS_H)))
    return img


def area_matrix(n_in, n_out):
    """Exact area-coverage downscale weights (what the overlay does on load;
    PIL's BOX filter weights whole pixels by their centers instead)."""
    m = np.zeros((n_out, n_in))
    r = n_in / n_out
    for o in range(n_out):
        s, e = o * r, min(n_in, (o + 1) * r)
        for i in range(int(s), int(np.ceil(e))):
            m[o, i] = min(e, i + 1) - max(s, i)
        m[o] /= e - s
    return m


def to_screen(img, size):
    w, h = size
    k = h / CANVAS_H
    black = Image.new("RGBA", img.size, (0, 0, 0, 255))
    black.alpha_composite(img)
    src = np.asarray(black.convert("RGB"), dtype=np.float64)
    ow, oh = round(img.width * k / A.SCALE), round(img.height * k / A.SCALE)
    scaled = np.einsum("oi,ijc->ojc", area_matrix(img.height, oh),
                       np.einsum("pj,ijc->ipc", area_matrix(img.width, ow), src))
    # placed like the overlay: whole-pixel canvas offset
    ox, oy = round(A.CANVAS_OFFSET[0] * k), round(A.CANVAS_OFFSET[1] * k)
    out = np.zeros((h, w, 3), dtype=np.int16)
    sx0, sy0 = max(0, -ox), max(0, -oy)
    dx0, dy0 = max(0, ox), max(0, oy)
    cw, ch = min(ow - sx0, w - dx0), min(oh - sy0, h - dy0)
    out[dy0:dy0 + ch, dx0:dx0 + cw] = np.round(scaled[sy0:sy0 + ch, sx0:sx0 + cw])
    return out, min(w, ox + round(img.width / A.SCALE * k))


def best_shift(cap, ref, r=3):
    best = None
    h, w = ref.shape[:2]
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            a = cap[r + dy:h - r + dy, r + dx:w - r + dx]
            b = ref[r:h - r, r:w - r]
            e = np.abs(a - b).mean()
            if best is None or e < best[0]:
                best = (e, dx, dy)
    return best


def main():
    cap_path, page = sys.argv[1], sys.argv[2]
    if len(sys.argv) > 3 and sys.argv[3] != "-":
        clock = sys.argv[3]
    else:
        t = time.localtime(Path(cap_path).stat().st_mtime)
        clock = f"{t.tm_hour % 12 or 12}:{t.tm_min:02d} {'AM' if t.tm_hour < 12 else 'PM'}"
    cap_img = Image.open(cap_path).convert("RGB")
    cap = np.asarray(cap_img, dtype=np.int16)
    ref, guide_w = to_screen(reference(page, clock), cap_img.size)

    d = np.abs(cap - ref).max(axis=2)[:, :guide_w]
    print(f"capture {cap_img.size[0]}x{cap_img.size[1]}, guide area {guide_w}px wide, clock '{clock}'")
    print(f"mean |diff| {d.mean():.2f}/255   p99 {np.percentile(d, 99):.0f}   max {d.max()}")
    for t in (4, 16, 48):
        print(f"  pixels off by > {t:2d}: {100 * (d > t).mean():.3f}%")
    if guide_w + 2 < cap.shape[1]:
        right = np.abs(cap[:, guide_w + 2:]).max()
        print(f"right of the Guide (should be backdrop black): max {right}")

    # alignment per tile: which shift of the capture best matches the reference
    th, tw = 6, 4
    print(f"tile alignment ({tw}x{th}), 'dx,dy err' (err = mean |diff| at best shift):")
    rows = []
    for ty in range(th):
        row = []
        for tx in range(tw):
            y0, y1 = ty * cap.shape[0] // th, (ty + 1) * cap.shape[0] // th
            x0, x1 = tx * guide_w // tw, (tx + 1) * guide_w // tw
            e, dx, dy = best_shift(cap[y0:y1, x0:x1], ref[y0:y1, x0:x1])
            flat = ref[y0:y1, x0:x1].std() < 2
            row.append("  (flat)   " if flat else f"{dx:+d},{dy:+d} {e:5.2f}")
        rows.append("   ".join(row))
    print("\n".join("  " + r for r in rows))

    if len(sys.argv) > 4:
        diff = np.clip(np.abs(cap - ref) * 4, 0, 255).astype(np.uint8)
        side = np.concatenate([cap.astype(np.uint8), ref.astype(np.uint8), diff], axis=1)
        Image.fromarray(side[:, :]).save(sys.argv[4])
        print("wrote", sys.argv[4])


if __name__ == "__main__":
    main()
