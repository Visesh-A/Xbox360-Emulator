"""Find where the Guide canvas sits in a screenshot (ours or real console footage).

Template-matches pieces of the Guide that are the same whatever menu is shown
(the XBOX 360 banner logo, the legend buttons), rendered from the console files,
over a range of scales. Reports the screenshot's pixels-per-canvas-unit and the
screen position of canvas (0,0), normalized to a 1280x720 screen.

  python locate_guide.py screenshot.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np

REF = Path(r"G:\Emulators\Xbox360\xenia-dash\guide\ref_menu_open.png")
REF_SCALE = 2.0  # ref px per canvas unit

# canvas-unit boxes of features common to the signed-in and signed-out Guide
FEATURES = {
    # XBOX 360 banner logo (orb + wordmark) inside btnGameBanner
    "banner logo": (232, 521, 268, 55),
    # legend buttons
    "Y button": (181, 624, 28, 28),
    "B button": (528, 623, 28, 28),
    "X button": (165, 655, 28, 28),
    "A button": (541, 654, 28, 28),
}


def edges(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    return cv2.Canny(g, 40, 120)


def main():
    shot = cv2.imread(sys.argv[1])
    ref = cv2.imread(str(REF), cv2.IMREAD_UNCHANGED)
    # put the ref on mid grey so transparent parts don't make edges
    alpha = ref[..., 3:4] / 255.0
    ref_bgr = (ref[..., :3] * alpha + 128 * (1 - alpha)).astype(np.uint8)
    h, w = shot.shape[:2]
    norm = 720.0 / h
    shot_e = edges(shot)
    results = {}
    for name, (x, y, fw, fh) in FEATURES.items():
        tpl = ref_bgr[int(y * REF_SCALE):int((y + fh) * REF_SCALE), int(x * REF_SCALE):int((x + fw) * REF_SCALE)]
        best = None
        for k in np.arange(0.70, 2.2, 0.005) * (h / 770.0):  # screen px per canvas unit
            s = k / REF_SCALE
            t = cv2.resize(tpl, None, fx=s, fy=s, interpolation=cv2.INTER_AREA)
            if t.shape[0] < 8 or t.shape[0] >= h or t.shape[1] >= w:
                continue
            r = cv2.matchTemplate(shot_e, edges(t), cv2.TM_CCORR_NORMED)
            _, v, _, loc = cv2.minMaxLoc(r)
            if best is None or v > best[0]:
                best = (v, k, loc)
        v, k, (lx, ly) = best
        ox, oy = lx - x * k, ly - y * k  # screen position of canvas (0,0)
        results[name] = (k, ox, oy)
        print(f"{name:12s}: score {v:.3f}  {k * norm:.4f} px/unit @720p  canvas origin at "
              f"({ox * norm:7.1f}, {oy * norm:6.1f}) @720p")
    ks = [r[0] for r in results.values()]
    print(f"=> scale {np.median(ks) * norm:.4f} px/unit @720p (ours: {720 / 770:.4f})")


if __name__ == "__main__":
    main()
