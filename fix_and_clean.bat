@echo off
cd /d D:\AvaAgentv2

echo.
echo ================================
echo   Ava Agent v2 - Fix and Clean
echo ================================
echo.

echo [1/4] Stripping BOM from phase 2 files...
python fix_bom.py

echo.
echo [2/4] Removing nested brain\brain ghost directory...
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
echo [4/4] Removing stray .tmp files under memory\self reflection...
del /f /q "memory\self reflection\*.tmp" 2>nul

echo.
echo All done! Run push_to_github.bat to commit the cleanup.
pause
