"""Render the Blades Guide overlay images from the console's own Guide files.

Output (next to xenia-dash, loaded by the overlay):
  chrome.png            blade panel + blade edge + ring of light (slides in)
  menu_<focus>.png      signed-out main menu + legends, one per focused item (fades in)
  error_<kind>_<yes|no>.png    xam message boxes in the right-side ErrorHUD
                        (exit to dashboard / turn off), canvas x ERROR_X..
  layout.txt            canvas size and the clock rectangle
The other images are the 1120x770 Guide canvas rendered at SCALE.
"""
import copy
import json
import os
import sys
from pathlib import Path

import skia

sys.path.insert(0, str(Path(__file__).parent))
import xui_render as X  # noqa: E402

# GUIDE_OUT: another folder (a Guide look rendered in the background, see
# render_guide_look.py)
OUT = Path(os.environ.get("GUIDE_OUT")
           or Path(__file__).resolve().parents[2] / "xenia-dash" / "guide")
SCALE = 2.0
OPEN = 44  # ClosedToHalf end frame: Guide fully open
FULL = 193  # ClosedToFull end frame: full-width Guide (e.g. the Xbox Live upsell)
ERROR = 358  # HalfToError end frame: xam message box in the right-side ErrorHUD
# The ErrorHUD group (1093 wide) settles at x 800 and comes from x 1500
# (HalfToError 329-358, ErrorToHalf 359-388, ErrorToClosed 269-298).
ERROR_X, ERROR_W, ERROR_FROM = 800, 1093, 1500
CHROME = ("graphic-base", "graphic-blade", "ROL")
CONTENT_HIDE = CHROME + ("DateTimeTextId", "GamerTag")
# Hidden in every page image: the clock and gamertag (drawn at run time) and
# the ring of light, a layer of its own on top (its place depends on how the
# Guide got there: hudbkgnd rests it at 618 after ClosedToHalf but 617 after
# FullToHalf / ErrorToHalf, 1025 after ClosedToFull but 1026 after HalfToFull,
# and it fades in only at the end of ClosedToHalf).
PAGE_HIDE = ("DateTimeTextId", "GamerTag", "ROL")
# hudbkgnd elements the overlay moves itself, by their keyframes (hud_keys.txt);
# the legends, clock and hosted page are drawn from their own images/text
HUD_KEYS_ONLY = ("Legend_A", "Legend_B", "Legend_X", "Legend_Y", "DateTimeTextId",
                 "AppHostElementId", "GamerTag")
# the legends alone, split as they move (A and B each their own way; X and Y
# together), for a page: <prefix>_legends_a / _b / _xy.png
LEGEND_PARTS = (("a", ("Legend_X", "Legend_Y", "Legend_B")),
                ("b", ("Legend_X", "Legend_Y", "Legend_A")),
                ("xy", ("Legend_A", "Legend_B")))
HUD_PARTS = {"graphic-base": "hud_base", "graphic-blade": "hud_blade", "ROL": "hud_rol"}
LEGENDS = ("Legend_A", "Legend_B", "Legend_X", "Legend_Y")

# Strings from the Guide's own Strings.xus (2858), by the indices hud.xex
# passes to XuiLookupStringTableByIndex before XamShowMessageBox.
import xus  # noqa: E402
STRINGS = xus.load(X.ART / "hud" / "Strings.xus")
EXIT_TEXT = STRINGS[15]  # "This will exit your current session. ..."
OFF_TEXT = STRINGS[44]   # "Are you sure you want to turn off the console?"
YES, NO = STRINGS[50], STRINGS[29]

GUIDE_TINTS = {"HUD_background": 0xFFE5E5E5, "HUD_blade": 0xFFE8E8E8}
# Where the console draws the Guide canvas, measured on real footage with
# locate_guide.py (same scale as fitting the 770-unit canvas to the screen
# height, but 62.6 units further left and 1 lower), and how dark it makes the
# screen behind it (the dashboard drops to ~28% brightness).
CANVAS_OFFSET = (-62.6, 1.1)
BACKGROUND_DIM = 0.72
CLOCK_SAMPLE = "12:34 PM"

# What the console fills in at run time on the signed-out menu, from its own
# strings and the real frames: no profiles on the console ("%d Profiles Found"),
# the mini media player loaded into scnMusic with nothing playing (the playlist
# button reads "Select Music", play/prev/stop/next disabled, the volume slider
# only appears after pressing volume). The battery icon is drawn by the overlay
# (shown only for a wireless controller, at its charge level).
MENU_EMBEDS = {"scnMusic": "MiniMediaPlayer.xui"}
MENU_STATE = {
    "labelProfiles": {"NavTabForward": "0 Profiles Found"},
    "imgBatteryIcon": {"Show": "false"},
    "btnPlaylist": {"NavTabForward": "Select Music"},
    # both real frames show the crossed-arrows icon (mediaInOrderPlayback.png),
    # not the scene's default mediaShufflePlayback.png (parallel arrows)
    "btnPlaybackMode": {"Text": "mediaInOrderPlayback.png"},
    "sliderVolume": {"Show": "false"},
    "imgVolume": {"Show": "false"},
    "btnPlay": {"Enabled": "false"},
    "btnPrev": {"Enabled": "false"},
    "btnStop": {"Enabled": "false"},
    "btnNext": {"Enabled": "false"},
}
DIALOG_STATE = {"imgBatteryIcon": {"Show": "false"}}
BATTERY_ICON = {"menu": (153, 49)}  # imgBatteryIcon, scene units

# Every control that can hold focus on the signed-out menu (enabled ones only).
MENU_FOCUS = ["btnSignIn", "btnNewProfile", "btnRecoverProfile", "btnOptions",
              "btnPlaybackMode", "btnVolume", "btnPlaylist", "btnGameBanner"]


def save(img, name):
    img.save(str(OUT / name), skia.kPNG)
    print("  ", name)


# Parts (setup runs a slow script as several processes at once): the script
# calls unit(name) before each block of work - images and the layout lines
# they give - and does the block only when unit() says it is this part's
# (GUIDE_PART "i/n": every n-th unit from i). emit() keeps a line for the
# block. finish(file) writes the layout file (one part: at once; several:
# each part's lines, then merge(file, n) puts them together in unit order).
# A single run (no GUIDE_PART) does every unit and writes the file directly.
PART, PARTS = (int(v) for v in os.environ.get("GUIDE_PART", "0/1").split("/"))
_units, _unit_lines, _current = [], {}, None


def unit(name):
    global _current
    _units.append(name)
    _current = name if (len(_units) - 1) % PARTS == PART else None
    return _current is not None


def emit(line):
    assert _current is not None, "emit() outside a unit of this part"
    _unit_lines.setdefault(_current, []).append(line)


def finish(file):
    if PARTS == 1:
        lines = [l for u in _units for l in _unit_lines.get(u, [])]
        (OUT / file).write_text("\n".join(lines) + "\n", encoding="utf-8")
        return lines
    (OUT / f"{file}.part{PART}.json").write_text(
        json.dumps({"units": _units, "lines": _unit_lines}), encoding="utf-8")
    return []


def merge(file, parts):
    units, lines = None, {}
    for i in range(parts):
        part = OUT / f"{file}.part{i}.json"
        d = json.loads(part.read_text(encoding="utf-8"))
        assert units in (None, d["units"]), f"{file}: the parts ran different units"
        units = d["units"]
        lines.update(d["lines"])
        part.unlink()
    out = [l for u in units for l in lines.get(u, [])]
    (OUT / file).write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"{file}: {len(out)} lines from {parts} parts")


def run(main, *files):
    """A script's entry: GUIDE_MERGE=n merges its layout files' n parts."""
    if os.environ.get("GUIDE_MERGE"):
        for file in files:
            merge(file, int(os.environ["GUIDE_MERGE"]))
    else:
        main()


def message_box(title, text, buttons):
    """xam's XamShowMessageBox as hud.xex calls it for "Xbox Dashboard" (Y) and
    for turning off the console: the skin visual "XuiMessageBox<n>" with n =
    buttons + 1 (xam appends a hidden cancel button, B), hosted in hudbkgnd's
    ErrorHostElement. Title = the pressed button's caption, icon type 2 =
    ico_32x_warning.png (xam's table: 1 error, 2 warning, 3 alert). The A/B
    legend captions are as on real footage; Y and X are disabled, no caption."""
    skin = X.cached_canvas(X.ART / "xui" / "skin.xui")
    visual = next(c for c in skin.children if c.id == f"XuiMessageBox{len(buttons) + 1}")
    scene = copy.deepcopy(visual.children[0])
    # the presenters show what xam sets on the scene
    title_node = scene.find("Title")
    title_node.cls = "XuiText"
    title_node.props["Text"] = title
    icon = scene.find("Icon")
    icon.cls = "XuiImage"
    icon.props["ImagePath"] = "ico_32x_warning.png"
    scene.find("MessageText").props["NavTabForward"] = text
    for i, caption in enumerate(buttons):
        scene.find(f"Button{i}").props["NavTabForward"] = caption
    scene.find("btnB").props["NavTabForward"] = "Back"
    scene.find("btnA").props["NavTabForward"] = "Select"
    return scene


def caption(scene_file, element):
    """A button's caption in one of the Guide's scenes (NavTabForward = text)."""
    return X.cached_canvas(X.ART / "xui" / scene_file).children[0].find(element).props["NavTabForward"]


def menu_nav_graph():
    """The signed-out menu's focus graph from the scenes' Nav* properties, with
    XUI's rules: a scene hands focus to its DefaultFocus (else its first
    enabled control), disabled controls are passed over in the same direction,
    and a control without a link in some direction defers to its parent scene.
    Returns {item: {"up"|"down"|"left"|"right": item or None}} over MENU_FOCUS."""
    root = X.cached_canvas(X.ART / "xui" / "MainMenuSignedOut.xui").children[0]
    nodes, parent = {}, {}

    def index(n, par):
        nodes[n.id] = n
        parent[n.id] = par
        kids = n.children
        if n.id in MENU_EMBEDS:
            kids = [X.cached_canvas(X.ART / "xui" / MENU_EMBEDS[n.id]).children[0]]
        for c in kids:
            if c.id:
                index(c, n.id)

    index(root, None)

    def prop(i, k):
        return MENU_STATE.get(i, {}).get(k, nodes[i].props.get(k))

    def enabled(i):
        return prop(i, "Enabled") != "false" and prop(i, "Show") != "false"

    def is_scene(i):
        return nodes[i].cls in ("XuiScene", "HUDScene") or i in MENU_EMBEDS

    def focus_into(i):
        if i in MENU_EMBEDS:
            return focus_into(X.cached_canvas(X.ART / "xui" / MENU_EMBEDS[i]).children[0].id)
        if not is_scene(i):
            return i
        d = prop(i, "DefaultFocus")
        if d and enabled(d):
            return focus_into(d)
        for c in nodes[i].children:
            if c.id in nodes and c.id in MENU_FOCUS and enabled(c.id):
                return c.id
        return None

    keys = {"up": "NavUp", "down": "NavDown", "left": "NavLeft", "right": "NavRight"}

    def move(i, direction):
        seen = set()
        cur = i
        while cur is not None:
            target = prop(cur, keys[direction])
            if target is None:
                cur = parent.get(cur)  # defer to the parent scene
                continue
            while target and target not in seen:
                seen.add(target)
                t = focus_into(target)
                if t is not None and enabled(t) and t != i:
                    return t
                if t is None or not is_scene(target):
                    target = prop(target, keys[direction])  # pass over disabled
                else:
                    break
            return None
        return None

    return {i: {d: move(i, d) for d in keys} for i in MENU_FOCUS}


def apply_runtime_state():
    """What the console fills in at run time, matched to real footage of the
    Guide: the Guide colour (the skin's olive/steel tints are only defaults the
    console replaces; the real frame is neutral silver, fitted with
    fit_guide_colors.py) and a full controller battery."""
    X.TINT_OVERRIDES.update(GUIDE_TINTS)
    # The user's Guide background (Personal Settings > Themes; xam 818D5AF8
    # puts it into each Guide frame visual's "background"): GUIDE_BACKGROUND
    # "color:AARRGGBB" (Custom Color: a solid fill) or "image:<file>" (a
    # Guide Background tile: a texture fill); unset, the default.
    bg = os.environ.get("GUIDE_BACKGROUND", "")
    if bg.startswith("color:"):
        X.BACKGROUND = ("color", int(bg[6:], 16))
    elif bg.startswith("image:"):
        X.BACKGROUND = ("image", bg[6:])
    # "Select Music" (btn_single, TextStyle 0x5110) sits 5.5 canvas units
    # higher in its box on two real frames (720p and 480-line) than the skin's
    # layout gives; its box matches. No rule found for it yet: measured
    # correction, in the button's own units (the menu host scales by 0.96).
    X.TEXT_NUDGE["btn_single"] = 5.5 / 0.96
    X.cached_canvas(X.ART / "xui" / "MainMenuSignedOut.xui").children[0] \
        .find("imgBatteryState").props["ImagePath"] = "ico_32x_Battery4.png"


def save_hud_parts():
    """Each moving piece of the Guide frame alone, where it rests in the full
    Guide (frame FULL), and all their keyframes (hud_keys.txt):
        key <id> <time> <interpolation> <ease in> <ease out> <ease scale> <x> <show> <opacity>
    """
    for elem, name in HUD_PARTS.items():
        others = tuple(e for e in CONTENT_HIDE if e != elem)
        if unit("image"):
            save(X.render_guide(FULL, None, hide=others + LEGENDS + ("AppHostElementId", "ErrorHUD"),
                                scale=SCALE), f"{name}.png")
    if not unit("hud_keys.txt"):
        return
    root = X.cached_canvas(X.ART / "xui" / "xam_hudbkgnd.xui").children[0]
    lines = []
    for elem_id, props, keys in root.timelines:
        if elem_id not in HUD_PARTS and elem_id not in HUD_KEYS_ONLY:
            continue
        for t, interp, vals, eases in keys:
            v = dict(zip(props, vals))
            x = X.vec(v.get("Position"))[0]
            show = 0 if v.get("Show") == "false" else 1
            opacity = float(v.get("Opacity") or 1.0)
            ein, eout, escale = (e * 100 for e in eases)
            lines.append(f"key {elem_id} {t} {interp} {ein:g} {eout:g} {escale:g} {x:.6f} {show} {opacity:g}")
    lines.append(f"rest {FULL}")
    (OUT / "hud_keys.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def save_gamertag():
    """hudbkgnd's GamerTag (xam 818D4218 sets it to the signed-in gamertag of
    the Guide's user, empty otherwise): its text box and full transform at
    frame OPEN (rotated 91.2 degrees along the blade; only its x, Show and
    Opacity are keyframed), gamertag.txt:
        gamertag <key x> <tx> <ty> <m00> <m01> <m10> <m11> <w> <h> <size> <ascent> <line_h> <style> <color>
    (m: canvas units per box unit; point (u, v) of the box goes to
    tx + m00 u + m01 v, ty + m10 u + m11 v)."""
    k = X.SUPERSAMPLE * SCALE
    if unit("gamertag.txt"):
        save_gamertag_layout(k)
    # reference: the Guide as xam draws it with a sample gamertag
    if unit("image"):
        save(X.render_guide(OPEN, None, hide=LEGENDS, live_text={"GamerTag": "Player1"}, scale=SCALE),
             "ref_gamertag.png")


def save_gamertag_layout(k):
    X.CAPTURE = {}
    X.render_guide(OPEN, None, hide=LEGENDS, live_text={"GamerTag": "\x01gamertag"}, scale=SCALE)
    e, X.CAPTURE = X.CAPTURE["gamertag"], None
    root = X.cached_canvas(X.ART / "xui" / "xam_hudbkgnd.xui").children[0]
    key_x = next(X.vec(dict(zip(props, vals))["Position"])[0]
                 for eid, props, keys in root.timelines if eid == "GamerTag"
                 for t, _, vals, _ in keys if t == OPEN)
    kx, ky = e["skew"]
    (OUT / "gamertag.txt").write_text(
        f"gamertag {key_x:.6f} {e['tx'] / k:.4f} {e['ty'] / k:.4f} {e['sx'] / k:.6f} {kx / k:.6f} "
        f"{ky / k:.6f} {e['sy'] / k:.6f} {e['w']:.4f} {e['h']:.4f} {e['size_px']:.4f} "
        f"{e['ascent']:.4f} {e['line_h']:.4f} {e['style']} {e['color']:08X}\n", encoding="utf-8")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    apply_runtime_state()
    print("chrome parts and their keyframes")
    save_hud_parts()
    save_gamertag()
    print("chrome")
    if unit("image"):
        save(X.render_guide(OPEN, None, hide=PAGE_HIDE + ("Legend_A", "Legend_B", "Legend_X", "Legend_Y"),
                            scale=SCALE), "chrome.png")
    # Menu/dialog pages (fade in, hide at once on close) and legends (fade in,
    # slide out with the chrome on close) are separate layers, like the timeline.
    # The pages are rendered *on* the chrome, in one pass like the console:
    # some of their lines blend additively onto it, which a separate layer
    # can't reproduce. The overlay crossfades chrome -> page while fading in.
    no_legends = PAGE_HIDE + LEGENDS
    only_legends = CONTENT_HIDE + ("AppHostElementId",)
    menu = dict(app_state=MENU_STATE, embeds=MENU_EMBEDS)
    print("menu")
    for focus in MENU_FOCUS:
        if unit("image"):
            save(X.render_guide(OPEN, "MainMenuSignedOut.xui", focus, hide=no_legends, scale=SCALE, **menu),
                 f"menu_{focus}.png")
    if unit("image"):
        save(X.render_guide(OPEN, "MainMenuSignedOut.xui", hide=only_legends, scale=SCALE, **menu),
             "legends_menu.png")
    for part, hide in LEGEND_PARTS:
        if unit("image"):
            save(X.render_guide(OPEN, "MainMenuSignedOut.xui", hide=only_legends + hide, scale=SCALE,
                                **menu), f"menu_legends_{part}.png")
    print("message boxes (ErrorHUD)")
    # hud.xex: Y "Xbox Dashboard" in a game -> XamShowMessageBox(title = the
    # legend's caption, Strings.xus 15, [Yes, No], focus 1 = No, icon 2);
    # "Shut Down" -> the same with Strings.xus 44. xam shows it in hudbkgnd's
    # ErrorHUD (HalfToError, settled at frame 358: ErrorHUD at x 800).
    boxes = (("exit", caption("MainMenuSignedOut.xui", "btnY"), EXIT_TEXT),
             ("off", caption("Options.xui", "btnTurnOff"), OFF_TEXT))
    for kind, title, text in boxes:
        scene = message_box(title, text, [YES, NO])
        for i, choice in enumerate(("yes", "no")):
            if unit("image"):
                save(X.render_guide(ERROR, None, f"Button{i}", hide=("GamerTag",), scale=SCALE,
                                    error_scene=scene, size=(ERROR_W, 770), origin_x=ERROR_X),
                     f"error_{kind}_{choice}.png")
    # full composite for comparison with real footage
    if unit("image"):
        save(X.render_guide(ERROR, None, "Button1", hide=("GamerTag",), scale=SCALE,
                            error_scene=message_box(*boxes[0][1:], [YES, NO]), size=(ERROR_X + ERROR_W, 770)),
             "ref_error_exit.png")
    # full composites of the open Guide for pixel comparison with the overlay
    if unit("image"):
        save(X.render_guide(OPEN, "MainMenuSignedOut.xui", "btnSignIn", hide=("GamerTag",),
                            live_text={"DateTimeTextId": CLOCK_SAMPLE}, scale=SCALE, **menu), "ref_menu_open.png")
    print("xbox live upsell (full-width guide)")
    # XamShowLiveUpsellUI: InfoUpsellLive.xur opens the Guide full width
    # (OpenType 2: hudbkgnd.xur ClosedToFull 164-193 / FullToClosed 194-223).
    upsell = dict(app_state=DIALOG_STATE)
    if unit("image"):
        save(X.render_guide(FULL, None, hide=PAGE_HIDE + LEGENDS, scale=SCALE), "chrome_full.png")
    if unit("image"):
        save(X.render_guide(FULL, "InfoUpsellLive.xui", "btnJoinLive", hide=no_legends, scale=SCALE, **upsell),
             "upsell_live.png")
    if unit("image"):
        save(X.render_guide(FULL, "InfoUpsellLive.xui", hide=only_legends, scale=SCALE, **upsell),
             "legends_upsell.png")
    for part, hide in LEGEND_PARTS:
        if unit("image"):
            save(X.render_guide(FULL, "InfoUpsellLive.xui", hide=only_legends + hide, scale=SCALE,
                                **upsell), f"upsell_legends_{part}.png")
    if unit("image"):
        save(X.render_guide(FULL, "InfoUpsellLive.xui", "btnJoinLive", hide=("GamerTag",),
                            live_text={"DateTimeTextId": CLOCK_SAMPLE}, scale=SCALE, **upsell),
             "ref_upsell_open.png")
    if not unit("layout.txt"):
        return
    print("battery icons")
    battery_lines = make_battery_icons()
    print("clock atlas")
    clock_lines = make_clock_atlas()
    nav = menu_nav_graph()
    # focus graph: "menu <item> <up> <down> <left> <right>" ('-' = none), the
    # first item being the scene's DefaultFocus
    menu_lines = "".join(
        f"menu {item} " + " ".join(nav[item][d] or "-" for d in ("up", "down", "left", "right")) + "\n"
        for item in MENU_FOCUS)
    # layout of the Guide canvas and its animation (hudbkgnd.xur ClosedToHalf):
    # chrome slides in over frames 1..30, menu + legends fade in over 30..44.
    (OUT / "layout.txt").write_text(
        "canvas 1120 770\n"
        f"scale {SCALE}\n"
        "slide 672\n"
        "slide_frames 29\n"
        "fade_frames 14\n"
        "fps 60\n"
        f"offset {CANVAS_OFFSET[0]} {CANVAS_OFFSET[1]}\n"
        f"dim {BACKGROUND_DIM}\n"
        # full width (ClosedToFull): chrome travels 1079 (blade -88 -> 991),
        # legends 1165 (Legend_A -576 -> 589), the clock ends at x 817
        "full_slide 1079\n"
        "full_legend_slide 1165\n"
        "full_clock_x 817\n"
        # message boxes: ErrorHUD at error_x, sliding error_slide (29 frames)
        f"error_x {ERROR_X}\n"
        f"error_slide {ERROR_FROM - ERROR_X}\n" + menu_lines + battery_lines + clock_lines)
    print("done ->", OUT)


def make_battery_icons():
    """ico_32x_Battery1..4 (charge Little/Low/Medium/High in the 2858 scenes),
    each on a 32x32-unit tile at SCALE, drawn by the overlay at the hosted
    scene's imgBatteryIcon (AppHostElementId: at 30,15, scale 0.96)."""
    s = SCALE * 0.96
    for level in range(1, 5):
        img = X.image(f"ico_32x_Battery{level}.png")
        surface = skia.Surface(int(32 * SCALE), int(32 * SCALE))
        canvas = surface.getCanvas()
        canvas.clear(skia.ColorTRANSPARENT)
        canvas.drawImageRect(img, skia.Rect.MakeWH(32 * s, 32 * s),
                             skia.SamplingOptions(skia.FilterMode.kLinear))
        save(surface.makeImageSnapshot(), f"battery_{level}.png")
    lines = ""
    for page, (x, y) in BATTERY_ICON.items():
        lines += f"battery {page} {30 + x * 0.96:.4f} {15 + y * 0.96:.4f}\n"
    return lines + "battery_size 32\n"


def make_clock_atlas():
    """Glyphs for the Guide clock (DateTimeTextId: 170x40 at 402,64, 18pt,
    TextStyle 528 = right aligned, top of the box, white), laid out exactly
    like xui_render.draw_text so the overlay can compose any time."""
    # the console shows "12:05 PM"
    chars = "0123456789:APM"
    font = skia.Font(X.FONT, 18 * X.POINT_TO_PX)
    metrics = font.getMetrics()
    line_h = metrics.fDescent - metrics.fAscent
    pad, cell = 6, 40  # canvas units
    s = SCALE
    surface = skia.Surface(int(cell * len(chars) * s), int((line_h + 2 * pad) * s))
    canvas = surface.getCanvas()
    canvas.clear(skia.ColorTRANSPARENT)
    canvas.scale(s, s)
    paint = skia.Paint(AntiAlias=True, Color=0xFFFFFFFF)
    lines = []
    for i, ch in enumerate(chars):
        canvas.drawString(ch, i * cell + pad, pad - metrics.fAscent, font, paint)
        lines.append(f"glyph {ch} {font.measureText(ch):.4f}")
    lines.append(f"space {font.measureText(' '):.4f}")
    surface.makeImageSnapshot().save(str(OUT / "clock_atlas.png"), skia.kPNG)
    return (f"clock_box 402 64 170 40\n"
            f"clock_font {line_h:.4f} {-metrics.fAscent:.4f}\n"
            f"clock_cell {cell} {pad}\n" + "\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
