@echo off
setlocal
cd /d "%~dp0"
title Copper Quant Cloud - Account Reset
where py >nul 2>nul
if %errorlevel%==0 (
  set "PY=py -3"
) else (
  set "PY=python"
)
echo Installing required PostgreSQL driver if needed...
%PY% -m pip install "psycopg[binary]>=3.2,<4"
if errorlevel 1 (
  echo Dependency installation failed.
  pause
  exit /b 1
)
%PY% reset_cloud_account.py
echo.
pause
