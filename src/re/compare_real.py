"""Per-feature offset between a real console frame and our capture, both at 720p.

Crops features that look the same signed in or out out of the real frame and
finds each one in our capture (normalized cross-correlation on edges).

  python compare_real.py real.png ours.png
"""
import sys

import cv2
import numpy as np

# 720p boxes in the REAL frame
FEATURES = {
    "banner logo": (140, 490, 300, 540),
    "Y button":    (107, 585, 137, 614),
    "X button":    (93, 612, 123, 642),
    "B button":    (433, 583, 463, 613),
    "A button":    (433, 610, 463, 640),
    "battery":     (105, 60, 138, 85),
    "ring":        (515, 125, 555, 165),
    "blade top curve": (470, 40, 560, 115),
}


def load(path):
    img = cv2.imread(path)
    return cv2.resize(img, (1280, 720), interpolation=cv2.INTER_AREA)


def edges(img):
    g = cv2.GaussianBlur(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (3, 3), 0)
    return cv2.Canny(g, 30, 90)


def main():
    real, ours = load(sys.argv[1]), load(sys.argv[2])
    re_, oe = edges(real), edges(ours)
    shifts = []
    for name, (x0, y0, x1, y1) in FEATURES.items():
        tpl = re_[y0:y1, x0:x1]
        m = 40
        sx0, sy0 = max(0, x0 - m), max(0, y0 - m)
        area = oe[sy0:y1 + m, sx0:x1 + m]
        r = cv2.matchTemplate(area, tpl, cv2.TM_CCORR_NORMED)
        _, v, _, (lx, ly) = cv2.minMaxLoc(r)
        dx, dy = sx0 + lx - x0, sy0 + ly - y0
        shifts.append((dx, dy))
        print(f"{name:16s}: ours is at {dx:+3d},{dy:+3d} px from the real one  (match {v:.2f})")
    d = np.array(shifts)
    print(f"median offset {np.median(d[:, 0]):+.1f},{np.median(d[:, 1]):+.1f} px @720p")


if __name__ == "__main__":
    main()
