@echo off
setlocal
cd /d "%~dp0"
set /p USERNAME=Cloud account username: 
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 -m pip install "psycopg[binary]>=3.2,<4"
  py -3 provision_admin.py --username "%USERNAME%"
) else (
  python -m pip install "psycopg[binary]>=3.2,<4"
  python provision_admin.py --username "%USERNAME%"
)
pause
