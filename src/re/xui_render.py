"""Minimal XUI (Xbox 360 UI) renderer for the 2006 Guide, using the console's own
scene/skin XML (converted from .xur with XUIHelper) and its extracted artwork.

Supports what the Guide uses: XuiFigure (bezier paths, solid/linear/radial fills,
strokes), images, nine-grids, text,
visuals with anchors, per-state timelines (Normal/Focus/...), opacity/scale/show.
Text uses the console font (fonts/XenonCLatin_1888.ttf).
"""
import math
import xml.etree.ElementTree as ET
from pathlib import Path

import skia

# The 2.0.2858.0 Guide: hud/huduiskin/xam/minimediaplayer with the June 2006
# system update applied (NOTES.md, --dump_patched_system_modules).
ART = Path(__file__).resolve().parent / "guide_art_2858"
IMAGE_DIRS = [ART / "hud", ART / "skin", ART / "shrdres", ART / "xamres", ART / "gamercrd", ART / "mplayer", ART / "mmp",
              ART / "vk", ART / "createprofile"]
DEFAULT_W, DEFAULT_H = 60.0, 30.0
# how XUI BlendMode 1 composites (see draw_figure)
BLEND1 = None  # BlendMode 1 = ordinary source-over: dark groove/separator lines and soft focus highlights on real frames (additive washed them out)
# visual id -> units to move its text presenters up (measured, see make_guide_assets)
TEXT_NUDGE = {}
# The console's GPU decides coverage per sample, so shapes that meet exactly
# leave no seam; skia's per-shape anti-aliasing would (dark ticks where the
# blade's tube pieces join). Shapes are drawn without it at SUPERSAMPLE x the
# requested scale and the result averaged down; text keeps its anti-aliasing.
SUPERSAMPLE = 4
SHAPE_AA = False
# gradients as xam draws them: a 128-texel texture sampled bilinearly
GRADIENT_TEXELS = True
PIVOT_FROM_CENTER = False  # tested: pivot measured from the element center is far worse on real frames
PIVOT_IGNORE = False  # tested on the sharp Image 14: ignoring pivots moves the tube pieces 2 units further off
RADIAL_R = 0.5  # radial position 1 = half the box (tested 0.707: worse)
RADIAL_CIRCLE = False  # radials stretch with the box (tested circular: far worse)
ROT_SIGN = 1  # tested: the opposite direction puts the blade edge up to 60 units off real frames
# experiment: rotated elements without a stored Pivot turn about their center
PIVOT_DEFAULT_CENTER = False  # tested: no better on the real blade edge; XUI default pivot is 0,0
# visual id -> ARGB replacing the skin's tint of its 'background' figure
TINT_OVERRIDES = {}
# The user's Guide background for those same figures: None (the default),
# ("color", ARGB) a solid fill (xam 8191EE98, fill type 1) or ("image", file)
# a texture fill (8191CD00; the tile tinted as the figure's FillColor says)
BACKGROUND = None
# visual id -> {element id: {prop: value}} applied wherever that visual draws
EXTRA_VISUAL_OVERRIDES = {}
# The console's own UI font ("Xbox TC", media:\XenonCLatin.xtt converted by
# xtt_to_ttf.py; the 2858 update's XenonCLatin.xttp only adds CJK/arrows).
FONT = skia.Typeface.MakeFromFile(str(Path(__file__).parent / "fonts" / "XenonCLatin_1888.ttf"))
# XUI point sizes are rendered at 96 dpi (measured on real footage: 1.29-1.34
# px per point across four labels).
POINT_TO_PX = 96 / 72

# Capture mode (for runtime-filled elements such as a message box's texts):
# while CAPTURE is a dict, a text or image path starting with "" is not
# drawn; its box goes into CAPTURE[name] as the final transform (device
# pixels), size and style, so the same layout can be filled in elsewhere.
CAPTURE = None


def capture(canvas, name, w, h, props, kind):
    m = canvas.getTotalMatrix()
    entry = dict(kind=kind, tx=m.getTranslateX(), ty=m.getTranslateY(),
                 sx=m.getScaleX(), sy=m.getScaleY(), skew=(m.getSkewX(), m.getSkewY()),
                 w=w, h=h, props=dict(props))
    if kind == "text":
        size = f(props.get("PointSize"), 14)
        font = skia.Font(FONT, size * POINT_TO_PX)
        metrics = font.getMetrics()
        entry.update(size_px=size * POINT_TO_PX, ascent=-metrics.fAscent,
                     line_h=(metrics.fDescent - metrics.fAscent) + f(props.get("LineSpacingAdjust"), 0),
                     style=int(f(props.get("TextStyle"), 0)),
                     color=color(props.get("TextColor"), 0xFF000000))
    CAPTURE[name] = entry

CONTROL_CLASSES = {"XuiButton", "XuiNavButton", "XuiBackButton", "XuiLabel", "XuiListItem",
                   "XuiCheckbox", "XuiRadioButton", "XuiEdit", "XuiSlider", "XuiControl",
                   "XuiProgressBar", "XuiList", "XuiCommonList"}
SKIP_CLASSES = {"XuiSoundXAudio", "XuiScrollEnd", "XuiCaret"}


# ---------------------------------------------------------------- XML model
class Node:
    def __init__(self, el):
        self.cls = el.tag
        self.props = {}
        self.children = []
        self.timelines = []   # (id, [props], [(time, interp, [values])])
        self.frames = {}      # named frame -> time
        for c in el:
            if c.tag == "Properties":
                self.props = parse_props(c)
            elif c.tag == "Timelines":
                for nf in c.iter("NamedFrame"):
                    self.frames[nf.findtext("Name")] = int(nf.findtext("Time"))
                for tl in c.findall("Timeline"):
                    keys = []
                    for kf in tl.findall("KeyFrame"):
                        keys.append((int(kf.findtext("Time")), int(kf.findtext("Interpolation") or 0),
                                     [p.text or "" for p in kf.findall("Prop")],
                                     (f(kf.findtext("EaseIn")) / 100, f(kf.findtext("EaseOut")) / 100,
                                      f(kf.findtext("EaseScale"), 50.0) / 100)))
                    self.timelines.append((tl.findtext("Id"),
                                           [p.text for p in tl.findall("TimelineProp")], keys))
            else:
                self.children.append(Node(c))
        self.id = self.props.get("Id", "")

    def find(self, id_):
        if self.id == id_:
            return self
        for c in self.children:
            r = c.find(id_)
            if r:
                return r
        return None


def parse_props(el):
    props = {}
    for c in el:
        if len(c) and c.find("Properties") is not None:
            props[c.tag] = parse_props(c.find("Properties"))
        elif c.get("index") is not None:
            props.setdefault(c.tag, {})[int(c.get("index"))] = c.text
        else:
            props[c.tag] = c.text if c.text is not None else ""
    return props


def f(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def vec(v, default=(0.0, 0.0, 0.0)):
    if not v:
        return default
    parts = [float(x) for x in v.split(",")]
    return tuple(parts + [0.0] * (3 - len(parts)))


def color(v, default=0xFFFFFFFF):
    if v is None:
        return default
    return int(v, 16) if v.startswith("0x") else int(v)


def boolean(v, default=True):
    if v is None:
        return default
    return v.strip().lower() == "true"


def load_canvas(path):
    return Node(ET.parse(path).getroot())


# ---------------------------------------------------------------- resources
_images = {}


def image(name):
    if not name:
        return None
    name = name.replace("sharedres://", "").replace("file://", "").split("#")[-1]
    if name in _images:
        return _images[name]
    img = None
    for d in IMAGE_DIRS:
        p = d / name
        if p.exists():
            img = skia.Image.open(str(p))
            break
    if img is None:
        print(f"  [missing image] {name}")
    _images[name] = img
    return img


# ---------------------------------------------------------------- timelines
def apply_timelines(node, state):
    """Return {element_id: {prop: value}} for the steady look of a named state."""
    if not node.frames or state not in node.frames:
        return {}
    # the End frame of a state is its settled look
    t = max(node.frames[state], node.frames.get("End" + state, node.frames[state]))
    return timelines_at(node, t)


def timelines_at(node, t):
    """Property overrides from all timelines of `node` at frame `t`.
    Keyframe interpolation: 0 = linear to the next key, 1 = hold, 2 = eased
    (EaseIn/EaseOut 0-100: slow start / slow end, see ease())."""
    overrides = {}
    for elem_id, props, keys in node.timelines:
        if not keys:
            continue
        prev = keys[0]
        nxt = None
        for k in keys:
            if k[0] <= t:
                prev = k
            else:
                nxt = k
                break
        vals = []
        for i, _ in enumerate(props):
            a = prev[2][i] if i < len(prev[2]) else ""
            if nxt and prev[1] in (0, 2) and nxt[0] != prev[0] and t > prev[0]:
                b = nxt[2][i] if i < len(nxt[2]) else a
                u = (t - prev[0]) / (nxt[0] - prev[0])
                if prev[1] == 2:
                    u = ease(u, *prev[3])
                vals.append(lerp_value(a, b, u))
            else:
                vals.append(a)
        overrides.setdefault(elem_id, {}).update(dict(zip(props, vals)))
    return overrides


def ease(u, ease_in, ease_out, ease_scale=0.5):
    """Eased progress as xam computes it (EaseIn/EaseOut/EaseScale as fractions
    of 100): a cubic Bezier from 0 to 1 with control points (scale, 0) turned by
    (1 - in) pi/4 and (1, 1) - (scale, 0) turned by (1 - out) pi/4 (xam
    8191E1A0), of which the timeline uses only y at the linear progress u
    (8190EA40). In/out 0 is linear; both 100 at scale 0.5 is 3u^2 - 2u^3."""
    import math
    p1 = ease_scale * math.sin((1 - ease_in) * math.pi / 4)
    p2 = 1 - ease_scale * math.sin((1 - ease_out) * math.pi / 4)
    v = 1 - u
    return 3 * p1 * v * v * u + 3 * p2 * v * u * u + u ** 3


def lerp_value(a, b, u):
    try:
        if "," in a:
            av, bv = vec(a), vec(b)
            return ",".join(str(x + (y - x) * u) for x, y in zip(av, bv))
        return str(float(a) + (float(b) - float(a)) * u)
    except ValueError:
        return a


# ---------------------------------------------------------------- drawing
class Ctx:
    def __init__(self, focus=None, text=None, image=None, host=None):
        self.focus = focus
        self.text = text
        self.image = image
        self.host = host
        self.columns = {}          # list item: DataAssociation -> text / image
        self.app = None            # hosted Guide menu scene (HUDScene node)
        self.app_overrides = None
        self.error_app = None      # xam message box scene hosted in ErrorHostElement
        # scene element id -> scene root the console loads into it (the
        # signed-out menu's scnMusic hosts MiniMediaPlayer.xur)
        self.embeds = {}
        self.legends = {}          # 'A'/'B'/'X'/'Y' -> caption
        self.live_text = {}        # element id -> text (clock, gamertag)
        # visual id -> {element id: {prop: value}}; ring of light shows player 1
        self.visual_overrides = {"ringOfLight_Group": {
            "light2": {"Show": "false"}, "light3": {"Show": "false"}, "light4": {"Show": "false"}}}
        # a script's own (e.g. a list visual's template item hidden)
        for vid, elems in EXTRA_VISUAL_OVERRIDES.items():
            for elem, props in elems.items():
                self.visual_overrides.setdefault(vid, {}).setdefault(elem, {}).update(props)


def figure_path(points, w, h):
    vals = [float(x) for x in points.strip(",").split(",") if x != ""]
    n = int(vals[0])
    pts = [vals[1 + 7 * i:1 + 7 * i + 7] for i in range(n)]
    if not pts:
        return None
    xs = [p[0] for p in pts] + [p[2] for p in pts] + [p[4] for p in pts]
    ys = [p[1] for p in pts] + [p[3] for p in pts] + [p[5] for p in pts]
    minx, miny = min(p[0] for p in pts), min(p[1] for p in pts)
    maxx, maxy = max(p[0] for p in pts), max(p[1] for p in pts)
    sx = w / (maxx - minx) if maxx > minx and w > 0 else 1.0
    sy = h / (maxy - miny) if maxy > miny and h > 0 else 1.0
    tr = lambda x, y: ((x - minx) * sx, (y - miny) * sy)
    path = skia.Path()
    path.moveTo(*tr(pts[0][0], pts[0][1]))
    for i in range(1, n + 1):
        a = pts[i - 1]
        b = pts[i % n]
        if i == n:
            break
        path.cubicTo(*tr(a[2], a[3]), *tr(a[4], a[5]), *tr(b[0], b[1]))
    return path, tr


def _xui_flatten(p0, c1, c2, p3, out, tol=0.5, depth=0):
    """xam 81924DB8: a cubic is emitted as its end point once it is flat,
    else split at t = 0.5 (de Casteljau, 81924980) and both halves done.
    Flat (81924858): the chord is shorter than sqrt(tol), or both control
    points lie within sqrt(tol) of the chord's line (squared distances
    compared with tol = 0.5)."""
    dx, dy = p3[0] - p0[0], p3[1] - p0[1]
    d2 = dx * dx + dy * dy
    flat = d2 < tol
    if not flat:
        ln = math.sqrt(d2)
        ux, uy = dx / ln, dy / ln
        worst = 0.0
        for c in (c1, c2):
            t = (c[0] - p0[0]) * ux + (c[1] - p0[1]) * uy
            ex, ey = c[0] - (p0[0] + t * ux), c[1] - (p0[1] + t * uy)
            worst = max(worst, ex * ex + ey * ey)
        flat = worst < tol
    if flat or depth > 16:
        out.append(p3)
        return
    m = lambda a, b: ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
    p01, p12, p23 = m(p0, c1), m(c1, c2), m(c2, p3)
    p012, p123 = m(p01, p12), m(p12, p23)
    mid = m(p012, p123)
    _xui_flatten(p0, p01, p012, mid, out, tol, depth + 1)
    _xui_flatten(mid, p123, p23, p3, out, tol, depth + 1)


def _xui_segments(pts):
    """Segment i runs from point i to point i+1 (the last back to the first)
    with point i's two control points (xam 8192D1D0 / 819422E0)."""
    n = len(pts)
    for i in range(n):
        a, b = pts[i], pts[(i + 1) % n]
        yield (a[0], a[1]), (a[2], a[3]), (a[4], a[5]), (b[0], b[1])


def closed_path(points, w, h, closed):
    """A figure's shape as xam builds it: the points are scaled by the
    element's size over the extent of the flattened outline (8192D280: every
    emitted vertex, so curves that bulge past their anchors count; a zero
    extent scales by 1) with no offset, then each segment is flattened again
    in scaled space (819422E0) and drawn as that polygon, starting at point 0.
    `closed` only matters for the stroke: an open figure's outline leaves out
    the last segment; its fill never does."""
    vals = [float(x) for x in points.strip(",").split(",") if x != ""]
    n = int(vals[0])
    pts = [vals[1 + 7 * i:1 + 7 * i + 7] for i in range(n)]
    if n < 2 or (w <= 0 and h <= 0):
        return None  # degenerate markers (e.g. zero-size nav arrows)
    verts = []
    for seg in _xui_segments(pts):
        _xui_flatten(*seg, verts)
    bw = max(v[0] for v in verts) - min(v[0] for v in verts)
    bh = max(v[1] for v in verts) - min(v[1] for v in verts)
    sx = w / bw if bw != 0 else 1.0
    sy = h / bh if bh != 0 else 1.0
    scaled = [[q[0] * sx, q[1] * sy, q[2] * sx, q[3] * sy, q[4] * sx, q[5] * sy] for q in pts]
    path = skia.Path()
    path.moveTo(scaled[0][0], scaled[0][1])
    segs = list(_xui_segments(scaled))
    if not closed:
        segs = segs[:-1]
    for seg in segs:
        out = []
        _xui_flatten(*seg, out)
        for v in out:
            path.lineTo(*v)
    if closed:
        path.close()
    return path


def gradient_texture_stops(cols, pos, texels=128):
    """xam bakes every gradient into a 128x1 A8R8G8B8 texture (81942110):
    texel i holds the stops' colour at t = i / 128 (81941688 loop: linear per
    channel between the two stops around t, clamped before the first and
    after the last, segments under 1e-4 wide skipped; rounded to bytes). The
    GPU samples it with bilinear filtering from the brush's texcoord (radial
    pixel shader: t = 2 * |texcoord|), which is exactly a gradient with a stop
    at each texel center (i + 0.5) / 128, clamped at both ends."""
    def at(t):
        if t <= pos[0]:
            return cols[0]
        for k in range(len(pos) - 1):
            p0, p1 = pos[k], pos[k + 1]
            if t <= p1:
                u = 1.0 if p1 - p0 < 1e-4 else (t - p0) / (p1 - p0)
                c0, c1 = cols[k], cols[k + 1]
                out = 0
                for sh in (24, 16, 8, 0):
                    a, b = (c0 >> sh) & 255, (c1 >> sh) & 255
                    out |= int(round(a + (b - a) * u)) << sh
                return out
        return cols[-1]
    return ([at(i / texels) for i in range(texels)],
            [(i + 0.5) / texels for i in range(texels)])


def fill_paint(fill, w, h, opacity):
    paint = skia.Paint(AntiAlias=SHAPE_AA)
    ftype = int(f(fill.get("FillType"), 1))
    if ftype == 0:
        return None
    grad = fill.get("Gradient") if isinstance(fill.get("Gradient"), dict) else None
    if ftype in (2, 3) and grad:
        n = int(f(grad.get("NumStops"), 2))
        cols = [color(grad.get("StopColor", {}).get(i, "0xffffffff")) for i in range(n)]
        pos = [f(grad.get("StopPos", {}).get(i), i / max(1, n - 1)) for i in range(n)]
        if GRADIENT_TEXELS:
            cols, pos = gradient_texture_stops(cols, pos)
        # brush transform over the element box, about its center; the translation
        # is in box units (e.g. 0.55 moves a radial center past the corner)
        # Scale works like a texture-coordinate scale: 0.22 stretches the
        # gradient 1/0.22x (this turns the blade's ring bands into the long
        # highlights of a chrome tube).
        scx, scy, _ = vec(fill.get("Scale"), (1.0, 1.0, 1.0))
        scx = 1.0 / scx if scx else 1.0
        scy = 1.0 / scy if scy else 1.0
        # Translation is a texture-coordinate offset too (in box units): the
        # gradient itself moves the other way, by T / Scale.
        tx, ty, _ = vec(fill.get("Translation"))
        # (Button glows need this: Translation 0.57 puts the glow's center on
        # the edge touching the button, so it fades away from it.)
        rot = f(fill.get("Rotation"))

        # The brush maps the element's box, normalized to 0..1 (uv), to
        # gradient coordinates tc = R(rot) * S * (uv - 0.5) + 0.5 + T: scale in
        # the box's axes, then rotate, then offset. Checked on real frames and
        # the skin's own pieces: a 90 degree gradient runs across the box's
        # height with position 0 at the bottom (the Guide header's edge strip:
        # dark line above light); Scale in box axes (the header band's shading);
        # the offset turns with the rotation (the media buttons' four shadow
        # corners are one radial pushed by T = -0.55,-0.55 and rotated 0 / -90
        # / 180 / 90 onto each corner). The shader matrix is the inverse.
        def brush(extra=None):
            m = skia.Matrix()
            m.preScale(max(w, 1e-3), max(h, 1e-3))
            m.preTranslate(0.5, 0.5)
            m.preScale(scx or 1.0, scy or 1.0)
            m.preRotate(-rot)
            m.preTranslate(-0.5 - tx, -0.5 - ty)
            if extra:
                extra(m)
            return m

        radial = ftype == 3 or boolean(grad.get("Radial"), False)
        if radial:
            ry = RADIAL_R * (w / h if RADIAL_CIRCLE and h > 0 else 1.0)
            m2 = brush(lambda mm: (mm.preTranslate(0.5, 0.5), mm.preScale(RADIAL_R, ry)))
            shader = skia.GradientShader.MakeRadial((0, 0), 1.0, cols, pos, skia.TileMode.kClamp, 0, m2)
        else:
            shader = skia.GradientShader.MakeLinear([(0, 0.5), (1, 0.5)], cols, pos,
                                                    skia.TileMode.kClamp, 0, brush())
        paint.setShader(shader)
    elif ftype == 4:
        # texture fill: the tile (e.g. glass.png) tinted by FillColor
        if not fill.get("TextureFileName"):
            # no texture assigned (e.g. the Guide's CustomBanner until a game
            # banner is set): nothing to draw
            return None
        tex = image(fill.get("TextureFileName"))
        tint = color(fill.get("FillColor"), 0xFFFFFFFF)
        if tex is None:
            paint.setColor(tint)
        else:
            paint.setShader(tex.makeShader(skia.TileMode.kRepeat, skia.TileMode.kRepeat,
                                           skia.SamplingOptions(skia.FilterMode.kLinear)))
            paint.setColorFilter(skia.ColorFilters.Blend(tint, skia.BlendMode.kModulate))
    else:
        paint.setColor(color(fill.get("FillColor"), 0xFFFFFFFF))
    paint.setAlphaf(paint.getAlphaf() * opacity)
    return paint


def draw_text(canvas, text, w, h, props, opacity):
    if not text:
        return
    if CAPTURE is not None and text.startswith(""):
        capture(canvas, text[1:], w, h, props, "text")
        return
    size = f(props.get("PointSize"), 14)
    style = int(f(props.get("TextStyle"), 0))
    col = color(props.get("TextColor"), 0xFF000000)  # XUI default: black
    font = skia.Font(FONT, size * POINT_TO_PX)
    font.setEmbolden(bool(style & 0x2))
    paint = skia.Paint(AntiAlias=True, Color=col)
    paint.setAlphaf(paint.getAlphaf() * opacity)
    # TextStyle bits, read off the skin's own visuals: 0x400 centered
    # (XuiLabelCenterJustify), 0x200 right (XuiLabelRightJustify), 0x1000
    # vertically centered (Label_Body_V; btn_oneline-icon's 72-unit box on real
    # footage). 0x10 does not center: legends, the clock and button labels
    # (0x4010 / 0x210) sit at the top of their boxes on two real frames (720p
    # and 480-line), 5.5 units above a centered line. Long lines wrap to the
    # box width.
    lines = []
    for raw in text.replace("\r", "").split("\n"):
        if w > 0 and font.measureText(raw) > w:
            cur = ""
            for word in raw.split(" "):
                trial = (cur + " " + word).strip()
                if font.measureText(trial) > w and cur:
                    lines.append(cur)
                    cur = word
                else:
                    cur = trial
            lines.append(cur)
        else:
            lines.append(raw)
    metrics = font.getMetrics()
    lh = (metrics.fDescent - metrics.fAscent) + f(props.get("LineSpacingAdjust"), 0)
    total = lh * len(lines)
    if style & 0x1000:
        y0 = (h - total) / 2
    else:
        y0 = 0
    for i, line in enumerate(lines):
        tw = font.measureText(line)
        if style & 0x400:
            x = (w - tw) / 2
        elif style & 0x200:
            x = w - tw
        else:
            x = 0
        canvas.drawString(line, x, y0 + i * lh - metrics.fAscent, font, paint)


def draw_image(canvas, img, w, h, size_mode, opacity):
    if img is None:
        return
    paint = skia.Paint(AntiAlias=SHAPE_AA)
    paint.setAlphaf(opacity)
    iw, ih = img.width(), img.height()
    # SizeMode 4 stretches to the box: the Guide's 420x95 HudLive banner in its
    # 414x85 tempAdImage fills it on real footage (a keep-aspect fit would
    # leave it 10% narrower, its left edge 15 units further right)
    if size_mode == 8 and iw and ih:  # keep aspect, fit / center
        s = min(w / iw, h / ih) if w and h else 1.0
        dw, dh = iw * s, ih * s
        rect = skia.Rect.MakeXYWH((w - dw) / 2, (h - dh) / 2, dw, dh)
    elif size_mode == 16:  # native size, centered
        rect = skia.Rect.MakeXYWH((w - iw) / 2, (h - ih) / 2, iw, ih)
    else:
        rect = skia.Rect.MakeWH(w or iw, h or ih)
    canvas.drawImageRect(img, rect, skia.SamplingOptions(skia.FilterMode.kLinear), paint)


def draw_nine_grid(canvas, props, w, h, opacity):
    img = image(props.get("TextureFileName"))
    if img is None:
        return
    l, r = int(f(props.get("LeftOffset"))), int(f(props.get("RightOffset")))
    t, b = int(f(props.get("TopOffset"))), int(f(props.get("BottomOffset")))
    paint = skia.Paint(AntiAlias=SHAPE_AA)
    paint.setAlphaf(opacity)
    iw, ih = img.width(), img.height()
    sxs = [0, l, iw - r, iw]
    sys_ = [0, t, ih - b, ih]
    dxs = [0, l, w - r, w]
    dys = [0, t, h - b, h]
    sampling = skia.SamplingOptions(skia.FilterMode.kLinear)
    no_center = boolean(props.get("NoCenter"), False)
    for row in range(3):
        for col in range(3):
            if no_center and row == 1 and col == 1:
                continue
            src = skia.Rect.MakeLTRB(sxs[col], sys_[row], sxs[col + 1], sys_[row + 1])
            dst = skia.Rect.MakeLTRB(dxs[col], dys[row], dxs[col + 1], dys[row + 1])
            if src.width() > 0 and src.height() > 0 and dst.width() > 0 and dst.height() > 0:
                canvas.drawImageRect(img, src, dst, sampling, paint)


# ---------------------------------------------------------------- tree walk
class Renderer:
    def __init__(self, skin):
        self.skin = skin
        self.visuals = {c.id: c for c in skin.children if c.cls == "XuiVisual"}

    def render_children(self, canvas, node, ctx, overrides, dw=0.0, dh=0.0):
        for c in node.children:
            self.render(canvas, c, ctx, overrides, dw, dh)

    def render(self, canvas, node, ctx, overrides=None, dw=0.0, dh=0.0):
        if node.cls in SKIP_CLASSES:
            return
        props = dict(node.props)
        if overrides and node.id in overrides:
            props.update(overrides[node.id])
        if not boolean(props.get("Show"), True):
            return
        x, y, _ = vec(props.get("Position"))
        # properties equal to their defaults are not stored; XUI elements
        # default to 60x30 (the ring of light's socket image has no Height)
        w, h = f(props.get("Width"), DEFAULT_W), f(props.get("Height"), DEFAULT_H)
        # anchoring inside a visual that is drawn at a different size
        anchor = int(f(props.get("Anchor"), 0))
        if dw or dh:
            if anchor & 1 and anchor & 4:
                w += dw
            elif anchor & 4:
                x += dw
            if anchor & 2 and anchor & 8:
                h += dh
            elif anchor & 8:
                y += dh
        opacity = f(props.get("Opacity"), 1.0)
        sx, sy, _ = vec(props.get("Scale"), (1.0, 1.0, 1.0))
        px, py, _ = vec(props.get("Pivot"))
        angle = 0.0
        rot = props.get("Rotation")
        # Rotation is a quaternion about z; it applies to figures too (the
        # blade's tube is made of short segments rotated about their pivots).
        if rot and rot.count(",") == 3:
            qz, qw = [float(v) for v in rot.split(",")][2:4]
            angle = ROT_SIGN * math.degrees(2 * math.atan2(qz, qw))
        if PIVOT_DEFAULT_CENTER and abs(angle) > 0.01 and props.get("Pivot") is None:
            px, py = w / 2, h / 2
        if PIVOT_IGNORE:
            px, py = 0.0, 0.0
        if PIVOT_FROM_CENTER and abs(angle) > 0.01:
            px, py = px + w / 2, py + h / 2

        canvas.save()
        canvas.translate(x, y)
        if (sx, sy) != (1.0, 1.0) or abs(angle) > 0.01:
            canvas.translate(px, py)
            canvas.rotate(angle)
            canvas.scale(sx or 1.0, sy or 1.0)
            canvas.translate(-px, -py)
        layer = opacity < 0.999
        if layer:
            canvas.saveLayerAlpha(None, int(max(0.0, min(1.0, opacity)) * 255))
        blend = int(f(props.get("BlendMode"), 0))

        cls = node.cls
        if cls == "XuiFigure":
            self.draw_figure(canvas, props, w, h, blend)
        elif cls == "XuiImage":
            path = props.get("ImagePath") or ""
            if CAPTURE is not None and path.startswith(""):
                capture(canvas, path[1:], w, h, props, "image")
            else:
                draw_image(canvas, image(path or None), w, h, int(f(props.get("SizeMode"))), 1.0)
        elif cls == "XuiImagePresenter":
            # presenters keep the image's aspect, centered (the media
            # buttons' icons on real footage)
            path = ctx.columns.get(int(f(props.get("DataAssociation"), 0)), ctx.image)
            if CAPTURE is not None and (path or "").startswith("\x01"):
                capture(canvas, path[1:], w, h, props, "image")
            else:
                draw_image(canvas, image(path), w, h, 8, 1.0)
        elif cls == "XuiNineGrid":
            draw_nine_grid(canvas, props, w, h, 1.0)
        elif cls == "XuiTextPresenter":
            # a list item's columns by the presenter's DataAssociation
            text = ctx.columns.get(int(f(props.get("DataAssociation"), 0)), ctx.text)
            draw_text(canvas, text, w, h, props, 1.0)
        elif cls == "XuiText":
            text = props.get("Text")
            if node.id in ctx.live_text:
                text = ctx.live_text[node.id]
            draw_text(canvas, text, w, h, props, 1.0)
        elif node.id == "AppHostElementId" and ctx.app is not None:
            # the Guide menu scene is hosted here
            self.render_children(canvas, ctx.app, ctx, ctx.app_overrides)
        elif node.id == "ErrorHostElement" and ctx.error_app is not None:
            # xam's message box (XuiMessageBox<n> visual) is hosted here
            self.render_children(canvas, ctx.error_app, ctx, None)
        elif node.id in ctx.embeds:
            self.render(canvas, ctx.embeds[node.id], ctx, overrides)
        elif cls in CONTROL_CLASSES or props.get("Visual"):
            self.draw_control(canvas, node, props, w, h, ctx)
        self.render_children(canvas, node, ctx, overrides)

        if layer:
            canvas.restore()
        canvas.restore()

    def draw_figure(self, canvas, props, w, h, blend):
        pts = props.get("Points")
        if not pts:
            return
        # Closed only concerns the outline (stroke): a fill always follows every
        # segment, the curve back to the first point included. The Guide
        # blade's base shape (Closed false) has its inner edge on that last
        # curve; cutting it with a straight line left a gap the real console
        # doesn't have (its inner edge then runs within 1.5 units of the real
        # one down the whole blade).
        closed = boolean(props.get("Closed"), True)
        path = closed_path(pts, w, h, True)
        if path is None:
            return
        outline = path if closed else closed_path(pts, w, h, False)
        fill = props.get("Fill")
        if isinstance(fill, dict):
            paint = fill_paint(fill, w, h, 1.0)
        elif fill is None and props.get("Closed", "true") == "true":
            paint = None
        else:
            paint = None
        if paint:
            if blend == 1:
                if BLEND1 is not None:
                    paint.setBlendMode(BLEND1)
            canvas.drawPath(path, paint)
        stroke = props.get("Stroke")
        # A stroke group without a width is the authoring tool's default
        # (opaque black, never shown: the Guide's separators on real footage
        # are faint fills, not black lines); every styled stroke sets a width.
        if isinstance(stroke, dict) and "StrokeWidth" in stroke:
            sw = f(stroke.get("StrokeWidth"), 1.0)
            sp = skia.Paint(AntiAlias=SHAPE_AA, Style=skia.Paint.kStroke_Style, StrokeWidth=sw,
                            Color=color(stroke.get("StrokeColor"), 0xFF000000))
            canvas.drawPath(outline, sp)

    def draw_control(self, canvas, node, props, w, h, ctx):
        visual_name = props.get("Visual") or node.cls
        visual = self.visuals.get(visual_name) or self.visuals.get(
            {"XuiNavButton": "XuiButton"}.get(node.cls, ""))
        if visual is None:
            return
        state = "Focus" if ctx.focus and node.id == ctx.focus else "Normal"
        if (node.cls == "XuiListItem" and ctx.focus and ctx.host is not None
                and ctx.host.id == ctx.focus):
            state = "Focus"  # a focused list's item (e.g. btn_spinner's ListItem)
        base_state = state
        # a checked checkbox / radio button: its class's Check states (set
        # through app_state as "_checked")
        if props.get("_checked") == "true":
            state += "Check"
        if props.get("Enabled") == "false":
            state += "Disable"
        if node.id.startswith("Legend_") and not ctx.legends.get(node.id[-1], ""):
            # a button the page gives no action: its dimmed icon without a
            # caption (the legend visual's NormalDisable), as on real 2858
            # footage of the full-width Guide pages
            state = "NormalDisable"
        overrides = apply_timelines(visual, state)
        for elem, extra in ctx.visual_overrides.get(visual.id, {}).items():
            overrides.setdefault(elem, {}).update(extra)
        # the user's Guide colour replaces the skin's default panel/blade tint
        if visual.id in TINT_OVERRIDES:
            bg = visual.find("background")
            fill = dict(bg.props.get("Fill") or {})
            fill["FillColor"] = f"0x{TINT_OVERRIDES[visual.id]:08x}"
            if BACKGROUND is not None and BACKGROUND[0] == "color":
                fill["FillType"] = "1"
                fill["FillColor"] = f"0x{BACKGROUND[1]:08x}"
            elif BACKGROUND is not None and BACKGROUND[0] == "image":
                fill["FillType"] = "4"
                fill["TextureFileName"] = BACKGROUND[1]
            overrides.setdefault("background", {})["Fill"] = fill
        # Text/ImagePath are mislabeled by the v5 schema: NavTabForward holds the
        # caption and Text holds the image for buttons.
        text = props.get("NavTabForward") or props.get("Label") or ""
        if node.id.startswith("Legend_"):
            text = ctx.legends.get(node.id[-1], "")
        img = props.get("Text") if (props.get("Text") or "").lower().endswith(".png") else props.get("ImagePath")
        if visual.id in TEXT_NUDGE:
            for c in visual.children:
                if c.cls == "XuiTextPresenter":
                    cur = overrides.get(c.id, {}).get("Position", c.props.get("Position"))
                    px, py, pz = vec(cur)
                    overrides.setdefault(c.id, {})["Position"] = f"{px},{py - TEXT_NUDGE[visual.id]},{pz}"
        if node.cls == "XuiEdit":
            # an edit's text starts at the top of its box (the message box's
            # MessageText, edit_Error TextStyle 0x110, on real footage), unlike
            # a label's centered line
            for c in visual.children:
                if c.cls == "XuiTextPresenter":
                    style = int(f(c.props.get("TextStyle"), 0)) & ~0x1000
                    overrides.setdefault(c.id, {})["TextStyle"] = str(style)
        vw, vh = f(visual.props.get("Width"), w), f(visual.props.get("Height"), h)
        sub = Ctx(ctx.focus, text, img, node)
        # a control whose class fills its presenters by DataAssociation (set
        # through app_state as "_columns": {n: text or image})
        sub.columns = props.get("_columns") or {}
        body = visual.find("SliderBody") if node.cls == "XuiSlider" else None
        if body is not None:
            # xam's XuiSlider (8192A8D8): SliderBody's timeline shown at the
            # frame between its <state> and End<state> named frames in
            # proportion to (Value - RangeMin) / (RangeMax - RangeMin)
            # (integer maths); the value as decimal text (_itow, 8192DAFC) in
            # the presenter with DataAssociation 1
            lo = int(f(props.get("RangeMin"), 0))
            hi = int(f(props.get("RangeMax"), 100))
            v = int(f(props.get("Value"), lo))
            if base_state in body.frames and "End" + base_state in body.frames and hi > lo:
                a, b = body.frames[base_state], body.frames["End" + base_state]
                frame = a + (v - lo) * (b - a) // (hi - lo)
                for elem, extra in timelines_at(body, frame).items():
                    overrides.setdefault(elem, {}).update(extra)
            sub.columns = dict(sub.columns)
            sub.columns.setdefault(1, str(v))
        self.render_children(canvas, visual, sub, overrides, w - vw, h - vh)


_cache = {}


def cached_canvas(path):
    if path not in _cache:
        _cache[path] = load_canvas(path)
    return _cache[path]


def render_guide(frame, app_scene=None, focus=None, live_text=None, hide=(),
                 size=(1120, 770), app_opacity=None, scale=1.0, legends=None,
                 app_state=None, embeds=None, error_scene=None, origin_x=0.0):
    """The real Guide frame (xam's hudbkgnd.xur) at timeline `frame`, hosting the
    menu scene `app_scene` (a hud.xex scene file name, or an already loaded and
    possibly edited Node) with `focus` on one of its controls. `app_state` is
    what the console sets at run time ({element id: {prop: value}}, for the menu
    and the scenes in `embeds` = {host element id: scene file}). Returns a
    skia.Image of size*scale."""
    skin = cached_canvas(ART / "xui" / "skin.xui")
    r = Renderer(skin)
    frame_canvas = cached_canvas(ART / "xui" / "xam_hudbkgnd.xui")
    root = frame_canvas.children[0]                      # HUDRootScene
    overrides = timelines_at(root, frame)
    for elem in hide:
        overrides.setdefault(elem, {})["Show"] = "false"
    if app_opacity is not None:
        overrides.setdefault("AppHostElementId", {})["Opacity"] = str(app_opacity)
    ctx = Ctx(focus)
    ctx.live_text = live_text or {}
    if app_scene is not None:
        if isinstance(app_scene, Node):
            app_root = app_scene
        else:
            app_root = cached_canvas(ART / "xui" / app_scene).children[0]   # HUDScene
        ctx.app = app_root
        ctx.app_overrides = {k: dict(v) for k, v in (app_state or {}).items()}
        for host, scene_file in (embeds or {}).items():
            ctx.embeds[host] = cached_canvas(ART / "xui" / scene_file).children[0]
        ctx.legends = {k[-1]: v for k, v in app_root.props.items()
                       if k.startswith("Legend") and len(k) == 7}
    if legends is not None:
        ctx.legends = legends
    ctx.error_app = error_scene
    ss = SUPERSAMPLE
    ow, oh = int(size[0] * scale), int(size[1] * scale)
    surface = skia.Surface(ow * ss, oh * ss)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(scale * ss, scale * ss)
    canvas.translate(-origin_x, 0)  # render the canvas region from x = origin_x
    r.render_children(canvas, root, ctx, overrides)
    img = surface.makeImageSnapshot()
    if ss == 1:
        return img
    import numpy as np
    # each output pixel = the rounded mean of its ss x ss samples, summed as
    # integers: (sum + ss*ss/2) // (ss*ss), the same as the float mean + 0.5
    # truncated (the sums are exact), about 4x faster
    b = img.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    b = b.reshape(oh, ss, ow * ss * 4)
    rows = b[:, 0].astype(np.uint16)
    for i in range(1, ss):
        rows += b[:, i]
    rows = rows.reshape(oh, ow, ss, 4)
    a = rows[:, :, 0].copy()
    for i in range(1, ss):
        a += rows[:, :, i]
    a += ss * ss // 2
    a //= ss * ss
    return skia.Image.fromarray(a.astype(np.uint8),
                                colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)


def render_scene(scene_path, out_path, focus=None, extra=None, background=None, size=(1120, 770)):
    skin = load_canvas(ART / "xui" / "skin.xui")
    scene = load_canvas(scene_path)
    r = Renderer(skin)
    surface = skia.Surface(*size)
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    if background:
        background(canvas, r)
    ctx = Ctx(focus)
    for c in scene.children:
        r.render(canvas, c, ctx)
    if extra:
        extra(canvas, r)
    surface.makeImageSnapshot().save(str(out_path), skia.kPNG)
    return r, scene


if __name__ == "__main__":
    import sys
    scene = ART / "xui" / (sys.argv[1] if len(sys.argv) > 1 else "MainMenuSignedOut.xui")
    focus = sys.argv[2] if len(sys.argv) > 2 else None
    out = sys.argv[3] if len(sys.argv) > 3 else "out.png"
    render_scene(scene, out, focus)
    print("wrote", out)
