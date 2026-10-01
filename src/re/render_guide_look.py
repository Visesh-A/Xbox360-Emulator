"""Renders the Guide's images for one Guide background (Personal Settings >
Themes: a Guide Background tile or a Custom Color), in the background, for the
overlay to switch to when done.

  render_guide_look.py <look> <out dir>
    <look>: "color:AARRGGBB" or "image:<tile file>" (as GUIDE_BACKGROUND)

The default Guide folder is copied first (layouts, strings, fonts and the
images that have no Guide background), then every image script runs again
with GUIDE_OUT / GUIDE_BACKGROUND; "ready" is written last.
"""
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT = HERE.resolve().parents[1] / "xenia-dash" / "guide"
SCRIPTS = [
    "make_guide_assets.py", "make_msgbox_assets.py", "make_createprofile_legends.py",
    # the keyboard's focus images in 4 parts (its layout is the default's)
    "make_keyboard_assets.py#0/4", "make_keyboard_assets.py#1/4",
    "make_keyboard_assets.py#2/4", "make_keyboard_assets.py#3/4", "make_congrats_assets.py", "make_addxboxlive_assets.py",
    "make_gamerprofile_assets.py", "make_prefs_assets.py", "make_viewgames_assets.py",
    "make_signedin_assets.py", "make_signin_assets.py", "make_options_assets.py",
    "make_downloads_assets.py", "make_music_assets.py", "make_themes_assets.py",
]


# signedin reads make_guide_assets' menu images; the rest are independent
AFTER = {"make_signedin_assets.py": "make_guide_assets.py"}


def main():
    look, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    (out / "ready").unlink(missing_ok=True)
    shutil.copytree(DEFAULT, out, dirs_exist_ok=True)
    (out / "ready").unlink(missing_ok=True)
    env = dict(os.environ, GUIDE_OUT=str(out), GUIDE_BACKGROUND=look)
    logs = out / "render_logs"
    logs.mkdir(exist_ok=True)
    start = time.time()
    # all at once (the process's priority, below normal from the overlay, is
    # inherited), each script's output in its own log
    running, done, failed = {}, set(), False
    pending = list(SCRIPTS)
    with open(out / "render.log", "w", encoding="utf-8") as log:
        while pending or running:
            for script in [s for s in pending if AFTER.get(s) in (None, *done)]:
                pending.remove(script)
                name, _, part = script.partition("#")
                f = open(logs / (script.replace("#", "_").replace("/", "of") + ".log"), "w", encoding="utf-8")
                penv = dict(env, KBD_PART=part) if part else env
                running[script] = (subprocess.Popen([sys.executable, str(HERE / name)], cwd=HERE,
                                                    env=penv, stdout=f, stderr=subprocess.STDOUT),
                                   f, time.time())
            for script, (proc, f, t) in list(running.items()):
                if proc.poll() is None:
                    continue
                f.close()
                del running[script]
                done.add(script)
                log.write(f"== {script}: exit {proc.returncode}, {time.time() - t:.0f} s\n")
                log.flush()
                failed |= proc.returncode != 0
            time.sleep(0.5)
        log.write(f"== all done in {time.time() - start:.0f} s\n")
    if failed:
        return 1
    (out / "ready").write_text(look, encoding="utf-8")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        import traceback
        with open(Path(sys.argv[2]) / "render_error.log", "w", encoding="utf-8") as f:
            traceback.print_exc(file=f)
        raise
