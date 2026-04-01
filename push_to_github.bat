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
echo Stashing local changes...
git stash

echo.
echo Syncing with remote...
git pull origin master --rebase
if %errorlevel% neq 0 (
    echo.
    echo Pull/rebase failed. Restoring your changes...
    git stash pop
    pause
    exit /b
)

echo.
echo Restoring local changes...
git stash pop

git add .
git commit -m "%msg%"
git push origin master

echo.
echo Done! Changes pushed to GitHub.
pause
