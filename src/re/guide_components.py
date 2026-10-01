"""Component-by-component placement check of the open signed-out Guide against
real footage.

Every visible element's box comes from the console's scene files (the menu
MainMenuSignedOut.xur hosted in hudbkgnd's AppHostElementId at (30,15) scale
0.96, the embedded MiniMediaPlayer.xur, and hudbkgnd's own legends/ring/blade).
Each is cut out of our render (ref_menu_open.png, 2 px/unit) and found in the
real frame by normalized cross-correlation of gradient images in a window
around where a global mapping puts it. The mapping (x and y scales separately:
footage is often 4:3 stretched) is fitted robustly to all components, and each
component's residual is reported in canvas units.

  python guide_components.py real.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
import xui_render as X  # noqa: E402

REF = Path(r"G:\Emulators\Xbox360\xenia-dash\guide\ref_menu_open.png")
S = 2.0
HOST = (30.0, 15.0, 0.96)
SKIP = {"artPanel", "grpLiveBanner", "btnA", "btnB", "btnX", "btnY", "tempAdImage",
        "btnDismissVolumeSliderA", "btnDismissVolumeSliderB", "sliderVolume", "imgVolume",
        "imgBatteryIcon", "imgBatteryState", "scnMusic", "sceneControlsContainer",
        "LabelSignIn", "labelProfiles", "imgDefaultGamertile", ""}


def components():
    out = {}
    root = X.load_canvas(X.ART / "xui" / "MainMenuSignedOut.xui").children[0]

    def walk(n, ox, oy):
        for c in n.children:
            p = c.props
            x, y, _ = X.vec(p.get("Position"))
            w, h = X.f(p.get("Width"), 60), X.f(p.get("Height"), 30)
            if c.id not in SKIP and p.get("Show") != "false":
                hx, hy, hs = HOST
                out[c.id] = (hx + hs * (x + ox), hy + hs * (y + oy), hs * w, hs * h)
            if c.id == "scnMusic":
                walk(X.load_canvas(X.ART / "xui" / "MiniMediaPlayer.xui").children[0], x + ox, y + oy)
            else:
                walk(c, x + ox, y + oy)

    walk(root, 0, 0)
    # hudbkgnd (frame 44): legend buttons (icon areas), ring of light, blade top
    out.update({
        "Legend_Y icon": (180 - 1, 621 - 1, 34, 34),
        "Legend_X icon": (164 - 1, 650 - 1, 34, 34),
        "Legend_B icon": (140 + 386, 621 - 1, 34, 34),
        "Legend_A icon": (154 + 386, 650 - 1, 34, 34),
        "Legend_Y text": (180 + 34, 621, 200, 40),
        "Legend_B text": (140 + 250, 621, 136, 40),
        "ROL ring": (617 - 4, 142 - 4, 46, 46),
        "blade top": (583.5, 0, 105, 110),
        "base top edge": (0, 20, 560, 110),
        "base bottom edge": (0, 560, 560, 60),
        "banner logo": (30 + 0.96 * 170, 15 + 0.96 * 525, 0.96 * 350, 0.96 * 65),
    })
    return out


def grad(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).astype(np.float32)
    gx = cv2.Sobel(g, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(g, cv2.CV_32F, 0, 1, ksize=3)
    return cv2.magnitude(gx, gy)


def main():
    real = cv2.imread(sys.argv[1])
    ref = cv2.imread(str(REF), cv2.IMREAD_UNCHANGED)
    a = ref[:, :, 3:4] / 255.0
    ref = (ref[:, :, :3] * a + 40 * (1 - a)).astype(np.uint8)
    rg = grad(cv2.GaussianBlur(real, (3, 3), 0))
    comps = components()
    # initial mapping: px = s*u + t
    sx, sy, tx, ty = [float(v) for v in sys.argv[2:6]] if len(sys.argv) > 5 else (1.93, 1.49, -197.0, -39.0)
    for it in range(4):
        res = {}
        win = 40 if it == 0 else 14
        for name, (x, y, w, h) in comps.items():
            crop = ref[int(y * S):int((y + h) * S), int(x * S):int((x + w) * S)]
            if crop.size == 0:
                continue
            t = cv2.resize(crop, (max(8, int(round(w * sx))), max(8, int(round(h * sy)))), interpolation=cv2.INTER_AREA)
            tg = grad(t)
            px, py = int(round(sx * x + tx)), int(round(sy * y + ty))
            x0, y0 = max(0, px - win), max(0, py - win)
            region = rg[y0:py + tg.shape[0] + win, x0:px + tg.shape[1] + win]
            if region.shape[0] < tg.shape[0] or region.shape[1] < tg.shape[1] or tg.std() == 0:
                continue
            r = cv2.matchTemplate(region, tg, cv2.TM_CCOEFF_NORMED)
            _, v, _, loc = cv2.minMaxLoc(r)
            res[name] = (x, y, w, h, x0 + loc[0], y0 + loc[1], v)
        good = [r for r in res.values() if r[6] > 0.5]
        # least squares for x and y separately, then drop outliers
        for _ in range(3):
            U = np.array([[g[0], 1] for g in good]); P = np.array([g[4] for g in good])
            (sx, tx), *_ = np.linalg.lstsq(U, P, rcond=None)
            V = np.array([[g[1], 1] for g in good]); Q = np.array([g[5] for g in good])
            (sy, ty), *_ = np.linalg.lstsq(V, Q, rcond=None)
            err = [abs(g[4] - (sx * g[0] + tx)) / sx + abs(g[5] - (sy * g[1] + ty)) / sy for g in good]
            lim = max(2.0, 3 * np.median(err))
            good = [g for g, e in zip(good, err) if e <= lim]
    print(f"mapping: x = {sx:.4f} u {tx:+.1f}   y = {sy:.4f} u {ty:+.1f}  (px per canvas unit)")
    print(f"{'component':24s} match   dx     dy   (canvas units, + = real is right/lower)")
    for name, (x, y, w, h, px, py, v) in sorted(res.items(), key=lambda kv: kv[1][1]):
        dx = (px - (sx * x + tx)) / sx
        dy = (py - (sy * y + ty)) / sy
        flag = "" if v > 0.5 else "  (weak match)"
        print(f"{name:24s} {v:5.2f} {dx:+6.1f} {dy:+6.1f}{flag}")


if __name__ == "__main__":
    main()
