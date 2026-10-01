"""Builds src/re's working art from the extracted packages (art2858/2858):

- guide_art_2858/<folder>: the package files the Guide's asset scripts use
  (manifests/guide_art_files.txt; folder -> package below)
- guide_art_2858/xui: the scenes converted from XUR to XUI with XUIHelper
- fonts/XenonCLatin_1888.ttf: the console font, from 1888.FS/xenonclatin.xtt
- vk_keys.json: the keyboard's key table from vk.xex (dumps2858/vk_2858.bin)

  python build_art.py <XUIHelper.CLI.exe>
"""
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RE = ROOT / "src" / "re"
ART = RE / "art2858" / "2858"
OUT = RE / "guide_art_2858"
FOLDERS = {"hud": "hud", "skin": "huduiskin", "mplayer": "xam0", "gamercrd": "xam1",
           "shrdres": "xam2", "xamres": "xam3", "mmp": "minimediaplayer", "vk": "vk",
           "createprofile": "createprofile", "gamerprofile": "gamerprofile",
           "marketplace": "marketplace"}
# guide_art_2858/xui/<name>.xui <- art2858/2858/<package>/<scene>.xur
SCENES = {
    "ColorSelect": "hud/ColorSelect", "CommunityBar": "hud/CommunityBar",
    "DashStyleSelect": "hud/DashStyleSelect", "InfoMessage": "hud/InfoMessage",
    "InfoUpsellLive": "hud/InfoUpsellLive", "MainMenuSignedIn": "hud/MainMenuSignedIn",
    "MainMenuSignedOut": "hud/MainMenuSignedOut", "MiniMediaPlayer": "hud/MiniMediaPlayer",
    "Options": "hud/Options", "OptionsController": "hud/OptionsController",
    "OptionsNotifications": "hud/OptionsNotifications", "OptionsOnline": "hud/OptionsOnline",
    "OptionsPersonalization": "hud/OptionsPersonalization", "OptionsVoice": "hud/OptionsVoice",
    "SkinSelect": "hud/SkinSelect", "Status": "hud/Status", "TileSelect": "hud/TileSelect",
    "VisionEffectSelect": "hud/VisionEffectSelect", "skin": "huduiskin/skin",
    "xam_hudbkgnd": "xam3/hudbkgnd", "xam_notify": "xam3/notify",
    "gc_GamerCard": "xam1/GamerCard",
    "cp_AddXboxLive": "createprofile/AddXboxLive",
    "cp_Congratulations": "createprofile/Congratulations",
    "cp_CreateGamerProfile": "createprofile/CreateGamerProfile", "cp_Keyboard": "vk/Keyboard",
    "mkt_ActiveDownloads": "marketplace/ActiveDownloads",
    "mkt_DownloadDetails": "marketplace/DownloadDetails",
    "si_inspad": "signin/inspad", "si_join": "signin/join", "si_passcode": "signin/passcode",
    "si_signin1": "signin/signin1", "si_signin2": "signin/signin2",
    "si_signin4": "signin/signin4", "si_status": "signin/status", "si_UserList": "signin/UserList",
}
for scene in ("570_MusicLibrary", "572_SelectMediaContainer", "576_SelectSong",
              "579_SelectMediaSource", "BeginPlayback", "FileView", "SelectGamePlaylist",
              "SelectGameSong"):
    SCENES["mmp_" + scene] = "minimediaplayer/" + scene
for scene in ("807_EditGamerTile", "808_editProfile", "809_ChangeGamerTile",
              "820_GameShowcaseMe", "821-2_GameAchievStatsMe", "828_AchievDetails",
              "830_GamerPreferences", "831_PreferenceSetting", "832_PreferenceCategory",
              "ChangePersonalTile", "GamerCardScene", "GamerscoreMoreInfo"):
    SCENES["gp_" + scene] = "gamerprofile/" + scene


def copy_art():
    files = (Path(__file__).parent / "manifests" / "guide_art_files.txt").read_text().split()
    for rel in files:
        folder, rest = rel.split("/", 1)
        dest = OUT / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ART / FOLDERS[folder] / rest, dest)
    print(f"guide_art_2858: {len(files)} files")


def convert_scenes(xuihelper):
    (OUT / "xui").mkdir(parents=True, exist_ok=True)
    for name, src in SCENES.items():
        r = subprocess.run([xuihelper, "conv", "-s", str(ART / (src + ".xur")), "-f", "xuiv12",
                            "-o", str(OUT / "xui" / (name + ".xui")), "-g", "V5"],
                           cwd=Path(xuihelper).parent, capture_output=True, text=True)
        if "SUCCESS" not in r.stdout:
            raise SystemExit(f"XUIHelper failed on {src}: {r.stdout}{r.stderr}")
    # signin's strings next to its scenes (make_signin_assets.py)
    shutil.copyfile(ART / "signin" / "Strings.xus", OUT / "xui" / "si_strings.xus")
    print(f"xui: {len(SCENES)} scenes")


def build_font():
    (RE / "fonts").mkdir(exist_ok=True)
    subprocess.run([sys.executable, str(RE / "xtt_to_ttf.py"), str(ROOT / "1888.FS" / "xenonclatin.xtt"),
                    str(RE / "fonts" / "XenonCLatin_1888.ttf")], check=True, capture_output=True)
    print("font: XenonCLatin_1888.ttf")


def decode_vk_keys():
    """vk.xex's key table at 0x917E1A38: per key 10 words (name, then three
    (code, text, mask) sets)."""
    d = (RE / "dumps2858" / "vk_2858.bin").read_bytes()
    base = 0x917E0000

    def s16(a):
        o = a - base
        if not 0 <= o < len(d):
            return None
        out = ""
        for i in range(0, 80, 2):
            c = int.from_bytes(d[o + i:o + i + 2], "big")
            if c == 0:
                break
            out += chr(c)
        return out

    keys, o = [], 0x1A38
    while True:
        w = struct.unpack_from(">10I", d, o)
        name = s16(w[0]) if 0x917E0000 <= w[0] < 0x91820000 else None
        if not name or not name.startswith("Key."):
            break
        k = {"id": name, "sets": []}
        for j in range(3):
            code, sp, mask = w[1 + 3 * j], w[2 + 3 * j], w[3 + 3 * j]
            k["sets"].append({"code": code, "text": s16(sp) if sp else None, "mask": mask})
        keys.append(k)
        o += 0x28
    with open(RE / "vk_keys.json", "w", encoding="utf-8") as f:
        json.dump(keys, f, ensure_ascii=False, indent=1)
    print(f"vk_keys.json: {len(keys)} keys")


if __name__ == "__main__":
    copy_art()
    convert_scenes(sys.argv[1])
    build_font()
    decode_vk_keys()
