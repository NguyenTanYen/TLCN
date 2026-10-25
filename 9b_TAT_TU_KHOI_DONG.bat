@echo off
schtasks /End /TN "TLCN_HeThongCDR" >nul 2>&1
schtasks /Delete /TN "TLCN_HeThongCDR" /F
for /f "tokens=5" %%p in ('netstat -ano ^| findstr /r /c:"127.0.0.1:8000 .*LISTENING"') do taskkill /F /PID %%p >nul 2>&1
echo Da go tu khoi dong va tat he thong.
pause
