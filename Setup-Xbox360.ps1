# Builds the complete Xbox 360 Blades setup in this folder from the two system
# files (see README.md): the 2.0.1888.0 dashboard and the 2.0.2858.0 system update.
#
#   1. Put "2.0.1888.0 FS.rar" and "2.0.2858.0.rar" in setup\downloads (or pass -Downloads).
#   2. Run Setup-Xbox360.cmd (or: powershell -ExecutionPolicy Bypass -File Setup-Xbox360.ps1).
#   3. Start-Xbox360.cmd
#
# Everything else is downloaded or built here: Python 3.12 and .NET 8 (winget, if missing),
# the pinned Python packages, XUIHelper, ffmpeg and the boot animation build. The Guide's
# images are then rendered from the system files (this takes a while; about 10 minutes on a
# 24-thread CPU) and checked against the reference setup's checksums.
param(
    [string]$Downloads = (Join-Path $PSScriptRoot "setup\downloads"),
    [switch]$SkipVerify
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$root = $PSScriptRoot
$setup = Join-Path $root "setup"
$tools = Join-Path $setup "tools"
$work = Join-Path $setup "work"
New-Item -ItemType Directory -Force $tools, $work | Out-Null

function Step([string]$text) { Write-Host ""; Write-Host "== $text" -ForegroundColor Cyan }
function Fail([string]$text) { Write-Host "ERROR: $text" -ForegroundColor Red; exit 1 }
function Hash([string]$path) { (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash }
function Download([string]$url, [string]$out, [string]$sha256) {
    if ((Test-Path -LiteralPath $out) -and (Hash $out) -eq $sha256) { return }
    Write-Host "   downloading $url"
    Invoke-WebRequest $url -OutFile $out -UseBasicParsing
    if ((Hash $out) -ne $sha256) { Fail "$out does not match its checksum (download corrupted?)" }
}

# Xenia takes paths on its command line unquoted, so the folder must not contain spaces.
if ($root -match ' ') { Fail "Install into a folder without spaces in its path (now: $root)." }
if (Get-Process xenia_canary -ErrorAction SilentlyContinue) { Fail "Close Xenia first." }

# ---------------------------------------------------------------------------------------------
Step "System files"
$inputs = @{
    "2.0.1888.0 FS.rar" = "2E50A8D4285040D34C89F1BD4B12A6D5F5BFCBBF25565B6373EDBCBC3E5AB240"
    "2.0.2858.0.rar"    = "D0CA0C57A49C2DD63F787F9FB51D73B76803A721D2FD85465D96E550ECECE9FD"
}
foreach ($name in $inputs.Keys) {
    $p = Join-Path $Downloads $name
    if (-not (Test-Path -LiteralPath $p)) { Fail "Missing $p - download it (README.md) into $Downloads." }
    if ((Hash $p) -ne $inputs[$name]) { Fail "$name is not the expected file (checksum differs)." }
    Write-Host "   $name ok"
}
# Windows' own tar (libarchive) reads RAR
$tar = Join-Path $env:SystemRoot "System32\tar.exe"
$x1888 = Join-Path $work "1888"; $x2858 = Join-Path $work "2858"
foreach ($d in $x1888, $x2858) { if (Test-Path $d) { Remove-Item -Recurse -Force $d }; New-Item -ItemType Directory $d | Out-Null }
& $tar -xf (Join-Path $Downloads "2.0.1888.0 FS.rar") -C $x1888; if ($LASTEXITCODE) { Fail "could not extract 2.0.1888.0 FS.rar" }
& $tar -xf (Join-Path $Downloads "2.0.2858.0.rar") -C $x2858; if ($LASTEXITCODE) { Fail "could not extract 2.0.2858.0.rar" }

# the dashboard's files (2.0.1888.0)
$fs = Join-Path $root "1888.FS"
if (Test-Path $fs) { Remove-Item -Recurse -Force $fs }
Copy-Item (Get-ChildItem $x1888 -Recurse -Directory -Filter "1888.FS" | Select-Object -First 1).FullName $fs -Recurse
# the June 2006 system update's patches ($SystemUpdate\su20076000_00000000, an STFS package)
$su = Get-ChildItem $x2858 -Recurse -File -Filter "su20076000_00000000" | Select-Object -First 1
$patches = Join-Path $work "2858-files"
if (Test-Path $patches) { Remove-Item -Recurse -Force $patches }
& (Join-Path $root "Tools\Extract-Stfs.ps1") -Package $su.FullName -OutDir $patches | Out-Null
# installed as Xenia title updates (names without "$flash_"): the dashboard's for xenia-dash,
# the boot animation's for xenia-bootanim; bootanim.xexp also beside bootanim.xex (the boot
# animation build only finds it there)
$tuDash = Join-Path $root "xenia-dash\content\0000000000000000\FFFE07D1\000B0000\SystemUpdate_2.0.2858.0"
$tuBoot = Join-Path $root "xenia-bootanim\content\0000000000000000\00000000\000B0000\SystemUpdate_2.0.2858.0"
New-Item -ItemType Directory -Force $tuDash, $tuBoot | Out-Null
foreach ($f in Get-ChildItem -LiteralPath $patches -Filter '$flash_*') {
    Copy-Item -LiteralPath $f.FullName (Join-Path $tuDash ($f.Name -replace '^\$flash_', '')) -Force
}
Copy-Item -LiteralPath (Join-Path $patches '$flash_bootanim.xexp') (Join-Path $tuBoot "bootanim.xexp") -Force
Copy-Item -LiteralPath (Join-Path $patches '$flash_bootanim.xexp') (Join-Path $fs "bootanim.xexp") -Force
Write-Host "   1888.FS and the 2858 update installed"

# ---------------------------------------------------------------------------------------------
Step "Tools"
# the boot animation build (seven7000real's Xenia fork 2.3.0: the only one that runs bootanim.xex)
New-Item -ItemType Directory -Force (Join-Path $root "xenia-bootanim") | Out-Null
Download "https://github.com/seven7000real/xenia-canary/releases/download/2.3.0/xenia_canary.exe" `
    (Join-Path $root "xenia-bootanim\xenia_canary.exe") "847370FEC60FDAD0BD8A4C3BB655FFA58CEF3693F01E7BD2D3616C0C4E9334D4"
# ffmpeg 9.0.2 (the Guide's sounds)
$ffZip = Join-Path $tools "ffmpeg-9.0.2-essentials_build.zip"
Download "https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip" `
    $ffZip "60F467265B1E312373DBCD92200C2618A74850F98D3D078E94296BB3FA2047BA"
$ffmpeg = Join-Path $tools "ffmpeg-9.0.2-essentials_build\bin\ffmpeg.exe"
if (-not (Test-Path $ffmpeg)) { Expand-Archive $ffZip $tools -Force }
Write-Host "   boot animation build, ffmpeg ok"

# Python 3.12 with the pinned packages, in .venv
$py = $null
foreach ($c in @("py -3.12", (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"))) {
    try {
        $v = if ($c -eq "py -3.12") { & py -3.12 --version 2>$null } else { & $c --version 2>$null }
        if ($v -match "^Python 3\.12") { $py = $c; break }
    } catch {}
}
if (-not $py) {
    Write-Host "   installing Python 3.12 (winget)"
    winget install --id Python.Python.3.12 -e --scope user --silent --accept-package-agreements --accept-source-agreements | Out-Null
    $py = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (-not (Test-Path $py)) { Fail "Python 3.12 could not be installed; install it from python.org and run setup again." }
}
$venv = Join-Path $root ".venv"
$python = Join-Path $venv "Scripts\python.exe"
if (-not (Test-Path $python)) {
    if ($py -eq "py -3.12") { & py -3.12 -m venv $venv } else { & $py -m venv $venv }
}
& $python -m pip install --quiet --disable-pip-version-check -r (Join-Path $setup "requirements.txt")
if ($LASTEXITCODE) { Fail "pip could not install setup\requirements.txt" }
Write-Host "   Python packages ok"

# .NET 8 SDK and XUIHelper (converts the Guide's XUR scenes to XUI)
$sdks = try { & dotnet --list-sdks 2>$null } catch { "" }
if (-not ($sdks -match "^8\.")) {
    Write-Host "   installing the .NET 8 SDK (winget)"
    winget install --id Microsoft.DotNet.SDK.8 -e --silent --accept-package-agreements --accept-source-agreements | Out-Null
    $env:PATH = "$env:ProgramFiles\dotnet;$env:PATH"
}
$xhCommit = "c0d083036c6b0e3cdec5a3df0abfca0e58973117"
$xhDir = Join-Path $tools "XUIHelper-$xhCommit"
$xui = Join-Path $xhDir "XUIHelper.CLI\bin\Release\net8.0\XUIHelper.CLI.exe"
if (-not (Test-Path $xui)) {
    $xhZip = Join-Path $tools "XUIHelper.zip"
    Invoke-WebRequest "https://github.com/SGCSam/XUIHelper/archive/$xhCommit.zip" -OutFile $xhZip -UseBasicParsing
    Expand-Archive $xhZip $tools -Force
    & dotnet build (Join-Path $xhDir "XUIHelper.CLI\XUIHelper.CLI.csproj") -c Release --nologo -v quiet | Out-Null
    if (-not (Test-Path $xui)) { Fail "XUIHelper did not build" }
}
Write-Host "   XUIHelper ok"

# ---------------------------------------------------------------------------------------------
Step "Configuration"
foreach ($pair in @(@("xenia-dash.config.toml", "xenia-dash"), @("xenia-bootanim.config.toml", "xenia-bootanim"))) {
    $dst = Join-Path $root "$($pair[1])\xenia-canary.config.toml"
    if (-not (Test-Path $dst)) { Copy-Item (Join-Path $setup "config\$($pair[0])") $dst }
}
New-Item -ItemType Directory -Force (Join-Path $root "Games") | Out-Null
Write-Host "   configs in place (kept if they already exist); Games folder ready"

# ---------------------------------------------------------------------------------------------
Step "Patched system modules (Xenia applies the 2858 patches and writes the images)"
$dumps = Join-Path $root "src\re\dumps2858"
New-Item -ItemType Directory -Force $dumps | Out-Null
Get-ChildItem $dumps -Filter *.bin | Remove-Item
$names = "hud", "huduiskin", "xam", "minimediaplayer", "signin", "createprofile", "vk", "gamerprofile", "marketplace"
$want = @($names | ForEach-Object { "$($_)_2858.bin" }) + "dash_2858.bin"
$xenia = Join-Path $root "xenia-dash\xenia_canary.exe"
$p = Start-Process $xenia -WorkingDirectory (Split-Path $xenia) -PassThru -ArgumentList `
    "--fullscreen=false --apply_title_update=true --dump_patched_system_modules=$fs|$tuDash|$dumps `"$fs\dash.xex`""
$sw = [Diagnostics.Stopwatch]::StartNew()
while ($sw.Elapsed.TotalSeconds -lt 180) {
    Start-Sleep 2
    if (@($want | Where-Object { -not (Test-Path (Join-Path $dumps $_)) }).Count -eq 0) { Start-Sleep 3; break }
    if ($p.HasExited) { break }
}
if (-not $p.HasExited) { Stop-Process $p -Force; Start-Sleep 1 }
$missing = @($want | Where-Object { -not (Test-Path (Join-Path $dumps $_)) })
if ($missing) { Fail "Xenia did not write: $($missing -join ', ') (see xenia-dash\xenia.log)" }
Write-Host "   $($want.Count) module images"

# ---------------------------------------------------------------------------------------------
Step "Art (resource packages, scenes, font, keyboard)"
$art = Join-Path $root "src\re\art2858\2858"
if (Test-Path $art) { Remove-Item -Recurse -Force $art }
& $python (Join-Path $setup "extract_packages.py") $dumps $art | Out-Null
if ($LASTEXITCODE) { Fail "extract_packages.py failed" }
& $python (Join-Path $setup "build_art.py") $xui
if ($LASTEXITCODE) { Fail "build_art.py failed" }

Step "Guide images (the long part)"
& $python (Join-Path $setup "make_all_assets.py") $ffmpeg
if ($LASTEXITCODE) { Fail "make_all_assets.py failed" }

# ---------------------------------------------------------------------------------------------
if (-not $SkipVerify) {
    Step "Checking against the reference setup"
    & $python (Join-Path $setup "verify.py")
    if ($LASTEXITCODE) { Fail "Some files differ from the reference setup (listed above)." }
}
Step "Done. Put your game discs (.iso) in Games and run Start-Xbox360.cmd"
