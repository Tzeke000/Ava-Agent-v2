@echo off
echo Stopping Ava...
for /f %%i in (D:\AvaAgentv2\state\ava.pid) do (
    taskkill /PID %%i /F
)
taskkill /IM ava-control.exe /F
echo Ava stopped.
pause
