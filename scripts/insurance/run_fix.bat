@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
python allgrp_watchdog.py fix --config watchdog_config.json
echo.
pause
