"""Renders everything in xenia-dash/guide (the Guide overlay's images,
layouts, strings, sounds and font) and xenia-dash/gamerpics from src/re's
art (build_art.py first).

  python make_all_assets.py <ffmpeg.exe>
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RE = ROOT / "src" / "re"
ART = RE / "guide_art_2858"
GUIDE = ROOT / "xenia-dash" / "guide"
PICS = ROOT / "xenia-dash" / "gamerpics"
SCRIPTS = [
    "make_guide_assets.py", "make_msgbox_assets.py", "make_createprofile_legends.py",
    "make_createprofile_strings.py", "make_keyboard_assets.py", "make_congrats_assets.py",
    "make_addxboxlive_assets.py", "make_gamerprofile_assets.py", "make_prefs_assets.py",
    "make_viewgames_assets.py", "make_signedin_assets.py", "make_signin_assets.py",
    "make_options_assets.py", "make_downloads_assets.py", "make_music_assets.py",
    "make_themes_assets.py",
]
# signedin reads make_guide_assets' menu images; the rest are independent
AFTER = {"make_signedin_assets.py": "make_guide_assets.py"}
# the Guide's sounds (xma in the system files) as 48 kHz stereo wav
SOUNDS = {"HUD_open": "xamres/HUD_open.xma", "HUD_close": "xamres/HUD_close.xma",
          "btn_Focus": "shrdres/btn_Focus.xma", "btn_Select": "shrdres/btn_Select.xma",
          "btn_Back": "shrdres/btn_Back.xma"}
# Themes > Guide Background tiles (read by the overlay)
TILES = ["Bubbles.png", "Carbon.png", "Fiber.png", "H2O.png", "Pearl.png", "Sahara.png", "Wood.png"]


def run_scripts():
    env = dict(os.environ)
    env.pop("GUIDE_OUT", None)
    env.pop("GUIDE_BACKGROUND", None)
    logs = ROOT / "setup" / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    pending, running, done, failed = list(SCRIPTS), {}, set(), []
    start = time.time()
    while pending or running:
        for script in [s for s in pending if AFTER.get(s) in (None, *done)]:
            pending.remove(script)
            f = open(logs / (script + ".log"), "w", encoding="utf-8")
            running[script] = (subprocess.Popen([sys.executable, str(RE / script)], cwd=RE, env=env,
                                                stdout=f, stderr=subprocess.STDOUT), f, time.time())
        for script, (proc, f, t) in list(running.items()):
            if proc.poll() is None:
                continue
            f.close()
            del running[script]
            done.add(script)
            print(f"  {script}: {'ok' if proc.returncode == 0 else 'FAILED'} ({time.time() - t:.0f} s)",
                  flush=True)
            if proc.returncode:
                failed.append(script)
        time.sleep(0.5)
    print(f"  all scripts: {time.time() - start:.0f} s")
    if failed:
        raise SystemExit(f"failed: {failed} (logs in {logs})")


def sounds(ffmpeg):
    for name, src in SOUNDS.items():
        subprocess.run([ffmpeg, "-hide_banner", "-loglevel", "error", "-y", "-i", str(ART / src),
                        "-ac", "2", "-ar", "48000", str(GUIDE / f"{name}.wav")], check=True)
    print(f"  sounds: {len(SOUNDS)}")


def copies():
    for tile in TILES:
        shutil.copyfile(ART / "hud" / tile, GUIDE / tile)
    PICS.mkdir(parents=True, exist_ok=True)
    pics = sorted((ART / "shrdres").glob("[36][24]_fffe07d1*.png"))
    for p in pics:
        shutil.copyfile(p, PICS / p.name)
    print(f"  tiles: {len(TILES)}, gamer pictures: {len(pics)}")


if __name__ == "__main__":
    GUIDE.mkdir(parents=True, exist_ok=True)
    run_scripts()
    sounds(sys.argv[1])
    copies()
