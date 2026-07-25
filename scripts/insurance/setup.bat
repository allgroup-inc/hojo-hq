@echo off
chcp 65001 >nul
echo [1/2] Python を確認します...
python --version || (echo Python が見つかりません。https://www.python.org/ からインストールしてください（インストール時に "Add python.exe to PATH" にチェック）。& pause & exit /b 1)
echo [2/2] openpyxl を導入します...
python -m pip install --quiet openpyxl && echo 完了しました。 || echo pip に失敗しました。ネット接続を確認してください。
pause
