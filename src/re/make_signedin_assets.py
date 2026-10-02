"""hud.xex's signed-in main menu (MainMenuSignedIn.xur) for an offline profile,
and the signed-out menu's profile count drawn at run time.

hud 91444010 sets the HUD state: 6 nobody signed in (MainMenuSignedOut), 5
signed in to Xbox Live, 8 signed in locally with an Xbox Live account, 9 signed
in locally without one (XamUserIsOnlineEnabled false: this console's
profiles). 914479E0 for state 8 shows txtSignInLive / btnSignInLive and hides
the community bar and btnQuickChat; for any other state the reverse. So in
state 9: the gamer card (xam's XuiGamerCard, Format Mini: its scenes' "Mini"
frames; offline base), the community bar (CommunityBar.xur: heading
"Community", or the focused button's "Friends" / "Messages" / "Players"
(91450C18); captions empty with no count (91450FF0)), Private Chat, Personal
Settings, the music player and the game banner.

The signed-out menu's labelProfiles is "%d Profiles Found" (Strings 37), or
"%d Profile Found" (38) for one (91449310): drawn at run time now.

Writes into the Guide asset folder:
  menusi_<item>.png       the signed-in menu with <item> focused, no legends
  menusi_legends_a/b/xy.png
  menu_<item>.png         the signed-out menu again, labelProfiles left out
  signedin.txt            nav ("menusi <item> <up> <down> <left> <right>"),
                          the card's texts and picture, the profile count text
"""
import json
import os

import numpy as np

import make_guide_assets as G
import xui_render as X

SI_EMBEDS = {"scnMusic": "MiniMediaPlayer.xui", "scnCommunity": "CommunityBar.xui",
             "ctlGamerCard": "gc_GamerCard.xui"}
SI_FOCUS = ["ctlGamerCard", "btnMessages", "btnFriends", "btnRecentPlayers", "btnQuickChat",
            "btnOptions", "btnPlaybackMode", "btnVolume", "btnPlaylist", "btnGameBanner"]
HEADING = {"btnFriends": "Friends", "btnMessages": "Messages", "btnRecentPlayers": "Players"}
K = X.SUPERSAMPLE * G.SCALE


def card_state():
    """xam's gamer card in Format Mini, offline (its scenes' Mini frames)."""
    card = X.cached_canvas(X.ART / "xui" / "gc_GamerCard.xui").children[0]
    st = {}
    for node, frame in ((card, card.frames["EndMini"]), (card.find("offlineBaseScene"), 2),
                        (card.find("onlineBaseScene"), 2)):
        for elem, props in X.timelines_at(node, frame).items():
            st.setdefault(elem, {}).update(props)
    st.update({
        "offlineBaseScene": {**st.get("offlineBaseScene", {}), "Show": "true"},
        "onlineBaseScene": {**st.get("onlineBaseScene", {}), "Show": "false"},
        "extendedScene": {"Show": "false"},
        "gamerTagText": {**st.get("gamerTagText", {}), "NavTabForward": "\x01card_gamertag"},
        "credText": {**st.get("credText", {}), "NavTabForward": "\x01card_cred"},
        "achievementsText": {**st.get("achievementsText", {}), "NavTabForward": "\x01card_ach"},
        "titlesPlayedText": {**st.get("titlesPlayedText", {}), "NavTabForward": "\x01card_titles"},
        "gamerTileImage": {**st.get("gamerTileImage", {}), "ImagePath": "\x01card_tile"},
    })
    return st


def si_state(focus):
    st = {k: dict(v) for k, v in G.MENU_STATE.items() if k != "labelProfiles"}
    st.update(card_state())
    st.update({
        # state 9 (914479E0)
        "btnSignInLive": {"Show": "false", "Enabled": "false"},
        "txtSignInLive": {"Show": "false"},
        "btnQuickChat": {"Show": "true", "Enabled": "true"},
        "scnCommunity": {"Show": "true", "Enabled": "true"},
        "txtCommunityHeading": {"NavTabForward": HEADING.get(focus, "Community")},
        "btnMessages": {"NavTabForward": ""},
        "btnFriends": {"NavTabForward": ""},
        "btnRecentPlayers": {"NavTabForward": ""},
    })
    return st


def nav_graph(scene, embeds, state, focusable):
    """menu_nav_graph's XUI focus rules for another menu scene."""
    root = X.cached_canvas(X.ART / "xui" / scene).children[0]
    nodes, parent = {}, {}

    def index(n, par):
        nodes[n.id] = n
        parent[n.id] = par
        kids = [X.cached_canvas(X.ART / "xui" / embeds[n.id]).children[0]] if n.id in embeds else n.children
        for c in kids:
            if c.id:
                index(c, n.id)

    index(root, None)

    def prop(i, k):
        v = state.get(i, {}).get(k, nodes[i].props.get(k))
        # a Nav target may be a path into a group ("radgrpOutputLocation\
        # radbtnPlayHeadset"): the element it names is its last part
        if v and k.startswith("Nav") and "\\" in v:
            v = v.split("\\")[-1]
        return v

    def enabled(i):
        return prop(i, "Enabled") != "false" and prop(i, "Show") != "false"

    def is_scene(i):
        return nodes[i].cls in ("XuiScene", "HUDScene") or (i in embeds and i not in focusable)

    def focus_into(i):
        if i in embeds and i not in focusable:
            return focus_into(X.cached_canvas(X.ART / "xui" / embeds[i]).children[0].id)
        if not is_scene(i):
            return i
        d = prop(i, "DefaultFocus")
        if d and enabled(d):
            return focus_into(d)
        for c in nodes[i].children:
            if c.id in nodes and c.id in focusable and enabled(c.id):
                return c.id
        return None

    keys = {"up": "NavUp", "down": "NavDown", "left": "NavLeft", "right": "NavRight"}

    def move(i, direction):
        seen = set()
        cur = i
        while cur is not None:
            target = prop(cur, keys[direction])
            if target is None:
                cur = parent.get(cur)
                continue
            while target and target not in seen:
                seen.add(target)
                t = focus_into(target)
                if t is not None and enabled(t) and t != i:
                    return t
                if t is None or not is_scene(target):
                    target = prop(target, keys[direction])
                else:
                    break
            return None
        return None

    return {i: {d: move(i, d) for d in keys} for i in focusable}


def item_line(name, e):
    s = e["sx"] / K
    if e["kind"] == "text":
        return (f"text {name} {e['tx'] / K:.4f} {e['ty'] / K:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f} "
                f"{e['size_px'] * s:.4f} {e['ascent'] * s:.4f} {e['line_h'] * s:.4f} "
                f"{e['style']} {e['color']:08X}")
    return f"image {name} {e['tx'] / K:.4f} {e['ty'] / K:.4f} {e['w'] * s:.4f} {e['h'] * s:.4f}"


def main():
    G.apply_runtime_state()
    no_legends = G.PAGE_HIDE + G.LEGENDS
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    # signed in
    for i, focus in enumerate(SI_FOCUS):
        if not G.unit(f"menusi_{focus}"):
            continue
        X.CAPTURE = {}
        img = X.render_guide(G.OPEN, "MainMenuSignedIn.xui",
                             "baseMetaPane" if focus == "ctlGamerCard" else focus,
                             hide=no_legends, scale=G.SCALE, app_state=si_state(focus), embeds=SI_EMBEDS)
        cap, X.CAPTURE = X.CAPTURE, None
        G.save(img, f"menusi_{focus}.png")
        if i == 0:
            for n, e in sorted(cap.items()):
                G.emit(item_line(n, e))
    for part, hide in G.LEGEND_PARTS:
        if G.unit(f"menusi_legends_{part}"):
            G.save(X.render_guide(G.OPEN, "MainMenuSignedIn.xui", hide=only_legends + hide,
                                  scale=G.SCALE, app_state=si_state(None), embeds=SI_EMBEDS),
                   f"menusi_legends_{part}.png")
    if G.unit("menusi_nav"):
        nav = nav_graph("MainMenuSignedIn.xui", SI_EMBEDS, si_state(None), SI_FOCUS)
        for item in SI_FOCUS:
            G.emit(f"menusi {item} " + " ".join(nav[item][d] or "-" for d in ("up", "down", "left", "right")))
    # signed out: the same images without the profile count, which is captured
    st = {k: dict(v) for k, v in G.MENU_STATE.items()}
    st["labelProfiles"] = {"NavTabForward": "\x01profiles"}
    for i, focus in enumerate(G.MENU_FOCUS):
        if not G.unit(f"menu_{focus}"):
            continue
        X.CAPTURE = {}
        img = X.render_guide(G.OPEN, "MainMenuSignedOut.xui", focus, hide=no_legends, scale=G.SCALE,
                             app_state=st, embeds=G.MENU_EMBEDS)
        cap, X.CAPTURE = X.CAPTURE, None
        # replaces make_guide_assets' menu_<focus>.png once menus() has
        # checked that only the label differs (so this can run alongside it)
        e = cap["profiles"]
        box = (e["tx"] / K * G.SCALE, e["ty"] / K * G.SCALE,
               (e["tx"] / K + e["w"] * e["sx"] / K) * G.SCALE,
               (e["ty"] / K + e["h"] * e["sx"] / K) * G.SCALE)
        (G.OUT / f"_signedout_menu_{focus}.json").write_text(json.dumps(box), encoding="utf-8")
        G.save(img, f"_signedout_menu_{focus}.png")
        if i == len(G.MENU_FOCUS) - 1:
            G.emit(item_line("profiles", cap["profiles"]))
    for line in G.finish("signedin.txt"):
        print(line)


def menus():
    """After make_guide_assets: each signed-out menu image differs from its
    menu_<focus>.png only in the profile count's label, then replaces it."""
    from PIL import Image
    for focus in G.MENU_FOCUS:
        new = G.OUT / f"_signedout_menu_{focus}.png"
        box_file = G.OUT / f"_signedout_menu_{focus}.json"
        box = json.loads(box_file.read_text(encoding="utf-8"))
        a = np.asarray(Image.open(G.OUT / f"menu_{focus}.png").convert("RGBA")).astype(int)
        b = np.asarray(Image.open(new).convert("RGBA")).astype(int)
        diff = np.argwhere(np.abs(a - b).max(axis=2) > 2)
        outside = [p for p in diff if not (box[0] - 2 <= p[1] <= box[2] + 2 and box[1] - 2 <= p[0] <= box[3] + 2)]
        print(f"   menu_{focus}: {len(diff)} px changed, {len(outside)} outside the label")
        if outside:
            raise SystemExit(f"menu_{focus}: pixels outside labelProfiles changed, e.g. {outside[:3]}")
        new.replace(G.OUT / f"menu_{focus}.png")
        box_file.unlink()


def sign_out_assets():
    """X "Sign Out" (914481F8): XamShowMessageBox(the legend's caption, Strings
    39, [41 "Yes, sign out", 40 "No, don't sign out"], focus 1, icon 2), shown
    like the menu's other boxes; Yes -> Status.xur ("Signing out", no legends,
    914441B8) while XamUserLogon signs the profile out (at least 2 s)."""
    G.apply_runtime_state()
    s = G.STRINGS
    # labelProfiles' strings (91449310)
    if G.unit("signedin_strings"):
        (G.OUT / "signedin_strings.txt").write_text(
            f"str 37 {s[37]}\nstr 38 {s[38]}\n", encoding="utf-8")
    scene = G.message_box("Sign Out", s[39], [s[41], s[40]])
    for i, choice in enumerate(("yes", "no")):
        if G.unit(f"error_signout_{choice}"):
            G.save(X.render_guide(G.ERROR, None, f"Button{i}", hide=("GamerTag",), scale=G.SCALE,
                                  error_scene=scene, size=(G.ERROR_W, 770), origin_x=G.ERROR_X),
                   f"error_signout_{choice}.png")
    no_legends = G.PAGE_HIDE + G.LEGENDS
    only_legends = G.CONTENT_HIDE + ("AppHostElementId",)
    if G.unit("status_signout"):
        G.save(X.render_guide(G.OPEN, "Status.xui", None, hide=no_legends, scale=G.SCALE),
               "status_signout.png")
    for part, hide in G.LEGEND_PARTS:
        if G.unit(f"status_legends_{part}"):
            G.save(X.render_guide(G.OPEN, "Status.xui", hide=only_legends + hide, scale=G.SCALE),
                   f"status_legends_{part}.png")


if __name__ == "__main__":
    import sys
    if os.environ.get("SIGNEDIN_MENUS"):
        menus()
    elif os.environ.get("GUIDE_MERGE"):
        G.merge("signedin.txt", int(os.environ["GUIDE_MERGE"]))
    elif "--signout" in sys.argv:
        sign_out_assets()
    else:
        main()
        sign_out_assets()
