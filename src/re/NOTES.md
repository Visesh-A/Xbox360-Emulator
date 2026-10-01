# Real Guide (hud.xex) in Xenia – reverse-engineering notes

Branch `real-guide` in `G:\Emulators\Xbox360\src\xenia-canary`, experiments run from
`G:\Emulators\Xbox360\xenia-re`. Dashboard 2.0.1888.0 (+2858 patches), xam.xex 2.0.1888.0.
Disassembler: `x360dis.py` (Capstone), dumps via `--dump_system_modules`.

## Research cvars added
- `real_xam_init` – run the real xam.xex DllMain(PROCESS_ATTACH) on a system thread.
- `real_xam_clients=hud.xex` – bind that module's xam imports to the real xam.xex.
- `hardware_info_extra_flags=0x200` – XboxHardwareInfo.flags bit that makes xam start its HUD.
- `load_guide_module`, `dump_system_modules` – inspection helpers.
- Crash handler now logs a symbolized host stack + guest lr (dbghelp + pdb).

## Kernel fixes needed by the real xam (xboxkrnl_misc.cc / xboxkrnl_modules.cc)
- XexLoadExecutable had the wrong signature: real is (name, PHANDLE, type_flags, min_version).
  Reports the already-running title as launched.
- XexStartExecutable: success (title already started by Xenia).
- DumpGetRawDumpInfo → no dump (else xam launches \SystemRoot\ProcessDump.Xex).
- HalGetPowerUpCause → 0x11, XeKeysGetStatus → 0, ExTerminateTitleProcess → ignored,
  KeSetPriorityClassThread → no-op, VdDisplayFatalError → logged.
- Resource-only XEX (huduiskin.xex, first resource tag "XUIZ") now loads; CalculateHash guards no-code modules.

## Guide architecture (xam 1888)
- hud.xex DllMain: XamRegisterSysApp(hmod, 0xFF, 0x913E3000, 0). App 0xFF = Guide.
- Guide message handler 0x913E3000: 0x80000004 = open (type 0/1/2 → scene objects
  ctor 913E4988 / 913E4EE8 / 913E4C90, stored at 913F6CEC), 0x80000005 = close, others forwarded.
- XamRegisterSysApp (818D9F58): app 0xFF handler stored at 0x81AAE898, record at 0x81AAE8A0.
- Open-app 818D9BB0 (XexLoadImage flags 0x40000008 ver 0x20076000 if needed, then msg 0x80000004
  through internal sender 818D2450). Wrappers 818DA108 (type 1) / 818DA178 (type 2).
- HUD manager object 0x81AAED88: +0 state (8 open, 0x10/0x20/0x40), +0x0C pending app,
  +0x10 param, +0x34 request queue, +0x80 active, +0x84 enabled.
  Request post 818DDF78(app, param, p3, flag); step 818DDD40; main task 818DE1F0.
- XamAppLoad (818DE018) opens system UI apps by path (signin.xex, deviceselector.xex, friends.xex…);
  needs +0x84; does XamEnableSystemAppInput(0xFF,1) + XNotifyBroadcast(9,1).
- HUD start: xam boot task 818C2D40 → if (XboxHardwareInfo.flags & 0x200) → 818DE940 (creates
  tasks, sets +0x84) → task 818DE7A8: VdRegisterXamGraphicsNotification(0x818DD7C0), allocates its own
  GPU surfaces (0x195000 bytes), XUI init (818DAED0: XuiRenderInitShared/CreateDC/XuiInit),
  loads media:\XenonJKLatin.xtt and \SystemRoot\huduiskin.xex ("skin" resource), DrvSetSysReqCallback.
- Graphics notification callback 0x818DD7C0(r3, type, data): type 1 copies 16 dwords (display info),
  type 3 copies 0x58 bytes, type 5 schedules the HUD render task with 3 dwords. Sent by the real kernel
  (Vd*), whose protocol is unknown without xboxkrnl.exe.

## Status / blockers
1. Real xam boots and coexists with Xenia HLE xam; HUD system initializes. ✔
2. Guide open trigger: real input path uses XInputd* kernel driver (all unimplemented in Xenia).
   Alternative: call the open path directly (818DDF78 / 818DA108) when Xenia sees Guide.
3. Rendering: needs the kernel side of VdRegisterXamGraphicsNotification (notification types 1/3/5…)
   and a real system command buffer (VdGetSystemCommandBuffer is a 0xBEEF stub) executed by the GPU
   each VdSwap. The kernel protocol is not observable without the real xboxkrnl.exe.
