@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Tat TAT CA ban he thong dang chay nen (cua so 5b + python cua du an nay), roi bat lai dung MOT ban
taskkill /F /T /FI "WINDOWTITLE eq HE THONG PHAN TICH CDR*" >nul 2>&1
taskkill /F /T /FI "WINDOWTITLE eq he_thong*" >nul 2>&1
powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { $_.ExecutablePath -like '*3. TLCN*HeThong*.venv*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }" >nul 2>&1
ping -n 4 127.0.0.1 >nul
if not exist logs mkdir logs
del /q "logs\he_thong.log" >nul 2>&1
start "he_thong" /min cmd /c 5b_CHAY_NEN_TU_KHOI_LAI.bat
