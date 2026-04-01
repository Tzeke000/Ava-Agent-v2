@echo off
cd /d D:\AvaAgent_v2

echo.
echo ================================
echo   Ava Agent v2 - GitHub Push
echo ================================
echo.

set /p msg="Commit message: "

if "%msg%"=="" (
    echo No message entered. Aborting.
    pause
    exit /b
)

git add .
git commit -m "%msg%"
git push

echo.
echo Done! Changes pushed to GitHub.
pause
