@echo off
chcp 65001 >nul
cd /d "%~dp0"
.venv\Scripts\python local_test.py
if errorlevel 1 goto fail
echo 完成。请阅读上方结果。
pause
exit /b 0
:fail
echo 未完成。请按README排查上方错误，不要关闭前忽略错误信息。
pause
exit /b 1
