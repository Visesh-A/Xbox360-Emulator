"""Renders everything in xenia-dash/guide (the Guide overlay's images,
layouts, strings, sounds and font) and xenia-dash/gamerpics from src/re's
art (build_art.py first).

  python make_all_assets.py <ffmpeg.exe>

The slow scripts run as several parts at once (GUIDE_PART / KBD_PART; their
layout files merged afterwards), as many jobs at a time as the PC has
threads and memory for, the longest first. The files are the same as one run
of each script.
"""
import ctypes
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
# script: number of parts (scripts made of G.unit() blocks; others run whole)
# and its layout file merged from the parts
SPLIT = {"make_guide_assets.py": (4, None), "make_prefs_assets.py": (4, "prefs.txt"),
         "make_addxboxlive_assets.py": (4, "axl.txt"), "make_themes_assets.py": (6, "themes.txt"),
         "make_signedin_assets.py": (4, "signedin.txt"),
         "make_gamerprofile_assets.py": (4, "gamerprofile.txt")}
KBD_PARTS = 6
WHOLE = ["make_msgbox_assets.py", "make_createprofile_legends.py",
         "make_createprofile_strings.py", "make_congrats_assets.py",
         "make_viewgames_assets.py", "make_signin_assets.py", "make_options_assets.py",
         "make_downloads_assets.py", "make_music_assets.py"]
# rough run time (seconds, one job alone), to start the longest first
WEIGHT = {"make_music_assets.py": 380, "make_options_assets.py": 330,
          "make_msgbox_assets.py": 260, "make_viewgames_assets.py": 250}
# the Guide's sounds (xma in the system files) as 48 kHz stereo wav
SOUNDS = {"HUD_open": "xamres/HUD_open.xma", "HUD_close": "xamres/HUD_close.xma",
          "btn_Focus": "shrdres/btn_Focus.xma", "btn_Select": "shrdres/btn_Select.xma",
          "btn_Back": "shrdres/btn_Back.xma"}
# Themes > Guide Background tiles (read by the overlay)
TILES = ["Bubbles.png", "Carbon.png", "Fiber.png", "H2O.png", "Pearl.png", "Sahara.png", "Wood.png"]


def jobs(look=False):
    """job name: (script, extra environment, jobs it waits for). A Guide
    look (render_guide_look.py) has no themes parts: its themes script makes
    only the pages' bases and legends."""
    out = {}
    for script in WHOLE:
        out[script] = (script, {}, ())
    for script, (parts, layout) in SPLIT.items():
        if look and script == "make_themes_assets.py":
            out[script] = (script, {}, ())
            continue
        names = [f"{script} {i + 1}/{parts}" for i in range(parts)]
        for i, name in enumerate(names):
            out[name] = (script, {"GUIDE_PART": f"{i}/{parts}"}, ())
        if layout:
            out[f"{script} layout"] = (script, {"GUIDE_MERGE": str(parts)}, tuple(names))
    kbd = [f"keyboard {i + 1}/{KBD_PARTS}" for i in range(KBD_PARTS)]
    for i, name in enumerate(kbd):
        out[name] = ("make_keyboard_assets.py", {"KBD_PART": f"{i}/{KBD_PARTS}"}, ())
    out["keyboard layout"] = ("make_keyboard_assets.py", {"KBD_MERGE": str(KBD_PARTS)}, tuple(kbd))
    # signedin's signed-out menus replace make_guide_assets' once both ran
    parts = [n for n in out if n.startswith(("make_guide_assets.py ", "make_signedin_assets.py "))
             and not n.endswith(" layout")]
    out["signed-out menus"] = ("make_signedin_assets.py", {"SIGNEDIN_MENUS": "1"}, tuple(parts))
    return out


def weight(name, job):
    script, extra, after = job
    if after:
        return 0
    if script in WEIGHT:
        return WEIGHT[script]
    if "GUIDE_PART" in extra or "KBD_PART" in extra:
        return 300
    return 100


def job_limit():
    """At most one job per thread, and about 1.2 GB of memory each."""
    class MemoryStatus(ctypes.Structure):
        _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("sullAvailExtendedVirtual", ctypes.c_ulonglong)]
    m = MemoryStatus(dwLength=ctypes.sizeof(MemoryStatus))
    ram = 8 << 30
    if hasattr(ctypes, "windll") and ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
        ram = m.ullTotalPhys
    return max(1, min(os.cpu_count() or 4, int(ram / (1.2 * (1 << 30)))))


def run_jobs(table, env, logs, label=print):
    logs.mkdir(parents=True, exist_ok=True)
    limit = job_limit()
    pending, running, done, failed = dict(table), {}, set(), []
    start = time.time()
    label(f"  {len(table)} jobs, {limit} at a time")
    while pending or running:
        ready = sorted((n for n, j in pending.items() if all(a in done for a in j[2])),
                       key=lambda n: -weight(n, pending[n]))
        for name in ready[:max(0, limit - len(running))]:
            script, extra, _ = pending.pop(name)
            f = open(logs / (name.replace("/", "of").replace(" ", "_") + ".log"), "w",
                     encoding="utf-8")
            running[name] = (subprocess.Popen([sys.executable, str(RE / script)], cwd=RE,
                                              env=dict(env, **extra), stdout=f,
                                              stderr=subprocess.STDOUT), f, time.time())
        for name, (proc, f, t) in list(running.items()):
            if proc.poll() is None:
                continue
            f.close()
            del running[name]
            done.add(name)
            label(f"  {name}: {'ok' if proc.returncode == 0 else 'FAILED'} ({time.time() - t:.0f} s)")
            if proc.returncode:
                failed.append(name)
        if failed:
            # stop: the rest would wait on, or merge, missing parts
            for proc, f, _ in running.values():
                proc.kill()
                f.close()
            break
        time.sleep(0.5)
    label(f"  all jobs: {time.time() - start:.0f} s")
    return failed


def clean_env():
    env = dict(os.environ)
    for k in ("GUIDE_OUT", "GUIDE_BACKGROUND", "GUIDE_PART", "GUIDE_MERGE", "KBD_PART", "KBD_MERGE",
              "SIGNEDIN_MENUS"):
        env.pop(k, None)
    return env


def run_scripts():
    logs = ROOT / "setup" / "logs"
    failed = run_jobs(jobs(), clean_env(), logs, lambda s: print(s, flush=True))
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
