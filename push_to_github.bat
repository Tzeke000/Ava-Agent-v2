@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d D:\AvaAgentv2

echo.
echo ===============================================
echo   Ava Agent v2 - One-Click GitHub Sync
echo ===============================================
echo.

for /f %%i in ('git rev-parse --abbrev-ref HEAD 2^>nul') do set "current_branch=%%i"
if not defined current_branch (
    echo Failed to detect current branch.
    pause
    exit /b 1
)

echo Current branch: %current_branch%
echo.

echo Staging all changes...
git add -A
if errorlevel 1 (
    echo git add failed.
    pause
    exit /b 1
)

set "changed_count=0"
set "file1="
set "file2="
set "file3="

for /f "delims=" %%f in ('git diff --cached --name-only') do (
    set /a changed_count+=1
    if !changed_count! EQU 1 set "file1=%%f"
    if !changed_count! EQU 2 set "file2=%%f"
    if !changed_count! EQU 3 set "file3=%%f"
)

set "auto_msg=auto: %changed_count% files updated"
if defined file1 set "auto_msg=%auto_msg% - %file1%"
if defined file2 set "auto_msg=%auto_msg%, %file2%"
if defined file3 set "auto_msg=%auto_msg%, %file3%..."

set "did_commit=0"
if %changed_count% GTR 0 (
    echo Auto commit message:
    echo   %auto_msg%
    echo.
    set /p custom_msg=Custom commit message (leave blank to use auto): 
    if "%custom_msg%"=="" (
        set "final_msg=%auto_msg%"
    ) else (
        set "final_msg=%custom_msg%"
    )

    echo.
    echo Committing...
    git commit -m "%final_msg%"
    if errorlevel 1 (
        echo Commit failed. Resolve issues and run again.
        pause
        exit /b 1
    )
    set "did_commit=1"
) else (
    echo Nothing to commit. Skipping commit step.
)

echo.
echo Pulling latest changes with rebase on %current_branch%...
git pull --rebase origin %current_branch%
if errorlevel 1 (
    echo Pull --rebase failed. Resolve conflicts and run again.
    pause
    exit /b 1
)

echo.
echo Pushing current branch (%current_branch%)...
git push origin %current_branch%
if errorlevel 1 (
    echo Push to %current_branch% failed.
    pause
    exit /b 1
)
set "pushed_current=1"
set "pushed_master=0"
set "merged_to_master=0"

if /i not "%current_branch%"=="master" (
    echo.
    echo Syncing master from %current_branch%...
    git checkout master
    if errorlevel 1 (
        echo Failed to checkout master.
        pause
        exit /b 1
    )

    git pull --rebase origin master
    if errorlevel 1 (
        echo Pull --rebase on master failed.
        git checkout %current_branch%
        pause
        exit /b 1
    )

    git merge %current_branch% --no-ff
    if errorlevel 1 (
        echo Merge into master failed.
        git checkout %current_branch%
        pause
        exit /b 1
    )
    set "merged_to_master=1"

    git push origin master
    if errorlevel 1 (
        echo Push to master failed.
        git checkout %current_branch%
        pause
        exit /b 1
    )
    set "pushed_master=1"

    git checkout %current_branch%
    if errorlevel 1 (
        echo WARNING: pushed successfully, but failed to switch back to %current_branch%.
    )
)

echo.
echo ===============================================
echo Sync summary
echo ===============================================
echo Current branch: %current_branch%
if "%did_commit%"=="1" (
    echo Commit created: YES
    echo Commit message: %final_msg%
) else (
    echo Commit created: NO (nothing to commit)
)
if "%pushed_current%"=="1" echo Pushed branch: %current_branch%
if "%pushed_master%"=="1" (
    echo Merged into master: YES
    echo Pushed branch: master
) else (
    echo Merged into master: NO
)
echo.
echo Done.
pause
