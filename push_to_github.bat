@echo off
cd /d D:\AvaAgentv2

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

echo.
echo Syncing with remote...
git pull origin master --rebase
if %errorlevel% neq 0 (
    echo.
    echo Pull/rebase failed. Check for conflicts above.
    pause
    exit /b
)

git add .
git commit -m "%msg%"
git push origin master

echo.
echo Done! Changes pushed to GitHub.
pause
