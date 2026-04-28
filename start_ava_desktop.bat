@echo off
setlocal EnableDelayedExpansion
cd /d "%~dp0"

REM ---------------------------------------------------------------------------
REM Ava desktop operator flow: Python runtime + operator HTTP + Tauri UI.
REM Standard packaged exe (cargo binary name): apps\ava-control\src-tauri\target\release\ava-control.exe
REM Build: scripts\build_desktop_release.bat  — or: cd apps\ava-control && npm run tauri:build
REM Dev fallback: npm run tauri:dev when release exe is missing.
REM ---------------------------------------------------------------------------

echo [ava-launch] Starting Python runtime (minimized window)...
start "Ava Python" /MIN /D "%~dp0" python avaagent.py
echo [ava-launch] Runtime process started.

if not exist "%~dp0wait_operator_http.ps1" (
  echo [ava-launch] ERROR: missing "%~dp0wait_operator_http.ps1" ^(required for startup wait^).
  pause
  exit /b 1
)
echo [ava-launch] Waiting for operator HTTP at http://127.0.0.1:5876 ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0wait_operator_http.ps1"
set "OP_FAIL=0"
if errorlevel 1 set "OP_FAIL=1"
if "!OP_FAIL!"=="1" (
  echo [ava-launch] WARNING: operator HTTP did not become ready in time.
  echo           The desktop UI will still launch; it may show ^"offline^" until the API is up.
)

set "REL_EXE=%~dp0apps\ava-control\src-tauri\target\release\ava-control.exe"
if exist "!REL_EXE!" (
  echo [ava-launch] Packaged release found: !REL_EXE!
  echo [ava-launch] Launching desktop app (packaged release^)...
  start "" "!REL_EXE!"
  REM `start` rarely reports failure; if exe was missing we would not be here.
  echo [ava-launch] App launch invoked (packaged release^).
  if "!OP_FAIL!"=="1" echo [ava-launch] Reminder: fix operator HTTP if the UI stays offline.
  pause
  exit /b 0
)

echo [ava-launch] No packaged release at apps\ava-control\src-tauri\target\release\ava-control.exe
echo [ava-launch] Fallback: development mode ^(Vite + tauri dev^).

cd apps\ava-control
if errorlevel 1 (
  echo [ava-launch] ERROR: cannot cd to apps\ava-control
  pause
  exit /b 1
)

if not exist node_modules (
  echo [ava-launch] Installing npm dependencies...
  call npm install
  if errorlevel 1 (
    echo [ava-launch] ERROR: npm install failed. Fix Node/npm and retry.
    pause
    exit /b 1
  )
)

echo [ava-launch] Starting Tauri dev server...
call npm run tauri:dev
set "TAURI_EC=!ERRORLEVEL!"
if not "!TAURI_EC!"=="0" (
  echo [ava-launch] ERROR: tauri:dev exited with code !TAURI_EC!.
  echo          Install Rust ^(+ MSVC build tools on Windows^), run from repo root, check errors above.
  pause
  exit /b !TAURI_EC!
)

echo [ava-launch] tauri:dev ended normally.
pause
exit /b 0
