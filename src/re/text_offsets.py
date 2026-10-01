"""Vertical offset (real - ours, canvas units) of each Guide text, by
correlating row profiles inside a column range that holds only that text."""
import sys
from pathlib import Path

import cv2
import numpy as np
S = 4


def to_canvas(img, sx, tx, sy, ty):
    M = np.float32([[sx / S, 0, tx], [0, sy / S, ty]])
    return cv2.warpAffine(img, M, (1120 * S, 770 * S), flags=cv2.INTER_LINEAR | cv2.WARP_INVERSE_MAP).mean(axis=2)


def ours_canvas(path):
    ref = cv2.imread(path, cv2.IMREAD_UNCHANGED).astype(float)
    a = ref[..., 3:4] / 255
    return cv2.resize((ref[..., :3] * a + 128 * (1 - a)).mean(axis=2), (1120 * S, 770 * S))


def shift(rc, oc, x0, x1, y0, y1):
    pr = rc[int(y0 * S):int(y1 * S), int(x0 * S):int(x1 * S)].std(axis=1)
    po = oc[int(y0 * S):int(y1 * S), int(x0 * S):int(x1 * S)].std(axis=1)
    pr, po = pr - pr.mean(), po - po.mean()
    best = max(((np.dot(np.roll(po, s), pr) / (np.linalg.norm(po) * np.linalg.norm(pr) + 1e-9), s / S)
                for s in range(-10 * S, 10 * S)), key=lambda t: t[0])
    return best


REF = Path(__file__).resolve().parent / "work" / "reference"

FRAMES = {
    # real-console reference frames (yours: photos or video frames of the Guide)
    "720p signed-in": (str(REF / "real_shot.png"), str(REF / "signedin_ref.png"), None),
    "4:3 signed-out": (str(REF / "4x3_signed_out.png"),
                       str(Path(__file__).resolve().parents[2] / "xenia-dash" / "guide" / "ref_menu_open.png"),
                       (1.9945, -212.5, 1.5309, -48.6)),
}
ITEMS = {
    "720p signed-in": {
        "legend Y 'Xbox Dashboard' 18pt 0x4010 h40": (222, 380, 612, 660),
        "legend B 'Back' 18pt 0x4210 h40": (475, 518, 612, 660),
        "legend A 'Select' 18pt 0x4210 h40": (475, 530, 642, 690),
        "legend X 'Sign Out' 18pt 0x4010 h40": (205, 290, 642, 690),
        "clock 18pt 0x210 h40": (440, 572, 55, 110),
        "Chat and IM (XuiButton 0x4010 h40)": (170, 330, 300, 350),
        "Select Music (btn_single 0x5110 h34)": (175, 340, 455, 500),
        "Gamerscore (btn_Gamercard)": (245, 400, 125, 160),
        "Community label": (170, 320, 200, 245),
    },
    "4:3 signed-out": {
        "legend Y 'Xbox Dashboard' 18pt 0x4010 h40": (222, 380, 612, 660),
        "legend B 'Back' 18pt 0x4210 h40": (475, 518, 612, 660),
        "Sign In (btn_Gamercard)": (255, 340, 115, 150),
        "0 Profiles Found (label)": (255, 440, 150, 185),
        "Create New Profile (btn_oneline-icon 0x5000 h72)": (250, 460, 225, 270),
        "Recover Gamertag 2 lines (0x5000)": (250, 460, 262, 318),
        "Personal Settings (XuiButton 0x4010 h40)": (185, 380, 350, 395),
        "Select Music (btn_single 0x5110 h34)": (190, 335, 455, 500),
    },
}
for frame, (real_path, ours_path, mapping) in FRAMES.items():
    real = cv2.imread(real_path).astype(float)
    if mapping is None:
        k = real.shape[0] / 770
        mapping = (k, -62.6 * k, k, 1.1 * k)
    rc = to_canvas(real, *mapping)
    oc = ours_canvas(ours_path)
    print(frame)
    for name, box in ITEMS[frame].items():
        c, s = shift(rc, oc, *box)
        print(f"  {name:52s} {s:+6.2f}  (corr {c:.2f})")
