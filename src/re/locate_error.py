"""Measure where each piece of the xam message box (ErrorHUD) sits in real
footage, against our render (ref_error_exit.png, full canvas at 2 px/unit).

Footage may be 4:3 stretched to 16:9, so x and y scales are searched separately.
Each feature (canvas-unit box) is template-matched on edges; a common
x/y mapping px = s*u + t is fitted and every feature's residual reported.

  python locate_error.py real.png
"""
import sys
from pathlib import Path

import cv2
import numpy as np

REF = Path(r"G:\Emulators\Xbox360\xenia-dash\guide\ref_error_exit.png")
REF_SCALE = 2.0
# canvas-unit boxes (x, y, w, h): ErrorHostElement at (861, 0) + visual coords
H = 861
FEATURES = {
    "warning icon": (H + 65, 61, 32, 32),
    "title": (H + 105, 58, 230, 40),
    "body line 1": (H + 68, 124, 400, 34),
    "Yes": (H + 70, 488, 60, 40),
    "No": (H + 70, 533, 60, 40),
    "Y button": (H + 80 + 2, 623, 30, 30),
    "X button": (H + 59 + 2, 651, 30, 30),
    "B button": (H + 41 + 384, 620, 38, 36),
    "A button": (H + 62 + 384, 649, 38, 36),
    "Back text": (H + 41 + 300, 624, 90, 30),
    "blade top": (800 + 6, 40, 110, 120),
}


def edges(img):
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    g = cv2.GaussianBlur(g, (3, 3), 0)
    return cv2.Canny(g, 30, 90)


def main():
    shot = cv2.imread(sys.argv[1])
    ref = cv2.imread(str(REF), cv2.IMREAD_UNCHANGED)
    alpha = ref[:, :, 3:4] / 255.0
    ref = (ref[:, :, :3] * alpha + 128 * (1 - alpha)).astype(np.uint8)
    se = edges(shot).astype(np.float32)
    best = None
    for sx in np.arange(1.90, 2.25, 0.01):
        for sy in np.arange(1.40, 1.70, 0.01):
            pts = []
            score = 0
            for name, (x, y, w, h) in FEATURES.items():
                crop = ref[int(y * REF_SCALE):int((y + h) * REF_SCALE), int(x * REF_SCALE):int((x + w) * REF_SCALE)]
                t = cv2.resize(crop, (max(4, int(w * sx)), max(4, int(h * sy))), interpolation=cv2.INTER_AREA)
                te = edges(t).astype(np.float32)
                if te.sum() == 0:
                    continue
                r = cv2.matchTemplate(se, te, cv2.TM_CCORR_NORMED)
                _, v, _, loc = cv2.minMaxLoc(r)
                score += v
                pts.append((name, x, y, loc[0], loc[1], v))
            if best is None or score > best[0]:
                best = (score, sx, sy, pts)
    score, sx, sy, pts = best
    tx = np.median([px - sx * x for _, x, _, px, _, _ in pts])
    ty = np.median([py - sy * y for _, _, y, _, py, _ in pts])
    print(f"scale x {sx:.3f} y {sy:.3f} px/unit; canvas origin at ({tx:.1f}, {ty:.1f}) px;"
          f" screen left edge = canvas x {-tx / sx:.1f}")
    for name, x, y, px, py, v in pts:
        print(f"  {name:12s} match {v:.2f}  dx {(px - (sx * x + tx)) / sx:+6.1f}  dy {(py - (sy * y + ty)) / sy:+6.1f} units")


if __name__ == "__main__":
    main()
