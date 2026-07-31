@echo off
chcp 65001 >nul
set PYTHONUTF8=1
cd /d "%~dp0"
python allgrp_watchdog.py check --config watchdog_config.json
echo.
echo ------------------------------------------------------------
echo  終了コード %errorlevel% : 0=異常なし / 1=重大異常あり(reportsを確認)
echo ------------------------------------------------------------
pause
