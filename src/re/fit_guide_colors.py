"""Fit the Guide's runtime colours (panel/blade tint, background dim) to a real frame.

The skin stores a default tint for the panel (HUD_background 'background',
glass.png x 0xff9bb482) and the blade (HUD_blade 'background', x 0xff708499); the
console replaces them with the user's Guide colour. Rendering with two tints and
solving per channel gives the tint that reproduces the real frame's colour.

  python fit_guide_colors.py real.png <origin_x@720p> <origin_y@720p> <px_per_unit@720p> [marked.png]
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import make_guide_assets as A  # noqa: E402
import xui_render as X  # noqa: E402

# canvas-unit sample boxes: plain panel / plain blade, away from menu content
REGIONS = {
    "panel": ("HUD_background", (70, 230, 140, 300)),
    "panel low": ("HUD_background", (70, 420, 140, 480)),
    "blade": ("HUD_blade", (626, 470, 634, 560)),
}


def main():
    real = Image.open(sys.argv[1]).convert("RGB")
    ox, oy, k = float(sys.argv[2]), float(sys.argv[3]), float(sys.argv[4])
    norm = real.height / 720.0
    ra = np.asarray(real, dtype=np.float64)

    def real_box(box):
        x0, y0, x1, y1 = [(v * k + o) * norm for v, o in zip(box, (ox, oy, ox, oy))]
        return (int(x0), int(y0), int(x1), int(y1))

    if len(sys.argv) > 5:
        marked = real.copy()
        d = ImageDraw.Draw(marked)
        for name, (_, box) in REGIONS.items():
            d.rectangle(real_box(box), outline="red", width=2)
        marked.save(sys.argv[5])

    def render(tints, dim_bg):
        X._cache.clear()
        X.TINT_OVERRIDES = tints
        img = X.render_guide(A.OPEN, "MainMenuSignedOut.xui", None, hide=("GamerTag",), scale=1.0)
        rgba = Image.fromarray(img.toarray(colorType=X.skia.kRGBA_8888_ColorType), "RGBA")
        bg = Image.new("RGBA", rgba.size, (dim_bg, dim_bg, dim_bg, 255))
        bg.alpha_composite(rgba)
        return np.asarray(bg.convert("RGB"), dtype=np.float64)

    dim_bg = 40  # the dimmed dashboard behind (the real frame's is ~30-60)
    lo, hi = 128.0, 255.0
    out = {}
    for level in (lo, hi):
        t = int(level)
        tint = 0xFF000000 | (t << 16) | (t << 8) | t
        out[level] = render({"HUD_background": tint, "HUD_blade": tint}, dim_bg)
    for name, (visual, box) in REGIONS.items():
        x0, y0, x1, y1 = box
        a = out[lo][y0:y1, x0:x1].reshape(-1, 3).mean(0)
        b = out[hi][y0:y1, x0:x1].reshape(-1, 3).mean(0)
        rx0, ry0, rx1, ry1 = real_box(box)
        r = ra[ry0:ry1, rx0:rx1].reshape(-1, 3).mean(0)
        tint = lo + (r - a) / np.maximum(b - a, 1e-6) * (hi - lo)
        print(f"{name:10s} ({visual}): real {r.round(1)}  render@128 {a.round(1)} @255 {b.round(1)}"
              f"  -> tint {np.clip(tint, 0, 255).round(0)}")


if __name__ == "__main__":
    main()
