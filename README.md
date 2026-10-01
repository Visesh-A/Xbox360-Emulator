# Xbox 360 Blades — the 2006 console experience on Xenia

The original Xbox 360 "Blades" dashboard, version **2.0.2858.0** (June 2006), with the real
boot animation and an authentic **Xbox Guide**, running on a modified
[Xenia Canary](https://github.com/xenia-canary/xenia-canary).

- The real boot animation, then the real Blades dashboard: profiles, DVD tray, game discs.
- The Guide: rebuilt from the console's own Guide art and code (hud.xex / xam.xex):
  - menus, sign in / out and creating a profile;
  - the gamer card, Game Defaults, View Games and achievements;
  - Personal Settings, Themes (Guide Background, Custom Color, trims), Active Downloads;
  - Select Music, message boxes and sounds.
- The dashboard's Music area (an empty hard drive's library, the Music Player) and
  Media sources.

Everything Microsoft-owned (the dashboard, the system update, the art made from them)
is **not** in this repository. `Setup-Xbox360.ps1` builds it from the two system files
below. Games and personal saves are yours to add.

## What you need

1. **Windows 10/11 (x64)** with a Vulkan- or Direct3D 12-capable GPU.
2. **The two system files**, downloaded into `setup\downloads`:
   - `2.0.1888.0 FS.rar`, the dashboard 2.0.1888.0:
     <https://digiex.net/threads/xbox-360-dashboard-update-2-0-1888-0-download.6730/>
   - `2.0.2858.0.rar`, the system update 2.0.2858.0:
     <https://digiex.net/threads/xbox-360-dashboard-update-2-0-2858-0-download.6758/>

   Setup checks them against these SHA-256 checksums:

   | File | SHA-256 |
   |---|---|
   | `2.0.1888.0 FS.rar` | `2E50A8D4285040D34C89F1BD4B12A6D5F5BFCBBF25565B6373EDBCBC3E5AB240` |
   | `2.0.2858.0.rar` | `D0CA0C57A49C2DD63F787F9FB51D73B76803A721D2FD85465D96E550ECECE9FD` |

3. **Internet access during setup.** Setup downloads and installs the rest itself:

| What | From | Used for |
|---|---|---|
| Python 3.12 (if missing) | winget / python.org | rendering the Guide's images |
| Python packages (exact versions, `setup\requirements.txt`) | PyPI | skia, numpy, OpenCV, Pillow, Capstone, fontTools |
| .NET 8 SDK (if missing) | winget / Microsoft | building XUIHelper |
| [XUIHelper](https://github.com/SGCSam/XUIHelper) `c0d0830` | GitHub | converting the Guide's scenes (XUR → XUI) |
| [ffmpeg 9.0.2](https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2) | GitHub | the Guide's sounds |
| [Xenia boot animation build 2.3.0](https://github.com/seven7000real/xenia-canary/releases/tag/2.3.0) (seven7000real's fork) | GitHub | running bootanim.xex |

## Setup

1. Clone or download this repository into a folder **without spaces** in its path
   (e.g. `D:\Xbox360`).
2. Put the two `.rar` files in `setup\downloads`.
3. Run **`Setup-Xbox360.cmd`**. It takes about an hour, mostly rendering the Guide. At the
   end it compares every built file with the reference setup's checksums
   (`setup\manifests\expected.sha256`). "1431 of 1431 files identical" means your copy
   matches the original exactly.
4. Put your own game discs (`.iso`) in `Games`.
5. Run **`Start-Xbox360.cmd`** (720p), or `Start-Xbox360-2K.cmd` (rendered at 2x).

## Using it

- **Guide button:** opens the Guide. On a DualSense, the Create button is mapped to Guide
  and the PS button to Back (`xenia-dash\gamecontrollerdb.txt`). Keyboard: Xenia's
  keyboard controller mode.
- **Profiles:** create your own from the dashboard or the Guide. None is pre-made, as on a
  new console.
- **Games:** Games blade → Open Tray → pick a disc in the small window → Close Tray. The
  dashboard launches it, and Xbox Guide → Xbox Dashboard returns.

## Not like a real console

- **Xbox Live** is offline: like a console with the network cable unplugged.
- **Themes → Guide Background:** the first time a background is chosen, the Guide's
  images for it are rendered in the background (a few minutes); the Guide switches when
  done. A real console changes at once.
- **Switching between the dashboard and a game** restarts Xenia's window.

## Repository layout

| Path | What |
|---|---|
| `Setup-Xbox360.ps1` / `.cmd` | builds everything from the system files |
| `Start-Xbox360.ps1` / `.cmd` | the launcher: boot animation, dashboard, games |
| `xenia-dash\xenia_canary.exe` | the modified Xenia Canary (Windows x64 build) |
| `xenia-patches\` | its source: 51 patches on Xenia Canary `02d2cb5` (below) |
| `src\re\` | the Guide's asset scripts (XUI renderer, `make_*_assets.py`) and research tools |
| `setup\` | setup's steps, pinned packages, config templates, checksums |
| `Tools\Extract-Stfs.ps1` | extracts the system update package |

## Building Xenia from source (optional)

The prebuilt `xenia-dash\xenia_canary.exe` is all you need. To build it yourself (Visual
Studio 2022 Build Tools, CMake, Python 3.12, Vulkan SDK; see Xenia's
[Building](https://github.com/xenia-canary/xenia-canary/blob/canary_experimental/docs/building.md)):

```
git clone https://github.com/xenia-canary/xenia-canary.git
cd xenia-canary
git checkout 02d2cb5cc4bfbf047a3ee136923c263ae11f8356
git am ..\path\to\this\repo\xenia-patches\*.patch
python xenia-build.py setup
python xenia-build.py build --config=Release --target=xenia-app
```

Then copy `build\bin\Windows\Release\xenia_canary.exe` to `xenia-dash\`.

## Licences

- Xenia: BSD 3-Clause (`xenia-dash\LICENSE`). The patches and scripts here are under the
  same terms.
- Xbox 360, the dashboard and their art are Microsoft's and are not distributed here.
