"""Renders the Guide's images for one Guide background (Personal Settings >
Themes: a Guide Background tile or a Custom Color), in the background, for the
overlay to switch to when done.

  render_guide_look.py <look> <out dir>
    <look>: "color:AARRGGBB" or "image:<tile file>" (as GUIDE_BACKGROUND)

The default Guide folder is copied first (layouts, strings, fonts and the
images that have no Guide background), then every image script runs again
with GUIDE_OUT / GUIDE_BACKGROUND; "ready" is written last.
"""
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
DEFAULT = HERE.resolve().parents[1] / "xenia-dash" / "guide"
# the same jobs as setup (setup/make_all_assets.py), into the look's folder
sys.path.insert(0, str(HERE.resolve().parents[1] / "setup"))
import make_all_assets as A  # noqa: E402


def main():
    look, out = sys.argv[1], Path(sys.argv[2])
    out.mkdir(parents=True, exist_ok=True)
    (out / "ready").unlink(missing_ok=True)
    shutil.copytree(DEFAULT, out, dirs_exist_ok=True)
    (out / "ready").unlink(missing_ok=True)
    env = dict(A.clean_env(), GUIDE_OUT=str(out), GUIDE_BACKGROUND=look)
    # (the process's priority, below normal from the overlay, is inherited)
    with open(out / "render.log", "w", encoding="utf-8") as log:
        def label(text):
            log.write(text + "\n")
            log.flush()
        failed = A.run_jobs(A.jobs(look=True), env, out / "render_logs", label)
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
