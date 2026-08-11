@echo off
REM ============================================================
REM  YanJiuZhiTan AI (Research-Quest) - Windows Launcher
REM  Pure ASCII to avoid cmd.exe GBK/UTF-8 encoding crash.
REM ============================================================
cd /d "%~dp0"
title YanJiuZhiTan AI Launcher

echo ============================================================
echo   YanJiuZhiTan AI - Starting services...
echo ============================================================
echo.

REM ---- 1. Locate Python (prefer Anaconda, skip WindowsApps stub) ----
set "PY="
for %%P in (
  "D:\Software\Anaconda\python.exe"
  "C:\ProgramData\Anaconda3\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
  "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
) do (
  if exist %%P ( if not defined PY ( set "PY=%%~P" ) )
)
if not defined PY (
  for /f "delims=" %%I in ('where python 2^>nul') do (
    echo %%I | findstr /i "WindowsApps" >nul || ( if not defined PY ( set "PY=%%I" ) )
  )
)
if not defined PY (
  echo [ERROR] Python not found. Install Python 3.10+ or add to PATH.
  pause
  exit /b 1
)
echo Python: %PY%
echo.

REM ---- 2. Python deps ----
echo [1/4] Checking Python deps...
"%PY%" -c "import fastapi, langgraph, deepagents" 2>nul
if errorlevel 1 (
  echo       Missing deps, installing requirements.txt...
  "%PY%" -m pip install -r requirements.txt
  if errorlevel 1 ( echo [ERROR] pip install failed. & pause & exit /b 1 )
)
echo       Deps OK.
echo.

REM ---- 3. Frontend deps ----
echo [2/4] Checking frontend deps...
if not exist "frontend\node_modules" (
  echo       node_modules missing, running npm install...
  pushd frontend & call npm install & popd
)
echo       Frontend deps OK.
echo.

REM ---- 4. Launch 3 services in separate windows ----
echo [3/4] Launching services (each in its own window)...
start "YanJiuZhiTan - MCP :7001" cmd /k "cd /d %~dp0 && set PYTHONPATH=%~dp0src && %PY% -m mcp_server.server_main"
timeout /t 4 /nobreak >nul
start "YanJiuZhiTan - Backend :8000" cmd /k "cd /d %~dp0 && set PYTHONPATH=%~dp0src && set BACKEND_PORT=8000 && %PY% -m api_view.web_main"
timeout /t 3 /nobreak >nul
start "YanJiuZhiTan - Frontend :3001" cmd /k "cd /d %~dp0frontend && npm run dev"
timeout /t 3 /nobreak >nul

echo.
echo [4/4] All services launched in new windows.
echo ============================================================
echo   YanJiuZhiTan AI started successfully.
echo.
echo   Frontend:   http://localhost:3001
echo   Backend:    http://localhost:8000/docs
echo   Login:      yanjiu / yanjiu123
echo.
echo   Each service runs in its own window.
echo   Wait ~30s for the Agent to initialize (until the header
echo   shows a green "Service Online" badge).
echo ============================================================
echo.
echo This window can be closed safely.
pause
