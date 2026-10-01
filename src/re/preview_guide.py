"""Preview renders of the open Guide (menu + dialogs) over a flat colour."""
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).parent))
import make_guide_assets as A  # noqa: E402
import xui_render as X  # noqa: E402

out = Path(sys.argv[1])
focuses = sys.argv[2:] or ["btnSignIn"]
A.apply_runtime_state()
tiles = []
for focus in focuses:
    if focus.startswith("dialog"):
        scene, f, state, embeds = A.dialog_scene("Xbox Guide", A.OFF_TEXT), "btnYes", A.DIALOG_STATE, None
    else:
        scene, f, state, embeds = "MainMenuSignedOut.xui", focus, A.MENU_STATE, A.MENU_EMBEDS
    img = X.render_guide(A.OPEN, scene, f, hide=("GamerTag",), live_text={"DateTimeTextId": A.CLOCK_SAMPLE},
                         scale=1.0, app_state=state, embeds=embeds)
    rgba = Image.fromarray(img.toarray(colorType=X.skia.kRGBA_8888_ColorType), "RGBA")
    bg = Image.new("RGBA", rgba.size, (40, 40, 40, 255))
    bg.alpha_composite(rgba)
    tiles.append(bg.convert("RGB").crop((0, 0, 720, 770)))
side = Image.new("RGB", (730 * len(tiles), 770), "white")
for i, t in enumerate(tiles):
    side.paste(t, (730 * i, 0))
side.save(out)
print("wrote", out)
