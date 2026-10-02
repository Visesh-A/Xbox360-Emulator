# Boots like a 2006 Xbox 360: original boot animation, then the Blades dashboard.
# Discs: every .iso in the Games folder. The drive is empty at power on and after leaving a
# game, so the Games blade shows Open Tray: choose a disc in the small "insert a disc" window
# (controller: D-pad, A insert, B leave as is; the last game played is highlighted), then
# Close Tray and the dashboard starts the game, as the console did.
# -Disc <iso> powers on with that disc already in the drive.
#   Boot animation: dbexperiment Xenia fork (it can run bootanim.xex)
#   Dashboard/games: xenia-dash, Xenia Canary 02d2cb5 built with dashboard_disc/dashboard_handoff
param(
    [string]$Disc,              # path to a game .iso to leave in the tray
    [ValidateSet("2858", "1888")] [string]$Version = "2858",  # 2858 = June 2006 update, 1888 = Nov 2005 launch
    [double]$DashDelay = 3,     # seconds into the boot animation to start loading the dashboard (hidden behind it)
    [double]$BootSeconds = 10,  # total time the boot animation stays on screen
    [ValidateSet(1, 2, 3)] [int]$Scale = 1,  # 1 = native 720p (original), 2 = 2560x1440 internal render
    [int]$FrameLimit = 0,       # 0 = Xenia default (paced by the guest's own 60 Hz vsync)
    [switch]$NoBoot,
    [string]$ExtraArgs = ""   # extra Xenia options for the dashboard and games (debugging)
)

# One console at a time: a second start (e.g. a double-click registering twice) would close
# this one's windows and both would fight over the dashboard's hand-off, so it just leaves.
$single = New-Object Threading.Mutex($false, "Local\Xbox360Launcher")
try { if (-not $single.WaitOne(0)) { exit } } catch [Threading.AbandonedMutexException] {}

$root      = $PSScriptRoot
$dashFs    = Join-Path $root "1888.FS"
$xenia     = Join-Path $root "xenia-dash\xenia_canary.exe"
$bootXenia = Join-Path $root "xenia-bootanim\xenia_canary.exe"
$handoff   = Join-Path (Split-Path $xenia) "dashboard_launch.txt"
$gamesDir  = Join-Path $root "Games"
# Everything the launcher does (and any error) goes to launcher.log
try { Start-Transcript -LiteralPath (Join-Path $root "launcher.log") -Force | Out-Null } catch {}

# -Disc: in the drive for the first power on only; afterwards the dashboard starts empty
$bootDisc = $Disc

# The 2858 system update is installed as a Xenia title update (content\...\000B0000\SystemUpdate_2.0.2858.0)
# that patches the 1888 base files on load. Toggle it in both emulators' configs.
$applyUpdate = if ($Version -eq "2858") { "true" } else { "false" }
# Every run rewrites these, so each .cmd always gets its own settings.
foreach ($exe in $xenia, $bootXenia) {
    $cfg = Join-Path (Split-Path $exe) "xenia-canary.config.toml"
    $t = [IO.File]::ReadAllText($cfg)
    $t = $t -replace '(?m)^apply_title_update = (true|false)', "apply_title_update = $applyUpdate"
    $t = $t -replace '(?m)^draw_resolution_scale_x = \d+', "draw_resolution_scale_x = $Scale"
    $t = $t -replace '(?m)^draw_resolution_scale_y = \d+', "draw_resolution_scale_y = $Scale"
    $t = $t -replace '(?m)^framerate_limit = \d+', "framerate_limit = $FrameLimit"
    # 2006 consoles had no HDMI: the Xbox 360 HD AV (component) cable, which the June 2006
    # dashboard knows (with Xenia's default HDMI value it shows a time zone as the video mode)
    $t = $t -replace '(?m)^avpack = \d+', 'avpack = 3'
    [IO.File]::WriteAllText($cfg, $t)
}

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class Win {
    [DllImport("user32.dll")] public static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int cx, int cy, uint flags);
    [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
}
"@
$TOPMOST = [IntPtr](-1); $NOMOVE_NOSIZE = 0x0003

function Wait-Window($proc, $timeoutSec = 15) {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    while ($sw.Elapsed.TotalSeconds -lt $timeoutSec) {
        $proc.Refresh()
        if ($proc.MainWindowHandle -ne [IntPtr]::Zero) { return $proc.MainWindowHandle }
        Start-Sleep -Milliseconds 100
    }
    return [IntPtr]::Zero
}

# Bring a window to the front and give it keyboard/controller focus.
# Windows can refuse SetForegroundWindow from a background script, so also bounce it through topmost.
function Focus-Window($proc, $h) {
    if ($h -eq [IntPtr]::Zero) { return }
    [void][Win]::SetWindowPos($h, $TOPMOST, 0, 0, 0, 0, $NOMOVE_NOSIZE)
    [void][Win]::SetWindowPos($h, [IntPtr](-2), 0, 0, 0, 0, $NOMOVE_NOSIZE)   # -2 = HWND_NOTOPMOST
    [void](New-Object -ComObject WScript.Shell).AppActivate($proc.Id)
    [void][Win]::SetForegroundWindow($h)
}

# Starts the dashboard (disc in the tray) or a game; every title hands its next launch back to us.
function Start-Title([string]$target, [bool]$isDashboard, [bool]$powerOn = $false) {
    if (Test-Path -LiteralPath $handoff) { Remove-Item -LiteralPath $handoff }
    $xeniaArgs = @("--dashboard_handoff=true", "--blades_guide=true")
    # Themes > Guide Background: the Guide's images rendered for the chosen
    # background, in the background (unquoted: Xenia keeps quotes literally)
    $lookPython = Join-Path $root ".venv\Scripts\python.exe"  # made by Setup-Xbox360.ps1
    if (-not (Test-Path -LiteralPath $lookPython)) {
        $lookPython = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    }
    $lookScript = Join-Path $root "src\re\render_guide_look.py"
    if ((Test-Path -LiteralPath $lookPython) -and (Test-Path -LiteralPath $lookScript) -and
        -not ("$lookPython$lookScript" -match ' ')) {
        $xeniaArgs += "--guide_look_python=$lookPython"
        $xeniaArgs += "--guide_look_script=$lookScript"
    }
    if ($ExtraArgs) { $xeniaArgs += $ExtraArgs }
    # Power-on: nobody signed in from before; the Auto Sign-In profile signs in
    if ($powerOn) { $xeniaArgs += "--power_on=true" }
    if ($isDashboard) {
        $xeniaArgs += "--disc_folder=`"$gamesDir`""
        if ($bootDisc) { $xeniaArgs += "--dashboard_disc=`"$bootDisc`""; $script:bootDisc = $null }
    }
    # The disc picker highlights the last game played
    if (-not $isDashboard -and $Disc) { [IO.File]::WriteAllText((Join-Path (Split-Path $xenia) "last_disc.txt"), $Disc) }
    $xeniaArgs += "`"$target`""
    Start-Process $xenia -ArgumentList $xeniaArgs -WorkingDirectory (Split-Path $xenia) -PassThru
}

# What the title asked for when it exited: "disc", "dashboard", "off" (Guide: turn off
# console), or $null (window closed)
function Read-Handoff {
    if (-not (Test-Path -LiteralPath $handoff)) { return $null }
    $request = Get-Content -LiteralPath $handoff -Raw
    if ($request -eq "OFF") { return "off" }
    if ($request -match '(?i)cdrom0|^dvd:|^d:') {
        # "<guest path>|<disc image>": the disc the dashboard has in its drive
        $parts = $request -split '\|', 2
        if ($parts.Count -eq 2 -and $parts[1].Trim()) { $script:Disc = $parts[1].Trim() }
        return "disc"
    }
    # "|<disc image>": the dashboard again (e.g. createprofile's Exit Session) with
    # that disc still in its drive
    if ($request -match '^\|(.+)$' -and $onDashboard) { $script:bootDisc = $Matches[1].Trim() }
    return "dashboard"
}

# Clear out anything left from a previous run
Get-Process xenia_canary -ErrorAction SilentlyContinue | Stop-Process -Force

$boot = $null
$clock = [Diagnostics.Stopwatch]::StartNew()
if (-not $NoBoot) {
    $boot = Start-Process $bootXenia -ArgumentList "`"$dashFs\bootanim.xex`"" `
        -WorkingDirectory (Split-Path $bootXenia) -PassThru
    $h = Wait-Window $boot
    # Keep the animation above the dashboard window while the dashboard loads
    if ($h -ne [IntPtr]::Zero) { [void][Win]::SetWindowPos($h, $TOPMOST, 0, 0, 0, 0, $NOMOVE_NOSIZE) }
    $clock.Restart()
    Start-Sleep -Milliseconds ([int]($DashDelay * 1000))
}

$current = Start-Title "$dashFs\dash.xex" $true $true
$ch = Wait-Window $current

if ($boot) {
    $left = $BootSeconds - $clock.Elapsed.TotalSeconds
    if ($left -gt 0) { Start-Sleep -Milliseconds ([int]($left * 1000)) }
    if (-not $boot.HasExited) { $boot | Stop-Process -Force }
}
Focus-Window $current $ch

# Dashboard <-> game loop, like the console's own title switching.
$onDashboard = $true
while ($true) {
    $current.WaitForExit()
    # Each Xenia start rewrites xenia.log: keep this session's (the last 10)
    $logs = Join-Path $root "logs"
    New-Item -ItemType Directory -Force $logs | Out-Null
    $log = Join-Path (Split-Path $xenia) "xenia.log"
    if (Test-Path -LiteralPath $log) {
        Copy-Item -LiteralPath $log (Join-Path $logs ("xenia-{0:yyyyMMdd-HHmmss}.log" -f (Get-Date))) -Force
        Get-ChildItem $logs -Filter "xenia-*.log" | Sort-Object Name -Descending | Select-Object -Skip 10 |
            Remove-Item -Force
    }
    $request = Read-Handoff
    if ($request -eq "off") { break }   # Guide: "Turn off console"
    if ($onDashboard) {
        if ($request -eq "disc" -and $Disc) { $current = Start-Title $Disc $false; $onDashboard = $false }
        elseif ($request) { $current = Start-Title "$dashFs\dash.xex" $true }
        else { break }   # dashboard window closed: console off
    } else {
        # Any way out of a game (its own "exit to dashboard", or closing the window) lands on the dashboard
        $current = Start-Title "$dashFs\dash.xex" $true; $onDashboard = $true
    }
    Focus-Window $current (Wait-Window $current)
}
