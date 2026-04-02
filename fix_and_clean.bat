@echo off
cd /d D:\AvaAgentv2

echo.
echo ================================
echo   Ava Agent v2 - Fix & Clean
echo ================================
echo.

echo [1/3] Stripping BOM from phase 2 files...
python -c "
files = ['brain/emotion.py','brain/attention.py','brain/initiative.py']
for f in files:
    try:
        txt = open(f, encoding='utf-8-sig').read()
        open(f, 'w', encoding='utf-8').write(txt)
        print('  stripped BOM:', f)
    except Exception as e:
        print('  error on', f, ':', e)
"

echo.
echo [2/3] Removing nested brain/brain/ ghost directory...
if exist brain\brain (
    rmdir /s /q brain\brain
    echo   removed brain\brain\
) else (
    echo   brain\brain\ not found - skipping
)

echo.
echo [3/3] Removing ghost from Git tracking...
git rm -r --cached brain/brain/ 2>nul
if %errorlevel% equ 0 (
    echo   untracked brain/brain/ from git
) else (
    echo   brain/brain/ was not tracked - skipping
)

echo.
echo Done! Run push_to_github.bat to commit the cleanup.
pause
