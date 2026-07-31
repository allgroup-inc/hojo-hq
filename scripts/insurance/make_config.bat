@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================================
echo  設定ファイル(watchdog_config.json)を作ります
echo  各フォルダ/ファイルを エクスプローラーからここへ
echo  ドラッグ＆ドロップ するとパスが入ります(Enterで確定)
echo ============================================================
echo.
set /p kpi="1) 定例_収集 フォルダ: "
set /p master="2) 【ALLGRPデータ】.xlsx ファイル: "
set /p work="3) 監視ログの出力先フォルダ: "
python -c "import json,sys; json.dump({'kpi_dir':sys.argv[1].strip('\"'),'master':sys.argv[2].strip('\"'),'work_dir':sys.argv[3].strip('\"')}, open('watchdog_config.json','w',encoding='utf-8'), ensure_ascii=False, indent=2)" "%kpi%" "%master%" "%work%"
echo.
echo watchdog_config.json を作成しました。中身:
type watchdog_config.json
echo.
pause
