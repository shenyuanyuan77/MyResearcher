@echo off
REM ============================================================
REM  YanJiuZhiTan AI - Stop all services (pure ASCII)
REM ============================================================
title YanJiuZhiTan AI - Stop

echo Stopping YanJiuZhiTan AI services...

REM Kill listeners on the three ports
for %%P in (7001 8000 3001) do (
  for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":%%P " ^| findstr LISTENING') do (
    echo   Killing PID %%a on port %%P
    taskkill /F /PID %%a >nul 2>&1
  )
)

echo.
echo All services stopped.
pause
