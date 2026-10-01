@echo off
rem Same boot + Blades dashboard, rendered at 2x (2560x1440).
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0Start-Xbox360.ps1" -Scale 2 %*
